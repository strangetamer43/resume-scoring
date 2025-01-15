from dotenv import load_dotenv
import os
import re
import streamlit as st
from PyPDF2 import PdfReader
import docx
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI with API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_response(job_description, content):
    """Generates a response from the Gemini model based on job description and resume content."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
You are an experienced Technical Human Resource Manager. Your task is to score the provided resumes against the job description provided below. 
Job Description: {job_description}
Evaluate the resume content and provide scores out of 10 for each category. Do share an overall score for each resume, but do not share improvement methods or a detailed analysis. Justification for scoring is required. 
Also share the previous experience in the resume. Share 3 questions you would ask particularly to that candidate. """
    response = model.generate_content([prompt, content])
    return response.text

def input_pdf_setup(uploaded_file):
    """Extracts text from a PDF file."""
    if uploaded_file is not None:
        return extract_text_from_pdf(uploaded_file)
    else:
        raise FileNotFoundError("No file uploaded")

def extract_text_from_pdf(uploaded_file):
    """Extracts text from a PDF file."""
    reader = PdfReader(uploaded_file)
    text = ''
    for page in reader.pages:
        text += page.extract_text() + '\n'
    return text.strip()

def input_docx_setup(uploaded_file):
    """Extracts text from a DOCX file."""
    if uploaded_file is not None:
        doc = docx.Document(uploaded_file)
        return "\n".join([para.text for para in doc.paragraphs]).strip()
    else:
        raise FileNotFoundError("No file uploaded")

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
    prompt = f"Based on the following job description, share 10 technical questions to ask candidates. Also share brief answers to those questions. give the answer in the form of points so it is easy for me to understand.\nJob Description: {job_description}"
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt])
    return response.text

# Streamlit App Configuration
st.set_page_config(page_title="Usurp Resume Scoring")
st.header("Resume Scoring System")
input_text = st.text_area("Job Description: ", key="input", height=400)
uploaded_files = st.file_uploader("Upload your resumes (PDF or DOCX)...", type=["pdf", "docx"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"{len(uploaded_files)} file(s) Uploaded Successfully")

submit_score = st.button("Score Resumes")
create_questions = st.button("Create Technical Questions")

if submit_score:
    results = []
    
    for uploaded_file in uploaded_files:
        if uploaded_file.type == "application/pdf":
            content_to_evaluate = input_pdf_setup(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            content_to_evaluate = input_docx_setup(uploaded_file)
        
        candidate_info = extract_candidate_info(content_to_evaluate)
        response = get_gemini_response(input_text, content_to_evaluate)
        
        results.append({"filename": uploaded_file.name, "candidate_info": candidate_info, "response": response})

    st.subheader("Results")
    for result in results:
        st.write(f"**{result['filename']}**")
        st.write(f"**Candidate Info:** {result['candidate_info']}")
        st.write(result['response'])

if create_questions:
    if input_text.strip():  # Ensure job description is provided
        technical_questions = get_technical_questions(input_text)
        st.subheader("Technical Questions")
        st.write(technical_questions)
    else:
        st.warning("Please enter a job description to generate technical questions.")
