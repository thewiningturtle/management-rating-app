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

    uploaded_files = st.file_uploader("Upload *Two* Earnings Call Transcripts – Current & Previous Quarter (PDFs)", type=["pdf"], accept_multiple_files=True)

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
        match = re.search(r"(?:welcome|call of) (?:to )?([A-Z][\w&.,'\-() ]{2,100}?)(?: Limited| Ltd| Incorporated| Inc| Group| Bank| Corp)?[.,\n]", text, re.IGNORECASE)
        return match.group(1).strip() if match else "Unknown Company"

    def generate_auto_rating(current_text, previous_text):
        openai.api_key = st.secrets["OPENAI_API_KEY"]

        system_prompt = """
        You are a forensic analyst evaluating company management based on their earnings call transcripts.
        Use the CURRENT quarter's transcript in comparison with the PREVIOUS quarter to:

        - Score the CURRENT quarter on:
          1. Strategy & Vision
          2. Execution & Delivery
          3. Handling Tough Phases
          4. Communication Clarity
          5. Capital Allocation
          6. Governance & Integrity
          7. Outlook & Realism

        - Rate each category from 0 to 5.

        - Detect Red Flags such as:
          • Leadership turnover (CEO/CFO resignations)
          • Promoter stake sale
          • Unrealistic forward guidance
          • Overuse of buzzwords without evidence
          • Repeated execution failures

        - Use clear justifications comparing BOTH transcripts.

        Output format:
        {
          'ratings': {'category': score},
          'justification': {'category': 'text'},
          'red_flags': ['flag1', 'flag2']
        }
        """

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CURRENT:\n{current_text[:6000]}\n\nPREVIOUS:\n{previous_text[:6000]}"}
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
            pdf.multi_cell(0, 10, f"Justification: {justifications.get(cat, 'N/A')}")
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

    if uploaded_files and len(uploaded_files) == 2:
        st.success("Two transcripts uploaded. Current + Previous comparison enabled.")
        current_file, previous_file = uploaded_files

        current_text = extract_text_from_pdf(current_file)
        previous_text = extract_text_from_pdf(previous_file)

        quarter = extract_quarter_info(current_text)
        company_name = extract_company_name(current_text)

        st.subheader("Transcript Preview")
        st.text_area("Current Quarter Text (partial)", current_text[:2500], height=250)
        st.text_area("Previous Quarter Text (partial)", previous_text[:2500], height=200)

        if st.button("Run AI Comparison and Rating"):
            result = generate_auto_rating(current_text, previous_text)
            ratings = result.get('ratings', {})
            justifications = result.get('justification', {})
            red_flags = result.get('red_flags', [])

            if not all(cat in ratings and isinstance(ratings[cat], (int, float)) for cat in categories):
                st.error("⚠️ Rating generation incomplete. Some categories are missing. Please retry or verify the AI response.")
            else:
                avg_score = round(sum(ratings.values()) / len(categories), 4)
                if company_name == "Unknown Company":
                    company_name = "Unnamed"

                new_row = {
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Company": company_name,
                    "Quarter": quarter,
                    **ratings,
                    "Average": avg_score
                }

                history_df = history_df[
                    ~((history_df["Company"] == company_name) & (history_df["Quarter"] == quarter))
                ]

                history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
                history_df.to_csv(history_file, index=False)

                pdf_data = create_pdf_report(company_name, quarter, ratings, justifications, red_flags)
                st.download_button("📥 Download PDF Report", data=pdf_data, file_name=f"{company_name}_{quarter}_Management_Report.pdf", mime="application/pdf")

    elif uploaded_files:
        st.warning("Please upload exactly two PDF files – current and previous quarter.")

    st.subheader("📈 Historical Ratings")
    if not history_df.empty:
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Table View", "📊 Trend Chart", "📈 Average Trend", "🧹 Reset Table"])

        with tab1:
            st.dataframe(history_df, use_container_width=True)

        with tab2:
            trend_data = history_df.groupby("Quarter")["Average"].mean().reset_index().sort_values(by="Quarter")
            st.line_chart(trend_data.set_index("Quarter"))

        with tab3:
            st.bar_chart(history_df.groupby("Company")["Average"].mean().sort_values(ascending=False))

        with tab4:
            if st.button("🗑️ Confirm Clear All History"):
                history_df = pd.DataFrame(columns=["Date", "Company", "Quarter"] + categories + ["Average"])
                history_df.to_csv(history_file, index=False)
                st.success("History cleared.")

    else:
        st.info("No historical data available yet.")
