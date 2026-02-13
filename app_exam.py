import streamlit as st
import google.generativeai as genai
import json
import time
import datetime
import PyPDF2

# --- CONFIGURATION ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    api_key = "PASTE_YOUR_KEY_HERE"

genai.configure(api_key=api_key)

st.set_page_config(page_title="MEDICAL EXAM SIMULATOR", layout="wide")

# --- UI ENGINE: FORCE WHITE THEME & BLACK TEXT ---
if 'font_size' not in st.session_state: st.session_state.font_size = 20

def apply_exam_ui():
    f_size = st.session_state.font_size
    st.markdown(f"""
        <style>
        /* 1. FORCE MAIN BACKGROUND WHITE */
        .stApp {{
            background-color: #ffffff !important;
            color: #000000 !important;
        }}
        
        /* 2. FORCE TEXT TO BE BLACK AND VISIBLE */
        p, div, label, span, h1, h2, h3, h4, .stMarkdown, .stRadio label {{
            font-size: {f_size}px !important;
            color: #000000 !important;
            opacity: 1.0 !important;
        }}

        /* 3. CRITICAL FIX: FORCE INPUT BOXES TO BE WHITE */
        .stTextInput input {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
        }}
        
        div[data-baseweb="select"] > div {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
        }}
        
        /* Dropdown Menu Options */
        ul[data-baseweb="menu"] {{
            background-color: #ffffff !important;
        }}
        li[data-baseweb="option"] {{
            color: #000000 !important;
        }}

        /* 4. SIDEBAR & PALETTE */
        [data-testid="stSidebar"] {{
            background-color: #f0f2f6 !important;
            border-right: 1px solid #cccccc !important;
        }}

        /* 5. BUTTONS */
        .stButton>button {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
            font-weight: bold !important;
        }}
        </style>
    """, unsafe_allow_html=True)

# --- SMART MODEL DETECTOR (PREVENTS CRASHES) ---
@st.cache_data
def get_working_model_name():
    try:
        # Ask Google which models are available
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name: return m.name
        return "models/gemini-pro" # Fallback
    except:
        return "models/gemini-1.5-flash"

# --- CORE FUNCTIONS ---
def extract_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "".join([p.extract_text() for p in reader.pages])

def generate_exam_data(topic, num, difficulty, context=None):
    # Use the auto-detected model
    model_name = get_working_model_name()
    model = genai.GenerativeModel(model_name)
    
    prompt = f"Create a {difficulty} medical exam with {num} questions on {topic}. JSON ONLY."
    if context: prompt += f"\nContext: {context[:12000]}"
    prompt += "\nFormat: [{\"question\":\"...\",\"options\":{\"A\":\"..\",\"B\":\"..\",\"C\":\"..\",\"D\":\"..\"},\"correct\":\"A\",\"explanation\":\"...\"}]"
    
    try:
        response = model.generate_content(prompt)
        txt = response.text
        start, end = txt.find('['), txt.rfind(']') + 1
        return json.loads(txt[start:end])
    except Exception as e:
        st.error(f"AI Error: {e}")
        return []

# --- STATE MANAGEMENT ---
if 'exam_active' not in st.session_state: st.session_state.exam_active = False
if 'exam_data' not in st.session_state: st.session_state.exam_data = []
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'current_q' not in st.session_state: st.session_state.current_q = 0
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'total_seconds' not in st.session_state: st.session_state.total_seconds = 0
if 'marked' not in st.session_state: st.session_state.marked = set()
if 'submitted' not in st.session_state: st.session_state.submitted = False

apply_exam_ui()

# --- TOP BAR: FONT SIZE ---
c_minus, c_plus = st.columns([1, 1])
with c_minus:
    if st.button("A-"): 
        st.session_state.font_size = max(14, st.session_state.font_size - 2)
        st.rerun()
with c_plus:
    if st.button("A+"): 
        st.session_state.font_size = min(30, st.session_state.font_size + 2)
        st.rerun()

# --- 1. SETUP SCREEN ---
if not st.session_state.exam_active and not st.session_state.submitted:
    st.title("📝 New Exam Setup")
    
    topic = st.text_input("Enter Exam Topic (e.g. Neurology)")
    source = st.radio("Question Source:", ["AI Knowledge", "Upload PDF"], horizontal=True)
    pdf_text = None
    if source == "Upload PDF":
        f = st.file_uploader("Upload Medical PDF", type='pdf')
        if f: pdf_text = extract_pdf(f)
    
    q_count = st.selectbox("Number of Questions:", [20, 40, 60])
    timer_map = {20: 25*60, 40: 45*60, 60: 70*60}
    
    st.divider()
    if st.button("🚀 Start Exam", type="primary"):
        with st.spinner("Generating Exam..."):
            data = generate_exam_data(topic, q_count, "Hard", pdf_text)
            if data:
                st.session_state.exam_data = data
                st.session_state.exam_active = True
                st.session_state.total_seconds = timer_map[q_count]
                st.session_state.start_time = time.time()
                st.rerun()

# --- 2. EXAM INTERFACE ---
elif st.session_state.exam_active:
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.total_seconds - elapsed
    
    if remaining <= 0:
        st.session_state.exam_active = False
        st.session_state.submitted = True
        st.rerun()

    mins, secs = divmod(int(remaining), 60)
    
    # --- RIGHT SIDEBAR: PALETTE ---
    with st.sidebar:
        st.markdown(f"<h1 style='text-align: center; color: red;'>{mins:02d}:{secs:02d}</h1>", unsafe_allow_html=True)
        st.progress(max(0.0, remaining / st.session_state.total_seconds))
        st.divider()
        st.markdown("### Question Palette")
        
        cols = st.columns(4)
        for i in range(len(st.session_state.exam_data)):
            label = f"{i+1}"
            if i in st.session_state.marked: label = f"★{i+1}"
            elif i in st.session_state.user_answers: label = f"✓{i+1}"
            
            if cols[i % 4].button(label, key=f"nav_{i}"):
                st.session_state.current_q = i
                st.rerun()
        
        st.divider()
        if st.button("🟥 SUBMIT EXAM", type="primary"):
            st.session_state.exam_active = False
            st.session_state.submitted = True
            st.rerun()

    # --- MAIN QUESTION AREA ---
    idx = st.session_state.current_q
    q = st.session_state.exam_data[idx]
    
    st.markdown(f"## Question {idx + 1}")
    st.markdown(f"**{q['question']}**")
    
    opts = list(q['options'].keys())
    prev_ans = st.session_state.user_answers.get(idx)
    
    ans = st.radio("Select Answer:", opts, 
                   format_func=lambda x: f"{x}: {q['options'][x]}",
                   index=opts.index(prev_ans) if prev_ans else None,
                   key=f"radio_{idx}")
    
    st.write("")
    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("⬅ Previous") and idx > 0:
        st.session_state.current_q -= 1
        st.rerun()
    if c2.button("⭐ Mark Review"):
        if idx in st.session_state.marked: st.session_state.marked.remove(idx)
        else: st.session_state.marked.add(idx)
        st.rerun()
    if c3.button("Save & Next ➡"):
        if ans: st.session_state.user_answers[idx] = ans
        if idx < len(st.session_state.exam_data) - 1: st.session_state.current_q += 1
        st.rerun()

# --- 3. REVIEW SCREEN ---
elif st.session_state.submitted:
    st.title("📊 Exam Results")
    
    total = len(st.session_state.exam_data)
    correct = sum(1 for i, q in enumerate(st.session_state.exam_data) if st.session_state.user_answers.get(i) == q['correct'])
    incorrect = len(st.session_state.user_answers) - correct
    skipped = total - len(st.session_state.user_answers)
    raw_score = (correct * 4) - (incorrect * 1)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Score", raw_score)
    c2.metric("Correct", correct)
    c3.metric("Wrong", incorrect)
    c4.metric("Skipped", skipped)

    st.divider()

    with st.sidebar:
        st.markdown("### Answer Key")
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
                if k != 'font_size': del st.session_state[k]
            st.rerun()

    idx = st.session_state.current_q
    q = st.session_state.exam_data[idx]
    user_a = st.session_state.user_answers.get(idx)
    real_a = q['correct']
    
    st.markdown(f"### Q{idx+1}: Review")
    st.write(q['question'])
    
    for opt, txt in q['options'].items():
        if opt == real_a: st.success(f"✅ {opt}: {txt} (Correct Answer)")
        elif opt == user_a and opt != real_a: st.error(f"❌ {opt}: {txt} (Your Answer)")
        else: st.write(f"{opt}: {txt}")
            
    st.info(f"**Explanation:** {q['explanation']}")
