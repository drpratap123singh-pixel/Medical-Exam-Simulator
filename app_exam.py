parsed_json = json.loads(raw_text.strip())
        return parsed_json
    except Exception as e:
        st.error(f"Failed to generate questions. Error: {e}")
        return None

# --- EXAM LOGIC FUNCTIONS ---
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

# --- VIEWS ---
def render_dashboard():
    st.title("🩺 INI SS Generator & Simulator")
    
    # API KEY INPUT
    api_key = st.sidebar.text_input("Enter Google Gemini API Key", type="password")
    st.sidebar.markdown("[Get API Key here](https://aistudio.google.com/app/apikey)")
    
    tab1, tab2, tab3 = st.tabs(["🧠 Generate from Topic", "📄 Generate from PDF", "📥 Paste Raw JSON"])
    
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
                    if qs: start_exam(qs)
                    st.rerun()
                    
    with tab2:
        st.subheader("Generate Exam from PDF Document")
        uploaded_file = st.file_type("Upload PDF", type=['pdf'])
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
                    if qs: start_exam(qs)
                    st.rerun()
                    
    with tab3:
        st.subheader("Import Pre-made JSON Exam")
        st.info("Paste the JSON code block I give you here to take that specific test.")
        raw_json = st.text_area("Paste JSON here", height=200)
        if st.button("Start Exam from JSON"):
            try:
                qs = json.loads(raw_json)
                start_exam(qs)
                st.rerun()
            except Exception as e:
                st.error("Invalid JSON format. Please check the code.")

def render_exam_ui():
    idx = st.session_state.current_q_idx
    q_data = st.session_state.active_questions[idx]
    total_q = len(st.session_state.active_questions)
    
    st.markdown("<div class='top-header'>MEDICAL EXAM SIMULATOR</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'><b>Time Left:</b> ⏳ <i>Mock Timer</i> &nbsp;&nbsp;|&nbsp;&nbsp; <b>Question Paper</b></div>", unsafe_allow_html=True)
    
    col_main, col_side = st.columns([3.5, 1.5], gap="large")
    
    with col_main:
        st.markdown("<div class='q-type-bar'>Question type : MCQ</div>", unsafe_allow_html=True)
        st.markdown(f"<b>Question no : {idx + 1}</b>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-box'>{q_data.get('question', '')}</div><br>", unsafe_allow_html=True)
        
        options = q_data.get('options', [])
        current_ans = st.session_state.responses.get(idx, None)
        default_idx = options.index(current_ans) if current_ans in options else None
        
        radio_key = f"radio_{idx}"
        st.radio("Options", options, index=default_idx, key=radio_key, label_visibility="collapsed")
        st.checkbox("I am guessing this ℹ️", key=f"guess_{idx}")
        
        st.divider()
        btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)
        with btn_c1: st.button("Mark for Review & Next", on_click=mark_and_next, use_container_width=True)
        with btn_c2: st.button("Clear Response", on_click=clear_response, use_container_width=True)
        with btn_c3: st.button("Save and Next", on_click=save_and_next, type="primary", use_container_width=True)
        with btn_c4: st.button("Submit Exam", on_click=submit_exam, use_container_width=True)

    with col_side:
        st.markdown("<div class='profile-box'><h1 style='margin:0;'>👤</h1><b>Candidate</b><br><span style='color:gray;'>INI SS Aspirant</span></div>", unsafe_allow_html=True)
        
        stats = {0:0, 1:0, 2:0, 3:0, 4:0}
        for s in st.session_state.statuses.values(): stats[s] = stats.get(s, 0) + 1
            
        st.markdown(f"""
        <div class='legend-box'>
            <div class='legend-item'><span class='status-1'>{stats[1]}</span> Answered</div>
            <div class='legend-item'><span class='status-2'>{stats[2]}</span> Not Answered</div>
            <div class='legend-item'><span class='status-0'>{stats[0]}</span> Not Visited</div>
            <div class='legend-item'><span class='status-3'>{stats[3]}</span> Marked</div>
            <div style='margin-top:5px;'><span class='status-4'>{stats[4]}</span> Ans & Marked</div>
        </div>
        <div style='background-color:#2a5298; color:white; padding:5px; text-align:center;'><b>All questions</b></div>
        """, unsafe_allow_html=True)
        
        cols_per_row = 5
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

def render_results():
    st.title("📊 Exam Results & Analysis")
    score = sum(1 for i, q in enumerate(st.session_state.active_questions) if st.session_state.responses.get(i) == q.get('correct_answer'))
    st.header(f"Your Score: {score} / {len(st.session_state.active_questions)}")
    
    if st.button("Return to Dashboard"):
        st.session_state.exam_active = False
        st.session_state.show_results = False
        st.rerun()
        
    st.divider()
    for i, q in enumerate(st.session_state.active_questions):
        correct = q.get('correct_answer')
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
            st.write(f"**Rationale:** {q.get('rationale', 'No rationale provided.')}")

def main():
    if st.session_state.show_results: render_results()
    elif st.session_state.exam_active: render_exam_ui()
    else: render_dashboard()

if __name__ == "__main__":
    main()
