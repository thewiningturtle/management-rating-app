# NOTE: This script is intended to be run in a local environment with required packages installed.
# Required packages: streamlit, PyMuPDF, openai, pandas, python-dotenv
# Install using: pip install streamlit pymupdf openai pandas python-dotenv

import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import ast
import re

# Load environment variables from .env file
load_dotenv()

# Try importing optional packages, but don't exit if missing
try:
    import streamlit as st
    import fitz  # PyMuPDF
    import openai
except ModuleNotFoundError as e:
    st = None
    fitz = None
    openai = None
    print("[WARNING] Some packages are not available. This script must be run locally with required packages installed.")

# If Streamlit isn't available, show an error and exit gracefully
if st is None:
    print("[ERROR] Streamlit is not available. Please install with: pip install streamlit pymupdf openai pandas python-dotenv")
else:
    # Page config
    st.set_page_config(layout="wide")

    # Title
    st.title("📊 Management Rating System - Ganesh Housing Prototype")

    # File uploader
    uploaded_file = st.file_uploader("Upload an Earnings Call Transcript (PDF)", type=["pdf"])

    # Define rating categories
    categories = [
        "Strategy & Vision",
        "Execution & Delivery",
        "Handling Tough Phases",
        "Communication Clarity",
        "Capital Allocation",
        "Governance & Integrity",
        "Outlook & Realism"
    ]

    # Extract text from PDF
    def extract_text_from_pdf(pdf_file):
        if fitz is None:
            st.error("PyMuPDF is not available. Please install it locally with: pip install pymupdf")
            return ""
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text

    # Parse quarter info
    def extract_quarter_info(text):
        match = re.search(r"Q(\d) FY'? ?(\d{2,4})", text, re.IGNORECASE)
        if match:
            return f"Q{match.group(1)} FY{match.group(2)}"
        return "Unknown"

    # Generate auto-ratings using GPT
    def generate_auto_rating(prompt_text):
        if openai is None:
            st.error("OpenAI module not found. Please install it locally with: pip install openai")
            return {}

        openai.api_key = st.secrets["OPENAI_API_KEY"]

        system_prompt = "Rate the company's management on a scale of 0 to 5 for each of the following categories: Strategy & Vision, Execution & Delivery, Handling Tough Phases, Communication Clarity, Capital Allocation, Governance & Integrity, Outlook & Realism. Provide just the scores in a dictionary format."

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ]
            )
            response_text = response.choices[0].message.content
            rating_dict = ast.literal_eval(response_text)
            if not isinstance(rating_dict, dict):
                return {"error": "Parsed response is not a dictionary."}
            return rating_dict
        except Exception as e:
            return {"error": str(e)}

    # Load or initialize history
    history_file = "management_ratings.csv"
    if os.path.exists(history_file):
        history_df = pd.read_csv(history_file)
    else:
        history_df = pd.DataFrame(columns=["Date", "Company", "Quarter"] + categories + ["Average"])

    # Display form if file is uploaded
    if uploaded_file:
        extracted_text = extract_text_from_pdf(uploaded_file)
        quarter = extract_quarter_info(extracted_text)
        st.subheader("Transcript Preview")
        st.text_area("Extracted Transcript Text (partial)", extracted_text[:3000], height=300)

        company_name = st.text_input("Enter Company Name", value="Ganesh Housing")
        mode = st.radio("Choose Rating Mode", ["Auto Rating (AI)", "Manual Rating"])

        if mode == "Manual Rating":
            st.subheader("Rate the Management (0 to 5)")
            st.session_state.rating_scores = {category: st.slider(category, 0, 5, 3) for category in categories}

        else:
            st.subheader("Generating Auto-Rating...")
            if st.button("Run AI Evaluation"):
                with st.spinner("Analyzing transcript with GPT..."):
                    result = generate_auto_rating(extracted_text[:6000])
                    if "error" in result:
                        st.error(f"GPT Error: {result['error']}")
                    else:
                        st.session_state.rating_scores = result
                        st.success("✅ AI-based Ratings Generated!")
                        for cat in categories:
                            st.write(f"**{cat}:** {result[cat]}")

        if st.button("Generate Summary") and "rating_scores" in st.session_state:
            rating_scores = st.session_state.rating_scores
            avg_score = sum(rating_scores.values()) / len(categories)

            st.markdown("---")
            st.header("📋 Management Evaluation Summary")
            for cat in categories:
                st.write(f"**{cat}:** {rating_scores[cat]}/5")

            st.markdown(f"**Overall Management Rating:** {avg_score:.2f} / 5")

            if avg_score >= 4.5:
                st.success("Excellent Management - Highly Consistent & Trustworthy")
            elif avg_score >= 3.5:
                st.info("Good Management - Performing with Stability")
            else:
                st.warning("Needs Further Review - Track Closely")

            # Save result to history
            new_row = {
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Company": company_name,
                "Quarter": quarter
            }
            new_row.update(rating_scores)
            new_row["Average"] = avg_score
            history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
            history_df.to_csv(history_file, index=False)

            # Allow export of latest result
            csv_output = pd.DataFrame([new_row]).to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📤 Download This Rating as CSV",
                data=csv_output,
                file_name=f"{company_name}_management_rating.csv",
                mime="text/csv",
            )

    # Display history
    st.markdown("---")
    st.subheader("📈 Historical Ratings")
    if not history_df.empty:
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Table View", "📊 Trend Chart", "📈 Average Trend", "🗑️ Reset Table"])

        with tab1:
            st.dataframe(history_df, use_container_width=True)

        with tab2:
            for cat in categories:
                trend_data = history_df[["Quarter", cat]].dropna()
                if not trend_data.empty:
                    st.line_chart(trend_data.set_index("Quarter"), height=250, use_container_width=True)

        with tab3:
            chart_data = history_df.groupby("Quarter")["Average"].mean().reset_index()
            st.line_chart(chart_data.set_index("Quarter"))

        with tab4:
            st.warning("⚠️ This will delete all historical records!")
            if st.button("Clear All Ratings"):
                history_df = pd.DataFrame(columns=["Date", "Company", "Quarter"] + categories + ["Average"])
                history_df.to_csv(history_file, index=False)
                st.success("All data cleared successfully.")
    else:
        st.info("No historical data available yet.")
