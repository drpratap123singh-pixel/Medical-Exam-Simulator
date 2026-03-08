import streamlit as st
import requests

# Set page to wide mode for a better CBT feel
st.set_page_config(layout="wide")

def fetch_data(url):
    try:
        response = requests.get(url)
        return response.json()
    except:
        return None

# --- SIDEBAR: THE QUESTION BANK MENU ---
st.sidebar.title("📚 Question Bank")
quiz_choice = st.sidebar.radio(
    "Select a Topic to Start Test:",
    ["Home", "Systemic Sclerosis", "Immunology (SAD)", "General Medicine"]
)

# Define your Gist URLs here
URL_MAP = {
    "Systemic Sclerosis": "https://gist.githubusercontent.com/drpratap123singh-pixel/0c89646350ae70ae3dc4353fe9d38f15/raw/...", 
    "Immunology (SAD)": "YOUR_SECOND_GIST_URL_HERE"
}

if quiz_choice == "Home":
    st.title("👨‍⚕️ CBT Exam Simulator")
    st.write("Select a topic from the sidebar to begin your super-specialty practice.")
else:
    questions = fetch_data(URL_MAP.get(quiz_choice))
    
    if questions:
        st.title(f"📝 CBT: {quiz_choice}")
        
        # Track question index in session state
        if f'q_idx_{quiz_choice}' not in st.session_state:
            st.session_state[f'q_idx_{quiz_choice}'] = 0
            st.session_state[f'score_{quiz_choice}'] = 0

        idx = st.session_state[f'q_idx_{quiz_choice}']
        
        # Progress Bar
        progress = (idx + 1) / len(questions)
        st.progress(progress)
        st.write(f"Question {idx + 1} of {len(questions)}")

        q = questions[idx]
        st.subheader(q['question'])

        # CBT Options
        for key, val in q['options'].items():
            if st.button(f"{key}: {val}", key=f"{quiz_choice}_{idx}_{key}"):
                if key == q['answer']:
                    st.success(f"Correct! \n\n {q['explanation']}")
                    st.session_state[f'score_{quiz_choice}'] += 1
                else:
                    st.error(f"Incorrect. Correct answer is {q['answer']}. \n\n {q['explanation']}")

        # Navigation
        if st.button("Next Question ➡️"):
            if idx < len(questions) - 1:
                st.session_state[f'q_idx_{quiz_choice}'] += 1
                st.rerun()
            else:
                st.balloons()
                st.write(f"### Test Complete! Your Score: {st.session_state[f'score_{quiz_choice}']} / {len(questions)}")
    else:
        st.error("Select a valid URL or check your internet connection.")
