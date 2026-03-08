import streamlit as st
import json
import random

# 1. Load the Question Database
@st.cache_data
def load_questions():
    with open('question_bank.json', 'r') as file:
        return json.load(file)

def main():
    st.title("🩺 INI SS Medical Exam Simulator")
    
    # Load data
    questions_db = load_questions()
    
    # Optional: Let user select a category
    categories = list(set([q['category'] for q in questions_db]))
    categories.insert(0, "All Topics")
    
    selected_category = st.sidebar.selectbox("Select Topic", categories)
    
    # Filter questions based on selection
    if selected_category == "All Topics":
        filtered_questions = questions_db
    else:
        filtered_questions = [q for q in questions_db if q['category'] == selected_category]
        
    st.write(f"Loaded **{len(filtered_questions)}** questions.")
    
    # Initialize session state to keep track of the current question
    if 'current_q' not in st.session_state:
        st.session_state.current_q = 0
        st.session_state.score = 0
        
    # UI to display the question
    if st.session_state.current_q < len(filtered_questions):
        q = filtered_questions[st.session_state.current_q]
        
        st.markdown(f"### Question {st.session_state.current_q + 1}")
        st.write(q['question'])
        
        with st.expander("💡 Need a hint?"):
            st.info(q['hint'])
            
        # Display Radio buttons for options
        # We use a unique key so Streamlit doesn't mix up states between questions
        choice = st.radio("Select an answer:", q['options'], key=f"q_{st.session_state.current_q}")
        
        if st.button("Submit Answer"):
            if choice == q['correct_answer']:
                st.success("Correct!")
                st.session_state.score += 1
            else:
                st.error(f"Incorrect. The correct answer is: {q['correct_answer']}")
                
            st.info(f"**Rationale:** {q['rationale']}")
            
            # Move to next question (requires a rerun to update UI)
            st.session_state.current_q += 1
            if st.button("Next Question"):
                st.rerun()
                
    else:
        st.balloons()
        st.write(f"### Quiz Complete! You scored {st.session_state.score} out of {len(filtered_questions)}.")
        if st.button("Restart Quiz"):
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.rerun()

if __name__ == "__main__":
    main()
