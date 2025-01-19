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

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI with API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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

# Define functions
def get_gemini_response(job_description, content):
    """Generates a response from the Gemini model based on job description and resume content."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
You are an experienced Technical Human Resource Manager. Your task is to score the provided resumes against the job description provided below. 
Job Description: {job_description}
Evaluate the resume content and provide scores out of 10 for each category. Do share an overall score for each resume, but do not share improvement methods or a detailed analysis. Justification for scoring is required. 
Also share the previous experience in the resume. Share 3 questions you would ask particularly to that candidate."""
    response = model.generate_content([prompt, content])
    
    # Extract overall score from response text using improved method
    overall_score = extract_overall_score(response.text)
    
    return {
        "text": response.text,
        "overall_score": overall_score
    }

def extract_overall_score(response_text):
    """Extracts the overall score from the response text using regex and fallback methods."""
    # Try regex first
    match = re.search(r'(?i)(overall\s*score[:\-\s]+|overall[:\-\s]+)(\d+(\.\d+)?)', response_text)
    if match:
        return float(match.group(2))  # Extract and return the numeric part
    
    # Fallback to keyword-based parsing if regex fails
    lines = response_text.splitlines()
    for line in lines:
        if "overall" in line.lower() and any(char.isdigit() for char in line):
            # Attempt to extract number from line
            match = re.search(r'\d+(\.\d+)?', line)
            if match:
                return float(match.group(0))
    
    return None

def calculate_average_overall_score(results):
    """Calculates the average overall score for all resumes in a session."""
    scores = [result['overall_score'] for result in results if result['overall_score'] is not None]
    if scores:
        return sum(scores) / len(scores)
    return 0

def extract_text_from_pdf(uploaded_file):
    """Extracts text from a PDF file."""
    reader = PdfReader(uploaded_file)
    text = ''
    for page in reader.pages:
        text += page.extract_text() + '\n'
    return text.strip()

def extract_text_from_docx(uploaded_file):
    """Extracts text from a DOCX file."""
    doc = docx.Document(uploaded_file)
    return "\n".join([para.text for para in doc.paragraphs]).strip()

def extract_candidate_info(content):
    """Extracts candidate name, phone number, and email from the resume content using regex."""
    name = "Not Found"
    phone_number = "Not Found"
    email = "Not Found"
    
    lines = content.split('\n')
    
    # Assuming the first line is the name (this can be adjusted based on formatting)
    if lines:
        name = lines[0].strip()
    
    # Regex patterns for phone number and email
    phone_pattern = re.compile(r'\+?\d[\d -]{8,}\d')
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    
    for line in lines:
        if email_pattern.search(line):
            email = email_pattern.search(line).group()
        if phone_pattern.search(line):
            phone_number = phone_pattern.search(line).group()

    return f"Name: {name}, Phone: {phone_number}, Email: {email}"

def get_technical_questions(job_description):
    """Generates technical questions and brief answers based on the job description."""
    prompt = f"Based on the following job description, share 10 technical questions to ask candidates. Also share brief answers to those questions. Give the answer in the form of points so it is easy for me to understand.\nJob Description: {job_description}"
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt])
    return response.text

# Streamlit App Configuration
st.set_page_config(page_title="Usurp Resume Scoring")
st.header("Usurp Resume Scoring System")

# Input fields
session_name = st.text_input("Enter Session Name:")
input_text = st.text_area("Job Description:", height=300)
uploaded_files = st.file_uploader("Upload your resumes (PDF or DOCX):", type=["pdf", "docx"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"{len(uploaded_files)} file(s) uploaded successfully.")

submit_score = st.button("Score Resumes")
create_questions = st.button("Create Technical Questions")
save_score = st.button("Save Scoring")

# Initialize session state for results if it doesn't exist
if "results" not in st.session_state:
    st.session_state.results = []

if submit_score:
    results = []
    
    for uploaded_file in uploaded_files:
        if uploaded_file.type == "application/pdf":
            content_to_evaluate = extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            content_to_evaluate = extract_text_from_docx(uploaded_file)
        
        candidate_info = extract_candidate_info(content_to_evaluate)
        response_data = get_gemini_response(input_text, content_to_evaluate)
        
        results.append({
            "filename": uploaded_file.name,
            "candidate_info": candidate_info,
            "response": response_data["text"],
            "overall_score": response_data["overall_score"]
        })
    
    # Store results in session state
    st.session_state.results = results
    
    # Sort results by overall score in descending order before displaying
    sorted_results = sorted(st.session_state.results, key=lambda x: x['overall_score'], reverse=True)

    # Display results
    st.subheader("Results")
    for result in sorted_results:
        st.write(f"**Filename:** {result['filename']}")
        st.write(f"**Candidate Info:** {result['candidate_info']}")
        st.write(result['response'])
        st.write(f"**Overall Score:** {result['overall_score']}")

if save_score and session_name:
    if len(st.session_state.results) > 0:
        # Prepare results string and overall scores for saving
        results_str = "\n\n".join([
            f"**Filename:** {result['filename']}\n**Candidate Info:** {result['candidate_info']}\n{result['response']}\nOverall Score: {result['overall_score']}"
            for result in st.session_state.results
        ])
        
        # Get current time in IST for created_at field
        ist_timezone = pytz.timezone('Asia/Kolkata')
        created_at_ist = datetime.now(ist_timezone).strftime('%Y-%m-%d %H:%M:%S')

        # Calculate average overall score for this session
        average_overall_score = calculate_average_overall_score(st.session_state.results)

        # Save to database including average overall score
        c.execute('INSERT INTO scoring_sessions (session_name, num_resumes, results, created_at, overall_score) VALUES (?, ?, ?, ?, ?)', 
                  (session_name, len(st.session_state.results), results_str, created_at_ist, average_overall_score))
        conn.commit()
        
        st.success("Scoring session saved successfully!")
        st.session_state.results.clear()  # Clear results after saving
    else:
        st.warning("No scoring results available to save.")

if create_questions:
    if input_text.strip():  # Ensure job description is provided
        technical_questions = get_technical_questions(input_text)
        st.subheader("Technical Questions")
        st.write(technical_questions)
    else:
        st.warning("Please enter a job description to generate technical questions.")

# Display previous scoring sessions sorted by overall score (descending order)
st.subheader("Saved Scoring Sessions")
previous_sessions = c.execute('SELECT * FROM scoring_sessions ORDER BY overall_score DESC LIMIT 10').fetchall()

for session in previous_sessions:
    session_id, name, num_resumes, results, created_at, overall_score = session
    
    with st.expander(f"{name} ({num_resumes} resumes) - {created_at} - Avg Score: {overall_score:.2f}"):
        st.write(f"**Session Name:** {name}")
        st.write(f"**Number of Resumes:** {num_resumes}")
        if results.strip():
            st.markdown(results)
        else:
            st.write("No results found.")

conn.close()

