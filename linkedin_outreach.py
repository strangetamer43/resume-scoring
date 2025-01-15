from dotenv import load_dotenv
load_dotenv()
import streamlit as st
import os
import google.generativeai as genai

# Set up the API key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize the Gemini model
model = genai.GenerativeModel('gemini-1.5-flash')

# Streamlit app layout
st.title("Outreach Message Generator")
st.write("Enter the details below to generate a professional outreach message.")

# User inputs
linkedin_page = st.text_input("Company LinkedIn Page URL")
company_website = st.text_input("Company Website URL")
target_user_linkedin = st.text_input("Target User's LinkedIn Account URL")

if st.button("Generate Message"):
    if linkedin_page and company_website and target_user_linkedin:
        # Create the prompt for the model
        prompt = (
            "You are a Sales representative for Usurp HRTech Solutions private limited Usurp aims to make hiring simple, seamless and hassle free. We believe in the motto It's not about finding more candidates, it's about finding the RIGHT one. We take up your hiring challenges, allowing you to do what you do best! We understand that you require speed and efficiency, inherently leading to lower down times and quicker onboardings, reducing operational pain and loss of resources. Our extensive screening process goes beyond just resumes and dives deep into the applicants' skills, behaviour, culture and mindset. This helps us close even the most challenging profiles. Using cutting edge tech platforms coupled with psychology and current recruitment strategies, we achieve our targets well in advance. who will create a professional yet catchy outreach message "
            "based on the provided company website, company LinkedIn page, and the target person's LinkedIn account.\n"
            f"Company LinkedIn Page: {linkedin_page}\n"
            f"Company Website: {company_website}\n"
            f"Target User's LinkedIn Account: {target_user_linkedin}\n"
        )

        # Generate content using the model
        response = model.generate_content(prompt)
        
        # Display the generated message
        st.subheader("Generated Outreach Message:")
        st.write(response.text)
    else:
        st.error("Please fill in all fields.")
