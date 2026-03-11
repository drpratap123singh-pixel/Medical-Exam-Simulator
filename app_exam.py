import streamlit as st
import json
import os
import requests
import PyPDF2
import re
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="INI SS CBT Simulator", initial_sidebar_state="collapsed")

QBANK_FILE = "local_qbank.json"
HISTORY_FILE = "local_history.json"

# --- 1. DATA MANAGEMENT FUNCTIONS ---
def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- 2. SESSION STATE INITIALIZATION ---
if 'qbank' not in st.session_state:
    st.session_state.qbank = load_json(QBANK_FILE)
if 'history' not in st.session_state:
    st.session_state.history = load_json(HISTORY_FILE)
    
# modes: 'dashboard', 'exam', 'review'
if 'mode' not in st.session_state:
    st.session_state.mode = 'dashboard'
    
if 'active_questions' not in st.session_state:
    st.session_state.active_questions = []
if 'current_q_idx' not in st.session_state:
    st.session_state.current_q_idx = 0
if 'responses' not in st.session_state:
    st.session_state.responses = {}
if 'statuses' not in st.session_state:
    st.session_state.statuses = {} 
if 'guesses' not in st.session_state:
    st.session_state.guesses = {}

# --- 3. AI GENERATION LOGIC (Dynamic Model Fetching) ---
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def generate_questions_from_ai(api_key, topic, pdf_text="", num_q=10):
    clean_key = api_key.strip()
    
    # STEP 1: Dynamically ask Google which models this specific API key has access to
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
    
    try:
        list_resp = requests.get(list_url)
        if list_resp.status_code == 400:
            st.error("Your API Key is invalid. Please check it and try again.")
            return None
            
        list_resp.raise_for_status()
        available_models = list_resp.json().get('models', [])
        
        # Filter for models that actually support text generation
        valid_models = [
            m['name'].replace('models/', '') 
            for m in available_models 
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]
        
        if not valid_models:
            st.error("Your API key does not have access to any text generation models in your region.")
            return None
            
        # Pick the best available model (prioritizing the newest flash/pro models)
        chosen_model = valid_models[0] # Fallback to whatever is first
        preferences = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro', 'gemini-pro']
        
        for pref in preferences:
            found = False
            for vm in valid_models:
                if pref in vm:
                    chosen_model = vm
                    found = True
                    break
            if found:
                break
                
    except Exception as e:
        st.error(f"Failed to authenticate or fetch allowed models. Error: {e}")
        return None

    # STEP 2: Use the exact model the API just told us is valid
    prompt = f"""
    You are an expert medical examiner for the INI SS (super-specialty) exam.
    Create {num_q} multiple-choice questions on the topic: "{topic}".
    If context text is provided below, base the questions on that text.
    
    Context Text: {pdf_text[:15000]}
    
    CRITICAL INSTRUCTION: Your response MUST be ONLY a valid JSON array. Do not include any markdown formatting or extra text.
    Format exactly like this:
    [
      {{
        "question": "Question text here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_answer": "Option B",
        "rationale": "Explanation here."
      }}
    ]
    """
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    
    generate_url = f"https://generativelanguage.googleapis.com/v1beta/models/{chosen_model}:generateContent?key={clean_key}"
    
    try:
        response = requests.post(generate_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if 'candidates' not in result or not result['candidates']:
            st.error("The AI returned an empty response. Please try again.")
            return None
            
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Smart cleanup using regex to find the JSON array
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            raw_text = match.group(0)
            
        return json.loads(raw_text)
        
    except requests.exceptions.HTTPError as err:
        st.error(f"Failed to generate questions. The model '{chosen_model}' rejected the request.")
        with st.expander("Click to view detailed API error"):
            st.code(response.text)
        return None
    except json.JSONDecodeError:
        st.error("The AI returned improperly formatted data. Please try generating again.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

# --- 4. NAVIGATION & EXAM LOGIC ---
def start_exam(questions):
    if not questions: return
    st.session_state.active_questions = questions
    st.session_state.mode = 'exam'
    st.session_state.current_q_idx = 0
    st.session_state.responses = {}
    st.session_state.guesses = {i: False for i in range(len(questions))}
    st.session_state.statuses = {i: 0 for i in range(len(questions))}
    st.session_state.statuses[0] = 2 # First question visited

def go_to_dashboard():
    st.session_state.mode = 'dashboard'
    st.session_state.active_questions = []

def get_current_selection():
    key = f"radio_{st.session_state.current_q_idx}"
    return st.session_state.get(key, st.session_state.responses.get(st.session_state.current_q_idx, None))

def move_to_next():
    total_q = len(st.session_state.active_questions)
    if st.session_state.current_q_idx < total_q - 1:
        st.session_state.current_q_idx += 1
        if st.session_state.statuses[st.session_state.current_q_idx] == 0:
            st.session_state.statuses[st.session_state.current_q_idx] = 2

def move_to_prev():
    if st.session_state.current_q_idx > 0:
        st.session_state.current_q_idx -= 1

def save_and_next():
    idx = st.session_state.current_q_idx
    ans = get_current_selection()
    if ans:
        st.session_state.responses[idx] = ans
        st.session_state.statuses[idx] = 1 # Answered
    else:
        st.session_state.responses.pop(idx, None)
        st.session_state.statuses[idx] = 2 # Not Answered
    move_to_next()

def mark_and_next():
    idx = st.session_state.current_q_idx
    ans = get_current_selection()
    if ans:
        st.session_state.responses[idx] = ans
        st.session_state.statuses[idx] = 4 # Answered & Marked
    else:
        st.session_state.responses.pop(idx, None)
        st.session_state.statuses[idx] = 3 # Marked
    move_to_next()

def clear_response():
    idx = st.session_state.current_q_idx
    st.session_state.responses.pop(idx, None)
    if f"radio_{idx}" in st.session_state:
        st.session_state[f"radio_{idx}"] = None
    st.session_state.guesses[idx] = False
    if f"guess_cb_{idx}" in st.session_state:
        st.session_state[f"guess_cb_{idx}"] = False
    st.session_state.statuses[idx] = 2 

def jump_to_question(idx):
    if st.session_state.mode == 'exam':
        curr = st.session_state.current_q_idx
        if st.session_state.statuses[curr] == 0:
            st.session_state.statuses[curr] = 2
        if st.session_state.statuses[idx] == 0:
            st.session_state.statuses[idx] = 2
    st.session_state.current_q_idx = idx

def get_correct_answer(q):
    correct = q.get('correct_answer')
    if not correct and 'answerOptions' in q:
        for opt in q.get('answerOptions', []):
            if opt.get('isCorrect'): return opt.get('text')
    return correct

def submit_exam():
    score = 0
    total = len(st.session_state.active_questions)
    for i, q in enumerate(st.session_state.active_questions):
        if st.session_state.responses.get(i) == get_correct_answer(q):
            score += 1
            
    exam_record = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "date": datetime.now().strftime("%b %d, %Y - %I:%M %p"),
        "score": score,
        "total": total,
        "questions": st.session_state.active_questions,
        "responses": st.session_state.responses,
        "guesses": st.session_state.guesses
    }
    
    st.session_state.history.insert(0, exam_record) # Add to top of history
    save_json(st.session_state.history, HISTORY_FILE)
    
    st.session_state.mode = 'review'
    st.session_state.current_q_idx = 0

def load_past_exam(record, is_retake=False):
    st.session_state.active_questions = record['questions']
    st.session_state.current_q_idx = 0
    if is_retake:
        start_exam(record['questions'])
    else:
        st.session_state.responses = record.get('responses', {})
        st.session_state.guesses = record.get('guesses', {})
        st.session_state.mode = 'review'


# --- 5. CSS STYLING ---
st.markdown("""
<style>
    /* Hide Streamlit components for app-like feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .top-bar-marrow {
        background-color: #212b36; color: white; padding: 10px 20px; font-size: 14px;
        display: flex; justify-content: flex-end; border-radius: 4px; margin-top: -20px; margin-bottom: 10px;
    }
    
    .q-type-bar { color: #d32f2f; font-weight: bold; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 15px;}
    .q-no { font-weight: bold; margin-bottom: 10px; color: #333; font-size: 18px;}
    .q-text { font-size: 16px; color: #333; margin-bottom: 20px; line-height: 1.6;}
    
    .profile-box { display: flex; align-items: center; background-color: #f9f9f9; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 15px;}
    .legend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px; margin-bottom: 15px;}
    
    .palette-header { background-color: #2167a6; color: white; padding: 8px; font-weight: bold; text-align: center; border-radius: 4px; margin-bottom: 10px;}
    
    /* Review Screen Specific Styles */
    .opt-correct { background-color: #e8f5e9; border: 2px solid #4caf50; padding: 10px; border-radius: 5px; margin-bottom: 8px; font-weight: bold;}
    .opt-wrong { background-color: #ffebee; border: 2px solid #f44336; padding: 10px; border-radius: 5px; margin-bottom: 8px; font-weight: bold;}
    .opt-neutral { background-color: #f5f5f5; border: 1px solid #ddd; padding: 10px; border-radius: 5px; margin-bottom: 8px;}
    .rationale-box { background-color: #e3f2fd; border-left: 5px solid #2196f3; padding: 15px; margin-top: 20px; border-radius: 4px;}
</style>
""", unsafe_allow_html=True)


# --- 6. DASHBOARD VIEW ---
def render_dashboard():
    st.title("🩺 INI SS Generator & Grand Test Simulator")
    
    with st.expander("🔑 Setup: Enter your Google Gemini API Key here first!", expanded=True):
        api_key = st.text_input("API Key", type="password", placeholder="Paste your API key here...", label_visibility="collapsed")
        st.markdown("Don't have one? [Get your free API Key here](https://aistudio.google.com/app/apikey)")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🧠 Generate New Exam", "📄 From PDF", "📥 Import JSON", "📊 Past Exams & Grand Tests"])
    
    with tab1:
        st.subheader("Generate Exam by Topic")
        topic = st.text_input("Enter Topic (e.g., Rheumatoid Arthritis, Vasculitis)")
        num_q = st.slider("Number of Questions", 5, 50, 10)
        if st.button("Generate & Start Exam", key="btn_gen_topic"):
            if not api_key: st.error("Please enter your API Key in the setup box above!")
            elif not topic: st.error("Please enter a topic!")
            else:
                with st.spinner("AI is dynamically finding approved models and generating your exam. Please wait..."):
                    qs = generate_questions_from_ai(api_key, topic, num_q=num_q)
                    if qs: 
                        st.session_state.qbank.extend(qs)
                        save_json(st.session_state.qbank, QBANK_FILE)
                        start_exam(qs)
                        st.rerun()
                        
    with tab2:
        st.subheader("Generate Exam from PDF Document")
        uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
        pdf_topic = st.text_input("Specific focus for these PDF questions (Optional)")
        num_q_pdf = st.slider("Number of Questions (PDF)", 5, 50, 10)
        if st.button("Generate & Start Exam", key="btn_gen_pdf"):
            if not api_key: st.error("Please enter your API Key in the setup box above!")
            elif not uploaded_file: st.error("Please upload a PDF!")
            else:
                with st.spinner("Reading PDF and dynamically selecting AI model..."):
                    text = extract_text_from_pdf(uploaded_file)
                    topic_str = pdf_topic if pdf_topic else "the provided document"
                    qs = generate_questions_from_ai(api_key, topic_str, pdf_text=text, num_q=num_q_pdf)
                    if qs: 
                        st.session_state.qbank.extend(qs)
                        save_json(st.session_state.qbank, QBANK_FILE)
                        start_exam(qs)
                        st.rerun()
                        
    with tab3:
        st.subheader("Start Exam from Global Question Bank")
        if not st.session_state.qbank:
            st.warning("Your question bank is empty. Generate some questions first, or paste JSON below.")
        else:
            if st.button(f"Start Grand Test with All Saved Questions ({len(st.session_state.qbank)})", type="primary"):
                start_exam(st.session_state.qbank)
                st.rerun()
                
        st.divider()
        st.info("Paste a JSON code block from a previous chat to add it to your bank.")
        raw_json = st.text_area("Paste JSON here", height=150)
        if st.button("Import JSON & Start"):
            try:
                qs = json.loads(raw_json)
                st.session_state.qbank.extend(qs)
                save_json(st.session_state.qbank, QBANK_FILE)
                start_exam(qs)
                st.rerun()
            except Exception as e:
                st.error("Invalid JSON format.")

    with tab4:
        st.subheader("Your Exam History")
        if not st.session_state.history:
            st.info("You haven't taken any exams yet. Generate one to get started!")
        else:
            for rec in st.session_state.history:
                with st.container(border=True):
                    cols = st.columns([4, 2, 2])
                    cols[0].markdown(f"**Exam Taken:** {rec['date']}<br>Questions: {rec['total']}", unsafe_allow_html=True)
                    cols[0].markdown(f"**Score:** <span style='color:green; font-size:18px; font-weight:bold;'>{rec['score']} / {rec['total']}</span>", unsafe_allow_html=True)
                    
                    if cols[1].button("🔍 Review Exam", key=f"rev_{rec['id']}", use_container_width=True):
                        load_past_exam(rec, is_retake=False)
                        st.rerun()
                    if cols[2].button("🔄 Retake Exam", key=f"ret_{rec['id']}", use_container_width=True):
                        load_past_exam(rec, is_retake=True)
                        st.rerun()

# --- 7. EXAM UI ---
def render_exam_ui():
    idx = st.session_state.current_q_idx
    q_data = st.session_state.active_questions[idx]
    total_q = len(st.session_state.active_questions)
    
    st.markdown("<div class='top-bar-marrow'><span>📄 Question Paper &nbsp;&nbsp;|&nbsp;&nbsp; ℹ️ Instructions</span></div>", unsafe_allow_html=True)
    
    col_main, col_side = st.columns([3.5, 1.5], gap="medium")
    
    with col_main:
        # Reduced height so buttons stay fixed at the bottom of the screen without needing to scroll the main page
        with st.container(height=480, border=True):
            st.markdown(f"<div style='text-align:right; color:#d32f2f; font-weight:bold;'>Time Left: 00:32:04</div>", unsafe_allow_html=True)
            st.markdown("<div class='q-type-bar'>Question type : MCQ</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='q-no'>Question no : {idx + 1}</div>", unsafe_allow_html=True)
            
            st.markdown(f"<div class='q-text'>{q_data.get('question', '')}</div>", unsafe_allow_html=True)
            
            options = q_data.get('options', [])
            if not options and 'answerOptions' in q_data:
                options = [opt.get('text', '') for opt in q_data.get('answerOptions', [])]
                
            current_ans = st.session_state.responses.get(idx, None)
            default_idx = options.index(current_ans) if current_ans in options else None
            
            st.radio("Options", options, index=default_idx, key=f"radio_{idx}", label_visibility="collapsed")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Active Guessing logic
            is_guessed = st.checkbox("I am guessing this ℹ️", value=st.session_state.guesses.get(idx, False), key=f"guess_cb_{idx}")
            st.session_state.guesses[idx] = is_guessed
            
        # Action Buttons Fixed Below Container (They will no longer be pushed down by long questions)
        btn_c1, btn_c2, btn_spacer, btn_c3, btn_c4 = st.columns([2.5, 2, 1, 2.5, 2])
        with btn_c1: st.button("Mark for Review & Next", on_click=mark_and_next, use_container_width=True)
        with btn_c2: st.button("Clear Response", on_click=clear_response, use_container_width=True)
        with btn_c3: st.button("Save and Next", on_click=save_and_next, type="primary", use_container_width=True)
        with btn_c4: st.button("Submit", on_click=submit_exam, type="primary", use_container_width=True)

    with col_side:
        # Adjusted height to match the new left column layout
        with st.container(height=560, border=True):
            st.markdown("""
            <div class='profile-box'>
                <div style='font-size:35px; margin-right:10px;'>👤</div>
                <div style='line-height:1.2;'><b>Candidate Name</b><br><span style='color:gray; font-size:12px;'>INI SS Aspirant</span></div>
            </div>
            """, unsafe_allow_html=True)
            
            stats = {0:0, 1:0, 2:0, 3:0, 4:0}
            for s in st.session_state.statuses.values(): stats[s] = stats.get(s, 0) + 1
                
            st.markdown(f"""
            <div class='legend-grid'>
                <div>🟢 {stats[1]} Answered</div>
                <div>🔴 {stats[2]} Not Answered</div>
                <div>⚪ {stats[0]} Not Visited</div>
                <div>🟣 {stats[3]} Marked</div>
            </div>
            <div style='font-size:12px; margin-bottom:15px;'>✅ {stats[4]} Ans & Marked (Will not be evaluated)</div>
            <div class='palette-header'>All questions</div>
            """, unsafe_allow_html=True)
            
            cols_per_row = 4
            for i in range(0, total_q, cols_per_row):
                row_cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < total_q:
                        q_num = i + j
                        stat = st.session_state.statuses[q_num]
                        
                        if stat == 1: indicator = "🟢"
                        elif stat == 2: indicator = "🔴"
                        elif stat == 3: indicator = "🟣"
                        elif stat == 4: indicator = "✅"
                        else: indicator = "⚪"
                        
                        label = f"{indicator} {q_num + 1}"
                        if q_num == idx: label = f"▶ {q_num + 1}"
                        
                        with row_cols[j]:
                            st.button(label, key=f"nav_{q_num}", on_click=jump_to_question, args=(q_num,), use_container_width=True)

# --- 8. REVIEW / RESULTS UI ---
def render_review_ui():
    idx = st.session_state.current_q_idx
    q_data = st.session_state.active_questions[idx]
    total_q = len(st.session_state.active_questions)
    
    # Calculate regular stats
    correct_count = sum(1 for i, q in enumerate(st.session_state.active_questions) if st.session_state.responses.get(i) == get_correct_answer(q))
    wrong_count = sum(1 for i, q in enumerate(st.session_state.active_questions) if st.session_state.responses.get(i) is not None and st.session_state.responses.get(i) != get_correct_answer(q))
    skipped_count = total_q - correct_count - wrong_count

    # Calculate guessing stats
    total_guessed = sum(1 for v in st.session_state.guesses.values() if v)
    guessed_correct = sum(1 for i, q in enumerate(st.session_state.active_questions) if st.session_state.guesses.get(i) and st.session_state.responses.get(i) == get_correct_answer(q))

    st.markdown("<div class='top-bar-marrow' style='background-color:#1e3c72;'><span>📊 Exam Review Mode</span></div>", unsafe_allow_html=True)
    
    col_main, col_side = st.columns([3.5, 1.5], gap="medium")
    
    with col_main:
        with st.container(height=480, border=True):
            st.markdown(f"<div class='q-no'>Question no : {idx + 1}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='q-text'>{q_data.get('question', '')}</div>", unsafe_allow_html=True)
            
            options = q_data.get('options', [])
            rationale = q_data.get('rationale', 'No rationale provided.')
            
            if not options and 'answerOptions' in q_data:
                for opt in q_data.get('answerOptions', []):
                    options.append(opt.get('text', ''))
                    if opt.get('isCorrect') and 'rationale' in opt:
                        rationale = opt.get('rationale')
            
            correct_ans = get_correct_answer(q_data)
            user_ans = st.session_state.responses.get(idx)
            
            for opt in options:
                if opt == correct_ans and opt == user_ans:
                    st.markdown(f"<div class='opt-correct'>✔️ {opt} <br><small>(Your Answer & Correct)</small></div>", unsafe_allow_html=True)
                elif opt == user_ans:
                    st.markdown(f"<div class='opt-wrong'>❌ {opt} <br><small>(Your Answer - Incorrect)</small></div>", unsafe_allow_html=True)
                elif opt == correct_ans:
                    st.markdown(f"<div class='opt-correct'>👉 {opt} <br><small>(Correct Answer)</small></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='opt-neutral'>{opt}</div>", unsafe_allow_html=True)
                    
            if user_ans is None:
                st.warning("You skipped this question.")
                
            # Show if user guessed this specific question
            if st.session_state.guesses.get(idx):
                st.info("🤔 You marked this question as a guess during the exam.")
                
            st.markdown(f"<div class='rationale-box'><b>Explanation:</b><br>{rationale}</div><br>", unsafe_allow_html=True)
            
        btn_c1, btn_c2, btn_c3 = st.columns([1, 2, 1])
        with btn_c1: st.button("⬅️ Previous", on_click=move_to_prev, use_container_width=True)
        with btn_c2: st.button("Return to Dashboard", on_click=go_to_dashboard, type="primary", use_container_width=True)
        with btn_c3: st.button("Next ➡️", on_click=move_to_next, use_container_width=True)

    with col_side:
        with st.container(height=560, border=True):
            st.markdown(f"""
            <div style='text-align:center; padding:10px; background:#f0f2f6; border-radius:5px; margin-bottom:15px;'>
                <h2 style='margin:0; color:#1e3c72;'>Score: {correct_count} / {total_q}</h2>
                <p style='margin:8px 0 0 0; color:#555; font-size:14px;'>You guessed on <b>{total_guessed}</b> questions.<br>Of those guesses, <b>{guessed_correct}</b> were correct.</p>
            </div>
            <div class='legend-grid'>
                <div>🟩 {correct_count} Correct</div>
                <div>🟥 {wrong_count} Wrong</div>
                <div>⬜ {skipped_count} Skipped</div>
            </div>
            <div class='palette-header'>Review Palette</div>
            """, unsafe_allow_html=True)
            
            cols_per_row = 4
            for i in range(0, total_q, cols_per_row):
                row_cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < total_q:
                        q_num = i + j
                        
                        ans = st.session_state.responses.get(q_num)
                        corr = get_correct_answer(st.session_state.active_questions[q_num])
                        
                        if ans is None: indicator = "⬜"
                        elif ans == corr: indicator = "🟩"
                        else: indicator = "🟥"
                        
                        label = f"{indicator} {q_num + 1}"
                        if q_num == idx: label = f"▶ {q_num + 1}"
                        
                        with row_cols[j]:
                            st.button(label, key=f"rev_nav_{q_num}", on_click=jump_to_question, args=(q_num,), use_container_width=True)

# --- 9. APP ROUTING ---
def main():
    if st.session_state.mode == 'exam':
        render_exam_ui()
    elif st.session_state.mode == 'review':
        render_review_ui()
    else:
        render_dashboard()

if __name__ == "__main__":
    main()
