import streamlit as st
import json
import os
import requests
import google.generativeai as genai
import PyPDF2
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="INI SS CBT Simulator")

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
        if raw_text.startswith("
