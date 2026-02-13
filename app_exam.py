import streamlit as st
import google.generativeai as genai
import json
import time
import datetime
import PyPDF2

# --- CONFIG ---
try:
    # Safe Cloud Secret
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    # Placeholder for local testing
    api_key = "PASTE_YOUR_KEY_HERE"

genai.configure(api_key=api_key)

st.set_page_config(page_title="MEDICAL EXAM SIMULATOR", layout="wide")

# --- UI ENGINE: WHITE THEME & BLACK TEXT ---
if 'font_size' not in st.session_state: st.session_state.font_size = 20

def apply_exam_ui():
    f_size = st.session_state.font_size
    st.markdown(f"""
        <style>
        .stApp {{ background-color: #ffffff !important; color: #000000 !important; }}
        
        /* Force Solid Black Text and Disable Fading */
        p, div, label, span, h1, h2, h3, h4, .stMarkdown, .stRadio label, .stButton p {{
            font-size: {f_size}px !important;
            color: #000000 !important;
            opacity: 1.0 !important;
            filter: none !important;
        }}
        
        /* Sidebar Question Palette */
        [data-testid="stSidebar"] {{
            background-color: #f8f9fa !important;
            border-left: 2px solid #dee2e6 !important;
        }}
        
        /* Professional Buttons */
        .stButton>button {{
            border: 1px solid #000000 !important;
            color: #000000 !important;
            background-color: #ffffff !important;
            font-weight: bold !important;
        }}
        </style>
    """, unsafe_allow_html=True)

# --- CORE FUNCTIONS ---
def extract_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "".join([p.extract_text() for p in reader.pages])

def generate_exam_data(topic, num, difficulty, context=None):
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    prompt = f"Create a {difficulty} medical exam with {num} questions on {topic}. JSON ONLY."
    if context: prompt += f"\nContext: {context[:12000]}"
    prompt += "\nFormat: [{\"question\":\"...\",\"options\":{\"A\":\"..\",\"B\":\"..\",\"C\":\"..\",\"D\":\"..\"},\"correct\":\"A\",\"explanation\":\"...\"}]"
    
    response = model.generate_content(prompt)
    txt = response.text
    start, end = txt.find('['), txt.rfind(']') + 1
    return json.loads(txt[start:end])

# --- SESSION STATE ---
if 'exam_active' not in st.session_state: st.session_state.exam_active = False
if 'exam_data' not in st.session_state: st.session_state.exam_data = []
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'current_q' not in st.session_state: st.session_state.current_q = 0
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'total_seconds' not in st.session_state: st.session_state.total_seconds = 0
if 'marked' not in st.session_state: st.session_state.marked = set()
if 'submitted' not in st.session_state: st.session_state.submitted = False

apply_exam_ui()

# --- TOP BAR: FONT CONTROLS ---
c_title, c_minus, c_plus = st.columns([8, 1, 1])
with c_minus:
    if st.button("➖"): 
        st.session_state.font_size = max(12, st.session_state.font_size - 2)
        st.rerun()
with c_plus:
    if st.button("➕"): 
        st.session_state.font_size = min(40, st.session_state.font_size + 2)
        st.rerun()

# --- APP FLOW ---
if not st.session_state.exam_active and not st.session_state.submitted:
    st.title("📝 Exam Setup")
    topic = st.text_input("Exam Topic (e.g. Harrison Cardiology)")
    source = st.radio("Source", ["Knowledge", "PDF Upload"], horizontal=True)
    pdf_text = None
    if source == "PDF Upload":
        f = st.file_uploader("Upload PDF", type='pdf')
        if f: pdf_text = extract_pdf(f)
    
    q_count = st.selectbox("Number of Questions", [20, 40, 60])
    timer_map = {20: 25*60, 40: 45*60, 60: 70*60}
    
    if st.button("Start Exam", type="primary"):
        with st.spinner("Generating Exam..."):
            data = generate_exam_data(topic, q_count, "Hard", pdf_text)
            if data:
                st.session_state.exam_data = data
                st.session_state.exam_active = True
                st.session_state.total_seconds = timer_map[q_count]
                st.session_state.start_time = time.time()
                st.rerun()

elif st.session_state.exam_active:
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.total_seconds - elapsed
    
    if remaining <= 0:
        st.session_state.exam_active = False
        st.session_state.submitted = True
        st.rerun()

    mins, secs = divmod(int(remaining), 60)
    
    with st.sidebar:
        st.markdown(f"### ⏱️ {mins:02d}:{secs:02d}")
        st.progress(max(0.0, remaining / st.session_state.total_seconds))
        st.divider()
        st.markdown("### Question Palette")
        cols = st.columns(4)
        for i in range(len(st.session_state.exam_data)):
            label = f"{i+1}"
            if i in st.session_state.marked: label = f"⭐{i+1}"
            if cols[i % 4].button(label, key=f"p_{i}"):
                st.session_state.current_q = i
                st.rerun()
        st.divider()
        if st.button("🏁 SUBMIT TEST", type="primary"):
            st.session_state.exam_active = False
            st.session_state.submitted = True
            st.rerun()

    idx = st.session_state.current_q
    q = st.session_state.exam_data[idx]
    
    st.markdown(f"### Question {idx + 1}")
    st.write(q['question'])
    
    opts = list(q['options'].keys())
    prev_ans = st.session_state.user_answers.get(idx)
    
    ans = st.radio("Choose:", opts, 
                   format_func=lambda x: f"{x}: {q['options'][x]}",
                   index=opts.index(prev_ans) if prev_ans else None,
                   key=f"ex_r_{idx}")
    
    st.divider()
    b1, b2, b3 = st.columns([1, 1, 1])
    if b1.button("⬅ Previous") and idx > 0:
        st.session_state.current_q -= 1
        st.rerun()
    if b2.button("⭐ Mark for Review"):
        st.session_state.marked.add(idx)
        st.rerun()
    if b3.button("💾 Save & Next ➡"):
        if ans: st.session_state.user_answers[idx] = ans
        if idx < len(st.session_state.exam_data) - 1:
            st.session_state.current_q += 1
        st.rerun()

elif st.session_state.submitted:
    st.title("📊 Performance Review")
    
    total = len(st.session_state.exam_data)
    correct = sum(1 for i, q in enumerate(st.session_state.exam_data) if st.session_state.user_answers.get(i) == q['correct'])
    incorrect = len(st.session_state.user_answers) - correct
    skipped = total - len(st.session_state.user_answers)
    
    # Negative Marking Calculation (+4 for Correct, -1 for Wrong)
    raw_score = (correct * 4) - (incorrect * 1)
    
    st.write(f"**Score:** {correct}/{total} | **Wrong:** {incorrect} | **Skipped:** {skipped}")
    st.info(f"Final Score (with -1 negative marking): **{raw_score}**")

    with st.sidebar:
        st.markdown("### Review Palette")
        cols = st.columns(4)
        for i in range(total):
            ans = st.session_state.user_answers.get(i)
            # Logic for palette colors in review
            btn_color = "✅" if ans == st.session_state.exam_data[i]['correct'] else "❌"
            if cols[i % 4].button(f"{btn_color}{i+1}", key=f"rev_{i}"):
                st.session_state.current_q = i
                st.rerun()
        if st.button("New Exam"):
            st.session_state.exam_active = False
            st.session_state.submitted = False
            st.session_state.user_answers = {}
            st.session_state.marked = set()
            st.rerun()

    idx = st.session_state.current_q
    q = st.session_state.exam_data[idx]
    ans = st.session_state.user_answers.get(idx)
    
    st.markdown(f"#### Q{idx+1} Review")
    st.write(q['question'])
    for k, v in q['options'].items():
        if k == q['correct']: st.success(f"✅ {k}: {v}")
        elif k == ans: st.error(f"❌ {k}: {v} (Your Selection)")
        else: st.write(f"{k}: {v}")
    st.info(f"**Explanation:** {q['explanation']}")