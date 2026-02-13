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

st.set_page_config(page_title="MEDICAL EXAM SIMULATOR", layout="wide")

# --- UI ENGINE: WHITE THEME & BLACK TEXT ---
if 'font_size' not in st.session_state: st.session_state.font_size = 20

def apply_exam_ui():
    f_size = st.session_state.font_size
    st.markdown(f"""
        <style>
        /* 1. FORCE MAIN BACKGROUND WHITE */
        .stApp {{ background-color: #ffffff !important; color: #000000 !important; }}
        
        /* 2. FORCE TEXT BLACK & VISIBLE */
        p, div, label, span, h1, h2, h3, h4, .stMarkdown, .stRadio label {{
            font-size: {f_size}px !important;
            color: #000000 !important;
            opacity: 1.0 !important;
        }}

        /* 3. WHITE INPUT BOXES */
        .stTextInput input, .stSelectbox div, div[data-baseweb="select"] > div {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
        }}
        
        /* 4. BUTTONS */
        .stButton>button {{
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
            font-weight: bold !important;
        }}
        
        /* 5. HIDE DEFAULT STREAMLIT SIDEBAR (Since we made our own Right Sidebar) */
        [data-testid="stSidebar"] {{ display: none; }}
        </style>
    """, unsafe_allow_html=True)

# --- DATA & SAVING ENGINE ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: return json.load(f)
        except: return []
    return []

def save_exam_result(topic, score, total, questions, user_answers):
    history = load_history()
    entry = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topic": topic,
        "score": f"{score}/{total}",
        "data": questions,
        "user_answers": user_answers
    }
    history.insert(0, entry)
    try:
        with open(HISTORY_FILE, "w") as f: json.dump(history, f)
    except: pass

@st.cache_data
def get_working_model_name():
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name: return m.name
        return "models/gemini-pro"
    except: return "models/gemini-1.5-flash"

def generate_exam_data(topic, num, difficulty, context=None):
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
        st.error(f"AI Error: {e}"); return []

def display_live_timer(total_seconds):
    end_timestamp = st.session_state.start_time + total_seconds
    end_timestamp_ms = end_timestamp * 1000
    st.markdown(f"""
        <div style="text-align: center; font-size: 30px; font-weight: bold; color: #d90429; border: 2px solid #000; padding: 10px; margin-bottom: 20px;">
            ⏱️ <span id="countdown_display">Loading...</span>
        </div>
        <script>
        var x = setInterval(function() {{
            var now = new Date().getTime();
            var distance = {end_timestamp_ms} - now;
            var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((distance % (1000 * 60)) / 1000);
            minutes = minutes < 10 ? "0" + minutes : minutes;
            seconds = seconds < 10 ? "0" + seconds : seconds;
            var display = document.getElementById("countdown_display");
            if (display) {{ display.innerHTML = minutes + ":" + seconds; }}
            if (distance < 0) {{ clearInterval(x); if (display) {{ display.innerHTML = "00:00"; }} }}
        }}, 1000);
        </script>
    """, unsafe_allow_html=True)

# --- STATE ---
if 'exam_active' not in st.session_state: st.session_state.exam_active = False
if 'exam_data' not in st.session_state: st.session_state.exam_data = []
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'current_q' not in st.session_state: st.session_state.current_q = 0
if 'start_time' not in st.session_state: st.session_state.start_time = None
if 'total_seconds' not in st.session_state: st.session_state.total_seconds = 0
if 'marked' not in st.session_state: st.session_state.marked = set()
if 'submitted' not in st.session_state: st.session_state.submitted = False
if 'history' not in st.session_state: st.session_state.history = load_history()

apply_exam_ui()

# --- TOP BAR ---
c_title, c_min, c_plus = st.columns([8, 1, 1])
with c_title: st.caption("Medical Exam Simulator Pro")
with c_min: 
    if st.button("A-"): st.session_state.font_size = max(14, st.session_state.font_size - 2); st.rerun()
with c_plus:
    if st.button("A+"): st.session_state.font_size = min(30, st.session_state.font_size + 2); st.rerun()

# --- 1. SETUP SCREEN (Show History Here) ---
if not st.session_state.exam_active and not st.session_state.submitted:
    st.title("📝 New Exam Setup")
    
    # History Section
    with st.expander("📜 Past Exams (Click to Load)"):
        if st.session_state.history:
            for i, h in enumerate(st.session_state.history):
                if st.button(f"{h['date']} - {h['topic']} ({h['score']})", key=f"hist_{i}"):
                    st.session_state.exam_data = h['data']
                    st.session_state.user_answers = h['user_answers']
                    st.session_state.submitted = True
                    st.session_state.current_q = 0
                    st.rerun()
        else:
            st.write("No saved exams yet.")

    st.divider()
    topic = st.text_input("Enter Exam Topic")
    source = st.radio("Source", ["AI Knowledge", "Upload PDF"], horizontal=True)
    pdf_text = None
    if source == "Upload PDF":
        f = st.file_uploader("Upload PDF", type='pdf')
        if f: 
            reader = PyPDF2.PdfReader(f)
            pdf_text = "".join([p.extract_text() for p in reader.pages])
    
    q_count = st.selectbox("Number of Questions:", [20, 40, 60])
    
    # TIMER: 1 min per question (20min, 40min, 60min)
    timer_map = {20: 20*60, 40: 40*60, 60: 60*60}
    
    if st.button("🚀 Start Exam", type="primary"):
        with st.spinner("Generating..."):
            data = generate_exam_data(topic, q_count, "Hard", pdf_text)
            if data:
                st.session_state.exam_data = data
                st.session_state.exam_active = True
                st.session_state.total_seconds = timer_map[q_count]
                st.session_state.start_time = time.time()
                st.session_state.current_topic = topic
                st.rerun()

# --- 2. EXAM INTERFACE (SPLIT LAYOUT) ---
elif st.session_state.exam_active:
    # Check Timer
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.total_seconds - elapsed
    if remaining <= 0:
        st.session_state.exam_active = False
        st.session_state.submitted = True
        save_exam_result(st.session_state.current_topic, 0, len(st.session_state.exam_data), st.session_state.exam_data, st.session_state.user_answers)
        st.rerun()

    # LAYOUT: LEFT (Questions) | RIGHT (Palette)
    col_left, col_right = st.columns([3, 1])

    # --- RIGHT SIDE: PALETTE & TIMER ---
    with col_right:
        display_live_timer(st.session_state.total_seconds)
        st.markdown("**Question Palette**")
        
        # Grid
        cols = st.columns(3)
        for i in range(len(st.session_state.exam_data)):
            label = f"{i+1}"
            if i in st.session_state.marked: label = f"★{i+1}"
            elif i in st.session_state.user_answers: label = f"✓{i+1}"
            
            if cols[i % 3].button(label, key=f"nav_{i}"):
                st.session_state.current_q = i
                st.rerun()
        
        st.write("")
        if st.button("🟥 SUBMIT EXAM", type="primary"):
            st.session_state.exam_active = False
            st.session_state.submitted = True
            # SAVE ON SUBMIT
            correct = sum(1 for i, q in enumerate(st.session_state.exam_data) if st.session_state.user_answers.get(i) == q['correct'])
            save_exam_result(st.session_state.current_topic, correct, len(st.session_state.exam_data), st.session_state.exam_data, st.session_state.user_answers)
            st.session_state.history = load_history() # Refresh history
            st.rerun()

    # --- LEFT SIDE: QUESTION ---
    with col_left:
        idx = st.session_state.current_q
        q = st.session_state.exam_data[idx]
        
        st.markdown(f"### Question {idx + 1}")
        st.markdown(f"**{q['question']}**")
        
        opts = list(q['options'].keys())
        prev = st.session_state.user_answers.get(idx)
        ans = st.radio("Select Answer:", opts, format_func=lambda x: f"{x}: {q['options'][x]}", index=opts.index(prev) if prev else None, key=f"rad_{idx}")
        
        st.divider()
        c1, c2, c3 = st.columns([1,1,1])
        if c1.button("⬅ Previous") and idx > 0: st.session_state.current_q -= 1; st.rerun()
        if c2.button("⭐ Mark Review"):
            if idx in st.session_state.marked: st.session_state.marked.remove(idx)
            else: st.session_state.marked.add(idx)
            st.rerun()
        if c3.button("Save & Next ➡"):
            if ans: st.session_state.user_answers[idx] = ans
            if idx < len(st.session_state.exam_data) - 1: st.session_state.current_q += 1
            st.rerun()

# --- 3. REVIEW INTERFACE (SPLIT LAYOUT) ---
elif st.session_state.submitted:
    
    total = len(st.session_state.exam_data)
    correct = sum(1 for i, q in enumerate(st.session_state.exam_data) if st.session_state.user_answers.get(i) == q['correct'])
    
    col_left, col_right = st.columns([3, 1])

    # --- RIGHT SIDE: RESULTS PALETTE ---
    with col_right:
        st.metric("Final Score", f"{correct}/{total}")
        st.markdown("**Result Palette**")
        
        cols = st.columns(3)
        for i in range(total):
            user_a = st.session_state.user_answers.get(i)
            real_a = st.session_state.exam_data[i]['correct']
            
            # Button Colors (Green=Correct, Red=Wrong)
            lbl = f"Q{i+1}"
            if user_a == real_a: btn_type = "✅" 
            elif user_a is None: btn_type = "⚪"
            else: btn_type = "❌"
            
            if cols[i % 3].button(f"{btn_type} {i+1}", key=f"res_{i}"):
                st.session_state.current_q = i
                st.rerun()

        st.divider()
        if st.button("Start New Exam"):
            st.session_state.exam_active = False
            st.session_state.submitted = False
            st.session_state.user_answers = {}
            st.session_state.marked = set()
            st.rerun()

    # --- LEFT SIDE: DETAILED REVIEW ---
    with col_left:
        idx = st.session_state.current_q
        q = st.session_state.exam_data[idx]
        user_a = st.session_state.user_answers.get(idx)
        real_a = q['correct']
        
        st.markdown(f"### Q{idx+1} Review")
        st.write(q['question'])
        
        for opt, txt in q['options'].items():
            if opt == real_a: st.success(f"✅ {opt}: {txt} (Correct Answer)")
            elif opt == user_a and opt != real_a: st.error(f"❌ {opt}: {txt} (Your Answer)")
            else: st.write(f"{opt}: {txt}")
        
        st.info(f"**Explanation:** {q['explanation']}")
