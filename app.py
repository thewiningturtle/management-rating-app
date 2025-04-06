# NOTE: This script is intended to be run in a local environment with required packages installed.
# Required packages: streamlit, PyMuPDF, openai, pandas, python-dotenv
# Install using: pip install streamlit pymupdf openai pandas python-dotenv

import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import ast
import re
from collections import defaultdict

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
        if fitz is None:
            st.error("PyMuPDF is not available. Please install it locally with: pip install pymupdf")
            return ""
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        return "".join([page.get_text() for page in doc])

    def extract_quarter_info(text):
        match = re.search(r"Q(\d) FY'? ?(\d{2,4})", text, re.IGNORECASE)
        return f"Q{match.group(1)} FY{match.group(2)}" if match else "Unknown"

    def extract_company_name(text):
        match = re.search(r"(?i)(?:welcome to|from)\s+([A-Z][\w\s&.-]+?)(?:\s+(?:Limited|Ltd\.|Inc\.|Group|Corporation|Corp\.|Bank))?\b", text)
        if match:
            return match.group(1).strip()
        return "Unknown Company"

    def generate_auto_rating(prompt_text):
        if openai is None:
            st.error("OpenAI module not found. Please install it locally with: pip install openai")
            return {}

        openai.api_key = st.secrets["OPENAI_API_KEY"]

        system_prompt = """
You are a forensic financial analyst with expertise in evaluating company management through earnings call transcripts.

Your job is to analyze the following transcript and rate the company’s management (scale of 0 to 5) on these 7 categories. Be strict, unbiased, and highlight any red flags:

1. Strategy & Vision – Is their plan well-articulated and future-aligned?
2. Execution & Delivery – Do they demonstrate actual results?
3. Handling Tough Phases – Are they transparent and accountable during challenges?
4. Communication Clarity – Is their language clear, direct, and data-supported?
5. Capital Allocation – Is there logic behind their capital usage (buybacks, dividends, lending)?
6. Governance & Integrity – Do they demonstrate honesty, control, and compliance?
7. Outlook & Realism – Are projections realistic or overly optimistic?

If anything seems evasive, vague, inconsistent, or risky – give low scores and note it.

Output strictly in a Python dictionary like:
{
    "Strategy & Vision": 3,
    "Execution & Delivery": 2,
    ...
}
Do not add explanations, comments, or text outside the dictionary.
"""

        chunks = [prompt_text[i:i+4000] for i in range(0, len(prompt_text), 4000)]
        combined_scores = defaultdict(list)

        for chunk in chunks:
            try:
                response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk}
                    ]
                )
                response_text = response.choices[0].message.content.strip()
                try:
                    rating_dict = ast.literal_eval(response_text)
                except Exception as parse_error:
                    return {"error": f"Parsing failed: {str(parse_error)}", "raw": response_text}

                if isinstance(rating_dict, dict):
                    for k, v in rating_dict.items():
                        combined_scores[k].append(v)
            except Exception as e:
                return {"error": str(e)}

        return {k: min(v) for k, v in combined_scores.items() if k in categories}

    history_file = "management_ratings.csv"
    history_df = pd.read_csv(history_file) if os.path.exists(history_file) else pd.DataFrame(columns=["Date", "Company", "Quarter"] + categories + ["Average"])

    if uploaded_files:
        if "ratings" not in st.session_state:
            st.session_state["ratings"] = {}

        for uploaded_file in uploaded_files:
            extracted_text = extract_text_from_pdf(uploaded_file)
            quarter = extract_quarter_info(extracted_text)
            company_name = extract_company_name(extracted_text)
            st.subheader(f"Transcript Preview: {uploaded_file.name}")
            st.text_area("Extracted Transcript Text (partial)", extracted_text[:3000], height=300)

            mode = st.radio(f"Choose Rating Mode for {uploaded_file.name}", ["Auto Rating (AI)", "Manual Rating"], key=uploaded_file.name)

            if mode == "Manual Rating":
                st.subheader("Rate the Management (0 to 5)")
                rating_scores = {category: st.slider(category, 0, 5, 3, key=f"{uploaded_file.name}_{category}") for category in categories}
                st.session_state.ratings[uploaded_file.name] = rating_scores

            else:
                st.subheader("Generating Auto-Rating...")
                if st.button(f"Run AI Evaluation for {uploaded_file.name}"):
                    with st.spinner("Analyzing transcript with GPT..."):
                        result = generate_auto_rating(extracted_text)
                        if "error" in result:
                            st.error(f"GPT Error: {result['error']}")
                            if "raw" in result:
                                st.code(result["raw"], language="python")
                        else:
                            st.success("✅ AI-based Ratings Generated!")
                            for cat in categories:
                                st.write(f"**{cat}:** {result[cat]}")
                            st.session_state.ratings[uploaded_file.name] = result

            if st.button(f"Generate Summary for {uploaded_file.name}"):
                if uploaded_file.name in st.session_state.ratings:
                    rating_scores = st.session_state.ratings[uploaded_file.name]
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

                    new_row = {
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Company": company_name,
                        "Quarter": quarter
                    }
                    new_row.update(rating_scores)
                    new_row["Average"] = avg_score
                    history_df = pd.concat([history_df, pd.DataFrame([new_row])], ignore_index=True)
                    history_df.to_csv(history_file, index=False)

                    csv_output = pd.DataFrame([new_row]).to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📤 Download This Rating as CSV",
                        data=csv_output,
                        file_name=f"{company_name}_management_rating.csv",
                        mime="text/csv",
                    )
                else:
                    st.warning("⚠️ Please run AI Evaluation or Manual Rating before generating summary.")

    st.markdown("---")
    st.subheader("📈 Historical Ratings")
    if not history_df.empty:
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Table View", "📊 Trend Chart", "📈 Average Trend", "🗑️ Reset Table"])
        with tab1:
            st.dataframe(history_df, use_container_width=True)
        with tab2:
            for cat in categories:
                if "Quarter" in history_df.columns:
                    trend_data = history_df[["Quarter", cat]].dropna()
                    if not trend_data.empty:
                        st.line_chart(trend_data.set_index("Quarter"), height=250, use_container_width=True)
        with tab3:
            if "Quarter" in history_df.columns:
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
