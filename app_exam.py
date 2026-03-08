import streamlit as st
import json
import os
import requests
import google.generativeai as genai
import PyPDF2

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="INI SS CBT Simulator")

DB_FILE = "local_qbank.json"

# --- 1. DATA MANAGEMENT FUNCTIONS ---
def load_qbank():
    """Loads the question bank from the local JSON file."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_qbank(data):
    """Saves the question bank to the local JSON file."""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- 2. SESSION STATE INITIALIZATION ---
if 'qbank' not in st.session_state:
    st.session_state.qbank = load_qbank()
    
if 'active_questions' not in st.session_state:
    st.session_state.active_questions = []
if 'exam_active' not in st.session_state:
    st.session_state.exam_active = False
if 'show_results' not in st.session_state:
    st.session_state.show_results = False
if 'current_q_idx' not in st.session_state:
    st.session_state.current_q_idx = 0
if 'statuses' not in st.session_state:
    st.session_state.statuses = {} 
if 'responses' not in st.session_state:
    st.session_state.responses = {}

# --- 3. AI GENERATION LOGIC ---
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def generate_questions_from_ai(api_key, topic, pdf_text="", num_q=10):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an expert medical examiner for the INI SS (super-specialty) exam.
    Create {num_q} multiple-choice questions on the topic: "{topic}".
    If context text is provided below, base the questions on that text.
    
    Context Text: {pdf_text[:15000]}
    
    CRITICAL INSTRUCTION: Your response MUST be ONLY a valid JSON array. Do not include any markdown formatting like ```json or ```.
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
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Clean up markdown if the AI includes it by mistake
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        parsed_json = json.loads(raw_text.strip())
        return parsed_json
    except Exception as e:
        st.error(f"Failed to generate questions. Error: {e}")
        return None

# --- 4. EXAM LOGIC FUNCTIONS ---
def start_exam(questions):
    if not questions: return
    st.session_state.active_questions = questions
    st.session_state.exam_active = True
    st.session_state.show_results = False
    st.session_state.current_q_idx = 0
    st.session_state.responses = {}
    st.session_state.statuses = {i: 0 for i in range(len(questions))}
    st.session_state.statuses[0] = 2 # First question visited

def get_current_selection():
    key = f"radio_{st.session_state.current_q_idx}"
    return st.session_state.get(key, st.session_state.responses.get(st.session_state.current_q_idx, None))

def move_to_next():
    total_q = len(st.session_state.active_questions)
    if st.session_state.current_q_idx < total_q - 1:
        st.session_state.current_q_idx += 1
        if st.session_state.statuses[st.session_state.current_q_idx] == 0:
            st.session_state.statuses[st.session_state.current_q_idx] = 2

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
    st.session_state.statuses[idx] = 2 

def jump_to_question(idx):
    curr = st.session_state.current_q_idx
    if st.session_state.statuses[curr] == 0:
        st.session_state.statuses[curr] = 2
    st.session_state.current_q_idx = idx
    if st.session_state.statuses[idx] == 0:
        st.session_state.statuses[idx] = 2

def submit_exam():
    st.session_state.exam_active = False
    st.session_state.show_results = True

# --- 5. CSS STYLING (MARROW CLONE) ---
st.markdown("""
<style>
    /* Hide main Streamlit menu and footer for cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Top Black Bar */
    .top-bar-marrow {
        background-color: #212b36;
        color: white;
        padding: 10px 20px;
        font-size: 14px;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        border-radius: 4px 4px 0 0;
    }
    
    /* Main Layout Containers */
    .main-panel { background-color: #f4f6f8; padding: 20px; min-height: 500px; border: 1px solid #ddd; border-top: none;}
    .right-panel { background-color: #ffffff; padding: 15px; border: 1px solid #ddd; height: 100%;}
    
    /* Typography & Headers */
    .timer-text { color: #d32f2f; font-weight: bold; text-align: right; margin-bottom: 10px;}
    .q-type-bar { color: #d32f2f; font-weight: bold; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 15px;}
    .q-no { font-weight: bold; margin-bottom: 10px; color: #333;}
    .q-text { font-size: 16px; color: #333; margin-bottom: 20px; line-height: 1.5;}
    
    /* Profile Box */
    .profile-box { display: flex; align-items: center; background-color: #f9f9f9; padding: 10px; border: 1px solid #ddd; margin-bottom: 15px;}
    .profile-icon { font-size: 40px; color: #ccc; margin-right: 15px;}
    
    /* Status Legend Custom Shapes */
    .legend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px; margin-bottom: 20px;}
    .status-badge { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 25px; color: white; font-weight: bold; margin-right: 8px;}
    
    .bg-green { background-color: #4caf50; border-radius: 3px; border: 1px solid #388e3c;}
    .bg-red { background-color: #e53935; border-radius: 3px; border: 1px solid #b71c1c;}
    .bg-grey { background-color: #e0e0e0; color: #333; border-radius: 3px; border: 1px solid #bdbdbd;}
    .bg-purple { background-color: #8e24aa; border-radius: 50%; width: 28px; height: 28px;}
    .bg-purple-check { background-color: #8e24aa; border-radius: 50%; width: 28px; height: 28px; position: relative;}
    .bg-purple-check::after { content: '✔'; position: absolute; bottom: -2px; right: -2px; font-size: 10px; background: #4caf50; color: white; border-radius: 50%; width: 14px; height: 14px; display: flex; align-items: center; justify-content: center;}
    
    /* Palette Header */
    .palette-header { background-color: #2167a6; color: white; padding: 8px; font-weight: bold; text-align: left; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 6. VIEWS ---
def render_dashboard():
    st.title("🩺 INI SS Generator & Simulator")
    
    # API KEY INPUT
    api_key = st.sidebar.text_input("Enter Google Gemini API Key", type="password")
    st.sidebar.markdown("[Get API Key here](https://aistudio.google.com/app/apikey)")
    
    tab1, tab2, tab3 = st.tabs(["🧠 Generate from Topic", "📄 Generate from PDF", "📥 Import/Start Pre-made"])
    
    with tab1:
        st.subheader("Generate Exam by Topic")
        topic = st.text_input("Enter Topic (e.g., Rheumatoid Arthritis, Vasculitis)")
        num_q = st.slider("Number of Questions", 5, 50, 10)
        if st.button("Generate & Start Exam (Topic)"):
            if not api_key: st.error("Please enter API Key in sidebar!")
            elif not topic: st.error("Please enter a topic!")
            else:
                with st.spinner("AI is generating your exam..."):
                    qs = generate_questions_from_ai(api_key, topic, num_q=num_q)
                    if qs: 
                        st.session_state.qbank.extend(qs)
                        save_qbank(st.session_state.qbank)
                        start_exam(qs)
                        st.rerun()
                    
    with tab2:
        st.subheader("Generate Exam from PDF Document")
        uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
        pdf_topic = st.text_input("Specific focus for these PDF questions (Optional)")
        num_q_pdf = st.slider("Number of Questions (PDF)", 5, 50, 10)
        if st.button("Generate & Start Exam (PDF)"):
            if not api_key: st.error("Please enter API Key in sidebar!")
            elif not uploaded_file: st.error("Please upload a PDF!")
            else:
                with st.spinner("Reading PDF and generating exam..."):
                    text = extract_text_from_pdf(uploaded_file)
                    topic_str = pdf_topic if pdf_topic else "the provided document"
                    qs = generate_questions_from_ai(api_key, topic_str, pdf_text=text, num_q=num_q_pdf)
                    if qs: 
                        st.session_state.qbank.extend(qs)
                        save_qbank(st.session_state.qbank)
                        start_exam(qs)
                        st.rerun()
                    
    with tab3:
        st.subheader("Start Exam from Question Bank")
        if not st.session_state.qbank:
            st.warning("Your question bank is empty. Generate some questions first, or paste JSON below.")
        else:
            if st.button(f"Start Exam with All Saved Questions ({len(st.session_state.qbank)})", type="primary"):
                start_exam(st.session_state.qbank)
                st.rerun()
            if st.button("Clear Entire Database"):
                st.session_state.qbank = []
                save_qbank([])
                st.rerun()
                
        st.divider()
        st.info("Paste a JSON code block from a previous chat to add it to your bank.")
        raw_json = st.text_area("Paste JSON here", height=150)
        if st.button("Import JSON & Start"):
            try:
                qs = json.loads(raw_json)
                st.session_state.qbank.extend(qs)
                save_qbank(st.session_state.qbank)
                start_exam(qs)
                st.rerun()
            except Exception as e:
                st.error("Invalid JSON format. Please check the code.")

def render_exam_ui():
    idx = st.session_state.current_q_idx
    q_data = st.session_state.active_questions[idx]
    total_q = len(st.session_state.active_questions)
    
    # Calculate Stats
    stats = {0:0, 1:0, 2:0, 3:0, 4:0}
    for s in st.session_state.statuses.values(): 
        stats[s] = stats.get(s, 0) + 1
    
    st.markdown("""
        <div class='top-bar-marrow'>
            <span style='margin-right:20px;'>📄 Question Paper</span>
            <span>ℹ️ Instructions</span>
        </div>
    """, unsafe_allow_html=True)
    
    col_main, col_side = st.columns([3, 1], gap="small")
    
    with col_main:
        st.markdown("<div class='main-panel'>", unsafe_allow_html=True)
        st.markdown("<div class='timer-text'>Time Left: 00:32:04</div>", unsafe_allow_html=True)
        st.markdown("<div class='q-type-bar'>Question type : MCQ</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-no'>Question no : {idx + 1}</div>", unsafe_allow_html=True)
        
        # Display Question text
        q_text = q_data.get('question', '')
        st.markdown(f"<div class='q-text'>{q_text}</div>", unsafe_allow_html=True)
        
        # Handle options format from JSON
        options = q_data.get('options', [])
        if not options and 'answerOptions' in q_data:
            options = [opt.get('text', '') for opt in q_data.get('answerOptions', [])]
            
        current_ans = st.session_state.responses.get(idx, None)
        default_idx = options.index(current_ans) if current_ans in options else None
        
        radio_key = f"radio_{idx}"
        st.radio("Options", options, index=default_idx, key=radio_key, label_visibility="collapsed")
        
        st.markdown("<br><label style='color:#555; font-size:14px;'><input type='checkbox'> I am guessing this ℹ️</label><hr>", unsafe_allow_html=True)
        
        # Buttons Layout
        btn_col1, btn_col2, btn_spacer, btn_col3, btn_col4 = st.columns([2.5, 2, 3, 2, 2])
        with btn_col1: 
            st.button("Mark for Review & Next", on_click=mark_and_next, use_container_width=True)
        with btn_col2: 
            st.button("Clear Response", on_click=clear_response, use_container_width=True)
        with btn_col3: 
            st.button("Save and Next", on_click=save_and_next, type="primary", use_container_width=True)
        with btn_col4: 
            st.button("Submit", on_click=submit_exam, type="primary", use_container_width=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

    with col_side:
        st.markdown("<div class='right-panel'>", unsafe_allow_html=True)
        
        # Profile Block
        st.markdown("""
        <div class='profile-box'>
            <div class='profile-icon'>👤</div>
            <div style='line-height:1.2;'>
                <b style='color:#444;'>Candidate Name</b><br>
                <span style='color:gray; font-size:12px;'>INI SS Aspirant</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Status Legend Grid
        st.markdown(f"""
        <div class='legend-grid'>
            <div><span class='status-badge bg-green'>{stats[1]}</span> Answered</div>
            <div><span class='status-badge bg-red'>{stats[2]}</span> Not Answered</div>
            <div><span class='status-badge bg-grey'>{stats[0]}</span> Not Visited</div>
            <div><span class='status-badge bg-purple'>{stats[3]}</span> Marked</div>
        </div>
        <div style='font-size:12px; color:#555; margin-bottom:15px; border-bottom:1px solid #ddd; padding-bottom:10px;'>
            <span class='status-badge bg-purple-check'>{stats[4]}</span> Answered & Marked for Review (will NOT be considered for evaluation)
        </div>
        <div class='palette-header'>All questions</div>
        """, unsafe_allow_html=True)
        
        # Question Palette Grid
        cols_per_row = 4
        for i in range(0, total_q, cols_per_row):
            row_cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < total_q:
                    q_num = i + j
                    stat = st.session_state.statuses[q_num]
                    
                    # Emojis map closest to the Marrow UI colors since Streamlit buttons can't take direct background-color CSS easily
                    if stat == 1: indicator = "🟩"
                    elif stat == 2: indicator = "🟥"
                    elif stat == 3: indicator = "🟪"
                    elif stat == 4: indicator = "✅"
                    else: indicator = "⬜"
                    
                    label = f"{indicator} {q_num + 1}"
                    if q_num == idx: label = f"▶ {q_num + 1}"
                    
                    with row_cols[j]:
                        st.button(label, key=f"nav_{q_num}", on_click=jump_to_question, args=(q_num,), use_container_width=True)
                        
        st.markdown("</div>", unsafe_allow_html=True)

def render_results():
    st.title("📊 Exam Results & Analysis")
    st.balloons()
    
    score = 0
    for i, q in enumerate(st.session_state.active_questions):
        correct = q.get('correct_answer')
        if not correct and 'answerOptions' in q:
            for opt in q.get('answerOptions', []):
                if opt.get('isCorrect'): correct = opt.get('text')
        if st.session_state.responses.get(i) == correct:
            score += 1
            
    st.header(f"Your Score: {score} / {len(st.session_state.active_questions)}")
    
    if st.button("Return to Dashboard"):
        st.session_state.exam_active = False
        st.session_state.show_results = False
        st.rerun()
        
    st.divider()
    for i, q in enumerate(st.session_state.active_questions):
        correct = q.get('correct_answer')
        rationale = q.get('rationale', 'No rationale provided.')
        
        if not correct and 'answerOptions' in q:
            for opt in q.get('answerOptions', []):
                if opt.get('isCorrect'):
                    correct = opt.get('text')
                    rationale = opt.get('rationale', rationale)
                    
        user_ans = st.session_state.responses.get(i, "Not Answered")
        with st.expander(f"Q{i+1}: {q.get('question', '')[:60]}..."):
            st.write(f"**Question:** {q.get('question', '')}")
            if user_ans == correct: st.success(f"**Your Answer:** {user_ans} (Correct)")
            elif user_ans == "Not Answered":
                st.warning("**Your Answer:** Not Answered")
                st.info(f"**Correct Answer:** {correct}")
            else:
                st.error(f"**Your Answer:** {user_ans} (Incorrect)")
                st.success(f"**Correct Answer:** {correct}")
            st.write(f"**Rationale:** {rationale}")

def main():
    if st.session_state.show_results: render_results()
    elif st.session_state.exam_active: render_exam_ui()
    else: render_dashboard()

if __name__ == "__main__":
    main()
