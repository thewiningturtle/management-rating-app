# NOTE: This script is intended to be run in a local environment with required packages installed.
# Required packages: streamlit, PyMuPDF, openai, pandas, python-dotenv, fpdf
# Install using: pip install streamlit pymupdf openai pandas python-dotenv fpdf

import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import ast
import re
from fpdf import FPDF

load_dotenv()

try:
    import streamlit as st
    import fitz  # PyMuPDF
    import openai
except ModuleNotFoundError as e:
    st = None
    fitz = None
    openai = None
    print("[WARNING] Some packages are not available. This script must be run locally with required packages installed.")

if st is None:
    print("[ERROR] Streamlit is not available. Please install with: pip install streamlit pymupdf openai pandas python-dotenv")
else:
    st.set_page_config(layout="wide")
    st.title("📊 Management Rating System")

    uploaded_files = st.file_uploader("Upload One or More Earnings Call Transcripts (PDFs)", type=["pdf"], accept_multiple_files=True)

    categories = [
        "Strategy & Vision", "Execution & Delivery", "Handling Tough Phases",
        "Communication Clarity", "Capital Allocation",
        "Governance & Integrity", "Outlook & Realism"
    ]

    def extract_text_from_pdf(pdf_file):
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        return "".join([page.get_text() for page in doc])

    def extract_quarter_info(text):
        match = re.search(r"Q(\d) FY'? ?(\d{2,4})", text, re.IGNORECASE)
        return f"Q{match.group(1)} FY{match.group(2)}" if match else "Unknown"

    def extract_company_name(text):
        match = re.search(r"(?i)(?:welcome to|from)\s+([A-Z][\w\s&.-]+?)(?:\s+(?:Limited|Ltd\.|Inc\.|Group|Corporation|Corp\.|Bank))?\b", text)
        return match.group(1).strip() if match else "Unknown Company"

    def generate_auto_rating(prompt_text):
        openai.api_key = st.secrets["OPENAI_API_KEY"]

        system_prompt = """
        Evaluate management strictly and unbiasedly based on the following categories (rate 0-5):

        1. Strategy & Vision:
           - Is strategy clear and realistic?
           - Check if the company diversifies unnecessarily into unrelated sectors or raises funds frequently without clear deployment plans.

        2. Execution & Delivery:
           - Does management deliver consistently?
           - Check for overpromising and exaggerating minor developments.

        3. Handling Tough Phases:
           - How effectively does management navigate through challenging times?
           - Check if there are frequent exits of key personnel.

        4. Communication Clarity:
           - Is management clear and transparent in communications?
           - Check for constant media presence without substantial progress and excessive buzzword usage.

        5. Capital Allocation:
           - Evaluate efficiency and transparency of capital allocation.
           - Check specifically for excessive related-party transactions.

        6. Governance & Integrity:
           - Is there robust corporate governance?
           - Highlight issues like high promoter pledging, extravagant promoter lifestyle, or management selling personal stakes.

        7. Outlook & Realism:
           - Are future plans realistic and justified?
           - Check if management consistently talks big or promises unrealistically high performance.

        Provide a detailed justification for each rating. Clearly highlight any red flags identified based on the above checkpoints.

        Output strictly as a dictionary:
        {'ratings': {'category': rating, ...}, 'justification': {'category': 'justification text', ...}, 'red_flags': ['red flag 1', 'red flag 2', ...]}
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ]
        )
        return ast.literal_eval(response.choices[0].message.content)

    def create_pdf_report(company, quarter, ratings, justifications, red_flags):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, f"Management Evaluation Report: {company} - {quarter}", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Arial", size=10)
        for cat in ratings:
            pdf.cell(0, 10, f"{cat}: {ratings[cat]}/5", ln=True)
            pdf.multi_cell(0, 10, f"Justification: {justifications[cat]}")
            pdf.ln(2)

        if red_flags:
            pdf.set_text_color(255, 0, 0)
            pdf.cell(0, 10, "Red Flags Identified:", ln=True)
            pdf.set_text_color(0, 0, 0)
            for flag in red_flags:
                pdf.cell(0, 10, f"- {flag}", ln=True)

        return pdf.output(dest='S').encode('latin1')

    history_file = "management_ratings.csv"
    history_df = pd.read_csv(history_file) if os.path.exists(history_file) else pd.DataFrame(columns=["Date", "Company", "Quarter"] + categories + ["Average"])

    if uploaded_files:
        for uploaded_file in uploaded_files:
            text = extract_text_from_pdf(uploaded_file)
            quarter = extract_quarter_info(text)
            company_name = extract_company_name(text)

            st.subheader(f"Transcript Preview: {uploaded_file.name}")
            st.text_area("Extracted Transcript Text (partial)", text[:3000], height=300)

            if st.button(f"Run AI Evaluation for {uploaded_file.name}"):
                result = generate_auto_rating(text)
                ratings, justifications, red_flags = result['ratings'], result['justification'], result['red_flags']

                avg_score = sum(ratings.values()) / len(categories)
                new_row = {"Date": datetime.now().strftime("%Y-%m-%d"), "Company": company_name, "Quarter": quarter, **ratings, "Average": avg_score}
                history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
                history_df.to_csv(history_file, index=False)

                pdf_data = create_pdf_report(company_name, quarter, ratings, justifications, red_flags)
                st.download_button("📥 Download PDF Report", data=pdf_data, file_name=f"{company_name}_{quarter}_Management_Report.pdf", mime="application/pdf")

    st.subheader("📈 Historical Ratings")
    st.dataframe(history_df, use_container_width=True)
