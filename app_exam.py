import streamlit as st
import google.generativeai as genai
import json
import time
import datetime
import os
import PyPDF2

# --- CONFIGURATION ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    api_key = "PASTE_YOUR_KEY_HERE"

genai.configure(api_key=api_key)
HISTORY_FILE = "exam_history.json"

st.set_page_config(page_title="MEDICAL PG EXAM SIMULATOR", layout="wide")

# --- UI ENGINE: WHITE THEME & BLACK TEXT ---
if 'font_size' not in st.session_state: st.session_state.font_size = 20

def apply_exam_ui():
    f_size = st.session_state.font_size
    st.markdown(f"""
        <style>
        /* 1. FORCE MAIN BACKGROUND WHITE */
        .stApp {{ background-color: #ffffff !important; color: #000000 !important; }}
        
        /* 2. FORCE TEXT BLACK & VISIBLE */
        p, div, label, span, h1, h2, h3, h4, .stMarkdown, .stRadio label, li {{
            font-size: {f_size}px !important;
            color: #000000 !important;
            opacity: 1.0 !important;
        }}

        /* 3. WHITE INPUT BOXES & DROPDOWNS */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
        }}
        
        /* 4. PALETTE GRID STYLING */
        .stButton button {{
            width: 100%;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid #ccc;
            background-color: #f0f2f6;
            color: black;
        }}
        
        /* 5. CURRENT QUESTION HIGHLIGHT (Blue Border) */
        div[data-testid="column"] {{
            border-radius: 10px;
            padding: 10px;
        }}
        
        /* 6. RADIO BUTTON SPACING */
        .stRadio div {{ margin-bottom: 10px; }}
        </style>
    """, unsafe_allow_html=True)

# --- SMART MODEL DETECTOR ---
@st.cache_data
def get_working_model_name():
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name: return m.name
        return "models/gemini-pro"
    except: return "models/gemini-1.5-flash"

# --- HISTORY & PDF FUNCTIONS ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: return json.load(f)
        except: return []
    return []

def save_history(topic, score, total, questions, answers):
    history = load_history()
    entry = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic": topic,
        "score": f"{score}/{total}",
        "data": questions,
        "user_answers": answers
    }
    history.insert(0, entry)
    try:
        with open(HISTORY_FILE, "w") as f: json.dump(history, f)
    except: pass
    return history

def extract_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "".join([p.extract_text() for p in reader.pages])

# --- AI GENERATION (COMPLEX QUESTIONS) ---
def generate_exam_data(topic, num, difficulty, context=None):
    model_name = get_working_model_name()
    model = genai.GenerativeModel(model_name)
    
    # COMPLEX PROMPT FOR MARROW-STYLE QUESTIONS
    prompt = f"""
    Act as a Medical Exam Setter (NEET PG / USMLE Step 2 Level). 
    Create a {difficulty} exam with {num} questions on {topic}.
    
    CRITICAL: You must generate a mix of these 4 types:
    1. Clinical Vignettes (Long patient history, labs, diagnosis).
    2. Match the Following (Present the columns clearly in the question text).
    3. Sequencing/Ordering (e.g., "Correct order of steps").
    4. Statement Analysis ("Which statement is most accurate?").
    
    Provide an 'extra_edge' (High Yield Pearl) for every question.
    Output VALID JSON ONLY.
    """
    if context: prompt += f"\nContext: {context[:15000]}"
    prompt += "\nFormat: [{\"question\":\"(Type: Vignette/Match/etc) Question Text...\",\"options\":{\"A\":\"..\",\"B\":\"..\",\"C\":\"..\",\"D\":\"..\"},\"correct\":\"A\",\"explanation\":\"...\",\"extra_edge\":\"...\"}]"
    
    try:
        response = model.generate_content(prompt)
        txt = response.text
        start, end = txt.find('['), txt.rfind(']') + 1
        return json.loads(txt[start:end])
    except Exception as e:
        st.error(f"AI Error: {e}"); return []

def create_report(topic, score, total, questions, answers):
    report = f"🎓 MEDICAL EXAM REPORT\nTopic: {topic}\nScore: {score}/{total}\n" + "="*50 + "\n\n"
    for i, q in enumerate(questions):
        ans = answers.get(i) or answers.get(str(i))
        status = "✅ CORRECT" if ans == q['correct'] else f"❌ WRONG (Your Answer: {ans})"
        report += f"Q{i+1}: {q['question']}\nSTATUS: {status}\n"
        report += f"OPTIONS:\n" + "\n".join([f" {'->' if k==q['correct'] else '  '} {k}: {v}" for k,v in q['options'].items()])
        report += f"\n\nEXPLANATION: {q.get('explanation', 'N/A')}\nEXTRA EDGE: {q.get('extra_edge', 'N/A')}\n" + "="*50 + "\n\n" 
    return report

# --- LIVE TIMER ---
def display_live_timer(remaining_seconds):
    mins, secs = divmod(int(remaining_seconds), 60)
    time_str = f"{mins:02d}:{secs:02d}"
    st.markdown(f"""
        <div style="text-align: center; font-size: 24px; font-weight: bold; color: #d90429; background-color: #fff; border: 2px solid #d90429; border-radius: 8px; padding: 5px; margin-bottom: 10px;">
            ⏱️ <span id="timer_box">{time_str}</span>
        </div>
        <script>
        (function() {{
            var start = {remaining_seconds};
            var display = document.getElementById("timer_box");
            var timer = setInterval(function() {{
                if (start <= 0) {{ clearInterval(timer); display.textContent = "00:00"; }} 
                else {{
                    start--;
                    var m = Math.floor(start / 60);
                    var s = Math.floor(start % 60);
                    m = m < 10 ? "0" + m : m;
                    s = s < 10 ? "0" + s : s;
                    display.textContent = m + ":" + s;
                }}
            }}, 1000);
        }})();
        </script>
    """, unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if 'exam_active' not in st.session_state: st.session_state.exam_active = False
if 'exam_data' not in st.session_state: st.session_state.exam_data = []
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'current_q' not in st.session_state: st.session_state.current_q = 0
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'total_seconds' not in st.session_state: st.session_state.total_seconds = 0
if 'marked' not in st.session_state: st.session_state.marked = set()
if 'submitted' not in st.session_state: st.session_state.submitted = False
if 'topic' not in st.session_state: st.session_state.topic = "General"
if 'history' not in st.session_state: st.session_state.history = load_history()

apply_exam_ui()

# --- TOP BAR: FONT SIZE ---
c_minus, c_plus = st.columns([1, 1])
with c_minus:
    if st.button("A-"): st.session_state.font_size = max(14, st.session_state.font_size - 2); st.rerun()
with c_plus:
    if st.button("A+"): st.session_state.font_size = min(30, st.session_state.font_size + 2); st.rerun()

# --- 1. SETUP SCREEN ---
if not st.session_state.exam_active and not st.session_state.submitted:
    st.title("Medical Exam Simulator Pro")
    
    col_setup, col_hist = st.columns([2, 1])
    
    with col_setup:
        topic = st.text_input("Enter Exam Topic (e.g. Ophthalmology Clinical Cases)")
        source = st.radio("Question Source:", ["AI Knowledge", "Upload PDF"], horizontal=True)
        pdf_text = None
        if source == "Upload PDF":
            f = st.file_uploader("Upload Medical PDF", type='pdf')
            if f: pdf_text = extract_pdf(f)
        q_count = st.selectbox("Number of Questions:", [20, 40, 60])
        timer_map = {20: 25*60, 40: 45*60, 60: 70*60}
        
        st.divider()
        if st.button("🚀 Start Exam", type="primary"):
            with st.spinner("Generating High-Yield Questions..."):
                st.session_state.topic = topic
                data = generate_exam_data(topic, q_count, "Hard", pdf_text)
                if data:
                    st.session_state.exam_data = data
                    st.session_state.exam_active = True
                    st.session_state.total_seconds = timer_map[q_count]
                    st.session_state.start_time = time.time()
                    st.rerun()

    with col_hist:
        st.subheader("📜 History")
        if st.session_state.history:
            for i, item in enumerate(st.session_state.history):
                if st.button(f"{item['topic']} ({item['score']})", key=f"hist_{i}"):
                    st.session_state.exam_data = item['data']
                    st.session_state.user_answers = item.get('user_answers', {})
                    st.session_state.topic = item['topic']
                    st.session_state.exam_active = False
                    st.session_state.submitted = True
                    st.session_state.current_q = 0
                    st.rerun()

# --- 2. EXAM INTERFACE (SPLIT SCREEN) ---
elif st.session_state.exam_active:
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.total_seconds - elapsed
    
    if remaining <= 0:
        st.session_state.exam_active = False
        st.session_state.submitted = True
        st.rerun()

    # LAYOUT: 75% Question | 25% Palette
    col_q, col_p = st.columns([3, 1])
    
    # --- RIGHT COLUMN (PALETTE & TIMER) ---
    with col_p:
        display_live_timer(remaining)
        st.markdown("**Question Palette**")
        
        # Grid Logic
        cols = st.columns(4)
        for i in range(len(st.session_state.exam_data)):
            # Determine Status Symbol
            if i == st.session_state.current_q: status = "🔵" # Current
            elif i in st.session_state.marked and i in st.session_state.user_answers: status = "🟣✅" # Marked & Answered
            elif i in st.session_state.marked: status = "🟣" # Marked Review
            elif i in st.session_state.user_answers: status = "✅" # Answered
            else: status = "⬜" # Not Visited/Answered
            
            if cols[i % 4].button(f"{status} {i+1}", key=f"nav_{i}"):
                st.session_state.current_q = i
                st.rerun()
        
        st.divider()
        if st.button("🟥 SUBMIT EXAM", type="primary"):
            st.session_state.exam_active = False
            st.session_state.submitted = True
            st.rerun()

    # --- LEFT COLUMN (QUESTION) ---
    with col_q:
        idx = st.session_state.current_q
        q = st.session_state.exam_data[idx]
        
        st.markdown(f"### Q{idx + 1}")
        st.markdown(f"**{q['question']}**")
        
        opts = list(q['options'].keys())
        prev_ans = st.session_state.user_answers.get(idx)
        
        # Radio Selection
        ans = st.radio("Select Option:", opts, 
                       format_func=lambda x: f"{x}: {q['options'][x]}",
                       index=opts.index(prev_ans) if prev_ans else None,
                       key=f"rad_{idx}")
        
        st.write("---")
        
        # ACTION BUTTONS
        b1, b2, b3, b4 = st.columns([1.5, 1.5, 2, 2])
        
        if b1.button("⬅ Previous") and idx > 0:
            st.session_state.current_q -= 1
            st.rerun()
            
        if b2.button("Clear Response"):
            if idx in st.session_state.user_answers:
                del st.session_state.user_answers[idx]
            st.rerun()
            
        if b3.button("🟣 Mark & Next"):
            if idx not in st.session_state.marked: st.session_state.marked.add(idx)
            if idx < len(st.session_state.exam_data) - 1: st.session_state.current_q += 1
            st.rerun()
            
        if b4.button("💾 Save & Next"):
            if ans: st.session_state.user_answers[idx] = ans
            if idx in st.session_state.marked: st.session_state.marked.remove(idx) # Unmark if saved
            if idx < len(st.session_state.exam_data) - 1: st.session_state.current_q += 1
            st.rerun()

# --- 3. REVIEW SCREEN ---
elif st.session_state.submitted:
    st.title("📊 Performance Analysis")
    
    # Save History ONCE
    if 'history_saved' not in st.session_state:
        total = len(st.session_state.exam_data)
        correct = sum(1 for i, q in enumerate(st.session_state.exam_data) if st.session_state.user_answers.get(i) == q['correct'])
        raw_score = (correct * 4) - ((len(st.session_state.user_answers) - correct) * 1)
        st.session_state.history = save_history(st.session_state.topic, raw_score, total * 4, st.session_state.exam_data, st.session_state.user_answers)
        st.session_state.history_saved = True

    # Stats
    total = len(st.session_state.exam_data)
    correct = sum(1 for i, q in enumerate(st.session_state.exam_data) if st.session_state.user_answers.get(i) == q['correct'])
    incorrect = len(st.session_state.user_answers) - correct
    skipped = total - len(st.session_state.user_answers)
    raw_score = (correct * 4) - (incorrect * 1)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score (+4/-1)", raw_score); c2.metric("Correct", correct)
    c3.metric("Wrong", incorrect); c4.metric("Skipped", skipped)
    
    report_text = create_report(st.session_state.topic, raw_score, total * 4, st.session_state.exam_data, st.session_state.user_answers)
    st.download_button("📥 Download Report", report_text, file_name=f"Exam_{st.session_state.topic}.txt")
    st.divider()

    col_res, col_key = st.columns([3, 1])
    
    # REVIEW PALETTE
    with col_key:
        st.markdown("**Answer Key**")
        cols = st.columns(4)
        for i in range(total):
            user_a = st.session_state.user_answers.get(i)
            real_a = st.session_state.exam_data[i]['correct']
            btn_lbl = "✅" if user_a == real_a else "❌"
            if user_a is None: btn_lbl = "⚪"
            if cols[i % 4].button(f"{btn_lbl}{i+1}", key=f"res_{i}"):
                st.session_state.current_q = i
                st.rerun()
        
        st.divider()
        if st.button("Start New Exam"):
            for k in list(st.session_state.keys()):
                if k != 'font_size' and k != 'history': del st.session_state[k]
            st.rerun()

    # QUESTION REVIEW
    with col_res:
        idx = st.session_state.current_q
        q = st.session_state.exam_data[idx]
        user_a = st.session_state.user_answers.get(idx)
        real_a = q['correct']
        
        st.markdown(f"### Q{idx+1}")
        st.markdown(f"**{q['question']}**")
        for opt, txt in q['options'].items():
            if opt == real_a: st.success(f"✅ {opt}: {txt} (Correct Answer)")
            elif opt == user_a and opt != real_a: st.error(f"❌ {opt}: {txt} (Your Answer)")
            else: st.write(f"{opt}: {txt}")
        
        st.info(f"**Explanation:** {q['explanation']}")
        if q.get('extra_edge') and q.get('extra_edge') != "N/A":
            st.warning(f"**⚡ Extra Edge:** {q.get('extra_edge')}")
