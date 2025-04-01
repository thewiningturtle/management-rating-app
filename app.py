# NOTE: This script is intended to be run in a local environment with required packages installed.
# Required packages: streamlit, PyMuPDF, openai, pandas, python-dotenv
# Install using: pip install streamlit pymupdf openai pandas python-dotenv

import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

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

    # Initialize rating dictionary
    rating_scores = {category: 0 for category in categories}
    extracted_text = ""

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

    # Generate auto-ratings using GPT
    @st.cache(show_spinner=False)
    def generate_auto_rating(prompt_text):
        if openai is None:
            st.error("OpenAI module not found. Please install it locally with: pip install openai")
            return {}
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            st.error("OPENAI_API_KEY environment variable not set.")
            return {}

        system_prompt = "Rate the company's management on a scale of 0 to 5 for each of the following categories: Strategy & Vision, Execution & Delivery, Handling Tough Phases, Communication Clarity, Capital Allocation, Governance & Integrity, Outlook & Realism. Provide just the scores in a dictionary format."

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ]
        )
        return eval(response.choices[0].message['content'])

    # Load or initialize history
    history_file = "management_ratings.csv"
    if os.path.exists(history_file):
        history_df = pd.read_csv(history_file)
    else:
        history_df = pd.DataFrame(columns=["Date", "Company"] + categories + ["Average"])

    # Display form if file is uploaded
    if uploaded_file:
        extracted_text = extract_text_from_pdf(uploaded_file)
        st.subheader("Transcript Preview")
        st.text_area("Extracted Transcript Text (partial)", extracted_text[:3000], height=300)

        company_name = st.text_input("Enter Company Name", value="Ganesh Housing")
        mode = st.radio("Choose Rating Mode", ["Auto Rating (AI)", "Manual Rating"])

        if mode == "Manual Rating":
            st.subheader("Rate the Management (0 to 5)")
            for category in categories:
                rating_scores[category] = st.slider(category, 0, 5, 3)
        else:
            st.subheader("Generating Auto-Rating...")
            with st.spinner("Analyzing transcript with GPT..."):
                rating_scores = generate_auto_rating(extracted_text[:6000])

        if st.button("Generate Summary"):
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
            new_row = {"Date": datetime.now().strftime("%Y-%m-%d"), "Company": company_name}
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
        st.dataframe(history_df.tail(10))

        chart_data = history_df.groupby("Date")["Average"].mean().reset_index()
        st.line_chart(chart_data.set_index("Date"))
    else:
        st.info("No historical data available yet.")
