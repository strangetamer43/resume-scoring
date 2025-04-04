import os
import re
import pymongo
import docx
import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from google.generativeai import GenerativeModel
from bson import ObjectId

# Load environment variables
load_dotenv()

# Google Generative AI configuration
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai_model = GenerativeModel('gemini-2.0-flash')

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
db = client["ai-resume-scoring"]

# Kanban Statuses
KANBAN_STATUSES = [
    "Resume Scoring", "Initial Call Done", "Client Submission Done", "Client Interview",
    "Selected", "Rejected", "Not Interested", "Offer Letter Shared", "Onboarded"
]

# ✅ Initialize session state variables at the start
if "candidates" not in st.session_state:
    st.session_state["candidates"] = []
if "selected_candidate_id" not in st.session_state:
    st.session_state["selected_candidate_id"] = None

def get_gemini_response(job_description, content):
    prompt = f"""
        You are an experienced Technical HR Manager. Your task is to evaluate the resume against the job description.
        Assign scores out of 10 for different categories (e.g., Skills, Experience, Education, etc.), then provide an overall score. Always provide an overall score.
        Check for gaps in the work experience timeline, mention if any, of how many months.
        Give 3 technical questions tailored for each individual resume. Keep the questions short and open-ended, but targeted.
        Search the company names and mention the industry that company works in. Mention for each company worked. Check their websites to make an accurate judgment.
        Job Description: {job_description}
    """
    response = genai_model.generate_content([prompt, content])
    response_text = response.text
    overall_score = calculate_average_score(response_text)
    return {"text": response_text, "overall_score": overall_score if overall_score is not None else 0}

def calculate_average_score(response_text):
    scores = [float(match.group(1)) for match in re.finditer(r'\b(\d+(\.\d+)?)\s*/\s*10\b', response_text)]
    return round(sum(scores) / len(scores), 2) if scores else None

def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()]).strip()

def extract_text_from_docx(uploaded_file):
    doc = docx.Document(uploaded_file)
    return "\n".join([para.text for para in doc.paragraphs]).strip()

def extract_name(content):
    """
    Extracts a probable full name from resume content using regex.
    - Assumes names appear at the start of the resume.
    - Detects capitalized first and last names.
    - Allows middle names and hyphenated names.
    """
    name_pattern = r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})\b"
    
    matches = re.findall(name_pattern, content)

    if matches:
        return matches[0]  # Return the first reasonable match
    
    return "Not Found"

def extract_candidate_info(content):
    name = extract_name(content) 
    phone_match = re.search(r'\+?\d[\d -]{8,}\d', content)
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
    return {
        "Name": name,
        "Phone": phone_match.group() if phone_match else "Not Found",
        "Email": email_match.group() if email_match else "Not Found"
    }

def update_candidate_notes(candidate, candidate_notes, job_collection):
    result = job_collection.update_one({"_id": ObjectId(candidate["_id"])}, {"$set": {"notes": candidate_notes}})
    if result.matched_count == 0:
        st.error("Failed to update notes: No matching candidate found.")
    else:
        st.success("Notes updated successfully!")
    
    # Refresh data after updating notes
    st.session_state["candidates"] = list(job_collection.find())
    st.rerun()

# Streamlit UI
st.set_page_config(page_title="Usurp Resume Scoring", layout="wide")
st.header("Usurp Resume Scoring System")

# Job title input and file upload
session_name = st.text_input("Enter Job Title:")
job_description = st.text_area("Job Description:", height=300)
uploaded_files = st.file_uploader("Upload Resumes (PDF/DOCX):", type=["pdf", "docx"], accept_multiple_files=True)

submit_score = st.button("Score Resumes")

# Fetch existing job collections
collection_names = db.list_collection_names()
collection_names.insert(0, "Select a Job Title")
selected_job_title = st.selectbox("Select Existing Job Title:", collection_names)

# Handle Resume Scoring & Database Insertion
if submit_score and session_name:
    results = []
    job_collection = db[session_name]

    for uploaded_file in uploaded_files:
        content = extract_text_from_pdf(uploaded_file) if uploaded_file.type == "application/pdf" else extract_text_from_docx(uploaded_file)
        candidate_info = extract_candidate_info(content)
        response_data = get_gemini_response(job_description, content)

        candidate_data = {
            "filename": uploaded_file.name,
            "candidate_info": candidate_info,
            "response": response_data["text"],
            "overall_score": response_data["overall_score"],
            "status": "Resume Scoring",
            "notes": ""
        }
        job_collection.insert_one(candidate_data)
        results.append(candidate_data)

    st.success("Resumes scored and added to the job collection!")

# Kanban Board
if selected_job_title and selected_job_title != "Select a Job Title":
    st.subheader(f"Candidate Progress for {selected_job_title}")
    job_collection = db[selected_job_title]

    # ✅ Ensure session state for candidates is updated
    st.session_state["candidates"] = list(job_collection.find())

    # Kanban Board
    for status in KANBAN_STATUSES:
        with st.expander(status):
            candidates = [c for c in st.session_state["candidates"] if c["status"] == status]
            candidates.sort(key=lambda x: x["overall_score"] if x.get("overall_score") is not None else -1, reverse=True)

            for candidate in candidates:
                col1, col2 = st.columns([3, 1])

                with col1:
                    if st.button(f"View Details: {candidate['filename']} | Overall Score: {candidate['overall_score']}", 
                                 key=f"{candidate['_id']}_{status}"):
                        st.session_state["selected_candidate_id"] = candidate["_id"]
                        st.rerun()

                with col2:
                    new_status = st.selectbox(
                        "Change Status",
                        KANBAN_STATUSES,
                        index=KANBAN_STATUSES.index(status),
                        key=f"status_{candidate['_id']}"
                    )
                    if new_status != status:
                        job_collection.update_one({"_id": ObjectId(candidate["_id"])}, {"$set": {"status": new_status}})
                        st.session_state["candidates"] = list(job_collection.find())  # Refresh candidates
                        st.rerun()

# ✅ Render Notes Section Separately
if st.session_state["selected_candidate_id"]:
    candidate = next((c for c in st.session_state["candidates"] if c["_id"] == st.session_state["selected_candidate_id"]), None)

    if candidate:
        st.subheader(f"Details for {candidate['candidate_info']['Name']} | {candidate['candidate_info']['Phone']} | {candidate['candidate_info']['Email']} | File name:{candidate['filename']}")
        st.write(candidate["response"])

        candidate_notes = st.text_area("Notes", candidate["notes"], key=f"notes_{st.session_state['selected_candidate_id']}")

        if st.button("Update Notes", key=f"update_notes_{st.session_state['selected_candidate_id']}"):
            update_candidate_notes(candidate, candidate_notes, job_collection)

