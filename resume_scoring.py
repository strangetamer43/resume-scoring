from dotenv import load_dotenv
import os
import re
import streamlit as st
from PyPDF2 import PdfReader
import docx
import sqlite3
import google.generativeai as genai
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

# Configure Google Generative AI
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Database setup
conn = sqlite3.connect('new_resume.db')
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS scoring_sessions (
    id INTEGER PRIMARY KEY,
    session_name TEXT,
    num_resumes INTEGER,
    results TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    overall_score REAL
)
''')
conn.commit()

# Functions
def get_gemini_response(job_description, content):
    """Generates a response from Gemini AI, extracting scores and questions."""
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""
    You are an experienced Technical HR Manager. Your task is to evaluate the resume against the job description.
    Assign scores out of 10 for different categories (e.g., Skills, Experience, Education, etc.), then provide an overall score.
    Check for gaps in the work expereince timeline, mention if any, of how many months.  
    Give 3 technical questions tailored for each individual resume. Keep the questions short and open ended, but targetted.
    Search the company names and mention the industry that company works in. Mention for each company worked. Check their websites to make an accurate judgement. 
    Job Description: {job_description}
    """
    response = model.generate_content([prompt, content])
    response_text = response.text
    overall_score = calculate_average_score(response_text)
    return {"text": response_text, "overall_score": overall_score}

def calculate_average_score(response_text):
    """Extracts individual scores and calculates an average."""
    scores = [float(match.group(1)) for match in re.finditer(r'\b(\d+(\.\d+)?)\s*/\s*10\b', response_text)]
    return round(sum(scores) / len(scores), 2) if scores else None

def extract_text_from_pdf(uploaded_file):
    """Extracts text from a PDF."""
    reader = PdfReader(uploaded_file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()]).strip()

def extract_text_from_docx(uploaded_file):
    """Extracts text from a DOCX file."""
    doc = docx.Document(uploaded_file)
    return "\n".join([para.text for para in doc.paragraphs]).strip()

def extract_candidate_info(content):
    """Extracts candidate details from the resume text."""
    name = content.split('\n')[0].strip() if content else "Not Found"
    phone_match = re.search(r'\+?\d[\d -]{8,}\d', content)
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
    return {
        "Name": name,
        "Phone": phone_match.group() if phone_match else "Not Found",
        "Email": email_match.group() if email_match else "Not Found"
    }

def get_technical_questions(job_description):
    """Generates 10 technical interview questions based on the job description."""
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"Based on the following job description, share 10 technical questions to ask candidates. Also share brief answers to those questions. Give the answer in the form of points so it is easy for me to understand.\nJob Description: {job_description}"
    response = model.generate_content([prompt])
    return response.text if response else "No questions generated."

def delete_scoring_session(session_id):
    """Deletes a scoring session from the database."""
    c.execute("DELETE FROM scoring_sessions WHERE id = ?", (session_id,))
    conn.commit()

# Streamlit UI
st.set_page_config(page_title="Usurp Resume Scoring")
st.header("Usurp Resume Scoring System")

session_name = st.text_input("Enter Session Name:")
job_description = st.text_area("Job Description:", height=300)
uploaded_files = st.file_uploader("Upload Resumes (PDF/DOCX):", type=["pdf", "docx"], accept_multiple_files=True)

submit_score = st.button("Score Resumes")
create_questions = st.button("Generate Technical Questions")
save_score = st.button("Save Scoring")

if "results" not in st.session_state:
    st.session_state.results = []

if submit_score:
    results = []
    
    for uploaded_file in uploaded_files:
        content = extract_text_from_pdf(uploaded_file) if uploaded_file.type == "application/pdf" else extract_text_from_docx(uploaded_file)
        candidate_info = extract_candidate_info(content)
        response_data = get_gemini_response(job_description, content)
        
        results.append({
            "filename": uploaded_file.name,
            "candidate_info": candidate_info,
            "response": response_data["text"],
            "overall_score": response_data["overall_score"]
        })
    
    st.session_state.results = sorted(results, key=lambda x: x["overall_score"] if x["overall_score"] is not None else -1, reverse=True)
    
    st.subheader("Results")
    for result in st.session_state.results:
        st.write(f"**Filename:** {result['filename']}")
        st.write(f"**Candidate Info:** {result['candidate_info']}")
        st.write(result['response'])
        st.write(f"**Overall Score:** {result['overall_score']}")

if save_score and session_name:
    if st.session_state.results:
        results_str = "\n\n".join([
            f"**Filename:** {result['filename']}\n**Candidate Info:** {result['candidate_info']}\n{result['response']}\nOverall Score: {result['overall_score']}"
            for result in st.session_state.results
        ])
        
        ist_timezone = pytz.timezone('Asia/Kolkata')
        created_at_ist = datetime.now(ist_timezone).strftime('%Y-%m-%d %H:%M:%S')
        avg_score = round(sum(r["overall_score"] for r in st.session_state.results if r["overall_score"] is not None) / len(st.session_state.results), 2)
        
        c.execute('''INSERT INTO scoring_sessions (session_name, num_resumes, results, created_at, overall_score) VALUES (?, ?, ?, ?, ?)''',
                  (session_name, len(st.session_state.results), results_str, created_at_ist, avg_score))
        conn.commit()
        st.success("Scoring session saved successfully!")
        st.session_state.results.clear()

st.subheader("Saved Scoring Sessions")
previous_sessions = c.execute('SELECT * FROM scoring_sessions ORDER BY overall_score DESC LIMIT 10').fetchall()
for session in previous_sessions:
    session_id, name, num_resumes, results, created_at, overall_score = session
    with st.expander(f"{name} ({num_resumes} resumes) - {created_at} - Avg Score: {overall_score:.2f}"):
        st.markdown(results)
        if st.button(f"Delete {name}", key=f"delete_{session_id}"):
            delete_scoring_session(session_id)
            st.experimental_rerun()

if create_questions:
    questions = get_technical_questions(job_description)
    st.subheader("Generated Technical Questions")
    st.write(questions)

conn.close()
