# NOTE: This script is intended to be run in a local environment with required packages installed.
# Required packages: streamlit, PyMuPDF, openai, pandas, python-dotenv, fpdf, feedparser
# Install using: pip install streamlit pymupdf openai pandas python-dotenv fpdf feedparser

import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import ast
import re
import feedparser
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

    uploaded_files = st.file_uploader("Upload 2 to 4 Earnings Call Transcripts – Current & Previous Quarter (PDFs)", type=["pdf"], accept_multiple_files=True)
    insider_file = st.file_uploader("(Optional) Upload Insider Trading CSV", type="csv")
    leadership_note = st.text_area("Leadership Change Summary (Optional)", placeholder="E.g. CFO resigned in Jan 2024...")
    annual_report = st.file_uploader("(Optional) Upload Annual Report PDF", type=["pdf"])
    news_summary = st.text_area("(Optional) Add News Summary", placeholder="Paste key headlines or press blurbs...")

    categories = [
        "Strategy & Vision", "Execution & Delivery", "Handling Tough Phases",
        "Communication Clarity", "Capital Allocation",
        "Governance & Integrity", "Outlook & Realism"
    ]

    normalization_map = {
        "Operational Performance": "Execution & Delivery",
        "Financial Performance": "Capital Allocation",
        "Strategic Growth Initiatives": "Strategy & Vision",
        "Forward-looking Statements": "Outlook & Realism",
        "Overall Transparency": "Governance & Integrity",
        "Investor Relations": "Governance & Integrity"
    }

    def extract_text_from_pdf(pdf_file):
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        return "".join([page.get_text() for page in doc])

    def extract_quarter_info(text):
        match = re.search(r"Q(\d) FY'? ?(\d{2,4})", text, re.IGNORECASE)
        return f"Q{match.group(1)} FY{match.group(2)}" if match else "Unknown"

    def extract_company_name(text, fallback):
        match = re.search(r"(?:welcome|call of) (?:to )?([A-Z][\w&.,'\-() ]{2,100}?)(?: Limited| Ltd| Incorporated| Inc| Group| Bank| Corp)?[.,\n]", text, re.IGNORECASE)
        if not match:
            match = re.search(r"([A-Z][A-Za-z0-9 &.,\-]+) (?:Limited|Ltd|Bank|Group|Corp|Industries)", text)
        if not match:
            return fallback.replace(".pdf", "").replace("_", " ").title()
        return match.group(1).strip()

    def fetch_recent_news(company):
        rss_url = f"https://news.google.com/rss/search?q={company.replace(' ', '+')}"
        feed = feedparser.parse(rss_url)
        return [entry.title for entry in feed.entries[:3]]

    def parse_insider_flags(df):
        red_flags = []
        for _, row in df.iterrows():
            if row.get("shares_sold", 0) > 100000:
                red_flags.append(f"Large Insider Sale: {row.get('insider_name')} sold {row.get('shares_sold')} shares on {row.get('date')}")
        return red_flags

    def normalize_ratings(ratings):
        normalized = {cat: 0 for cat in categories}  # Default to 0
        for key, value in ratings.items():
            core_key = normalization_map.get(key, key)
            if core_key in normalized:
                normalized[core_key] = value
        return normalized

    def generate_auto_rating(current_text, previous_text, news_snippets, insider_flags, leadership_note):
        openai.api_key = st.secrets["OPENAI_API_KEY"]

        system_prompt = f"""
        You are a forensic analyst evaluating company management based on earnings transcripts, insider trading, and leadership disclosures.

        Step-by-step:
        1. Score the CURRENT quarter across 7 categories (0 to 5).
        2. Compare CURRENT and PREVIOUS transcript: flag any missed delivery, fake optimism, or vague commitments.
        3. Highlight red flags:
           - Insider selling
           - Frequent leadership changes
           - Talk vs. Execution mismatch
           - Buzzword overdose without substance
           - Any media over-exposure
        4. Also use:
           • News: {news_snippets}
           • Insider Flags: {insider_flags}
           • Leadership: {leadership_note}

        Output format:
        {{
          "ratings": {{"category": score}},
          "justification": {{"category": "text"}},
          "red_flags": ["flag1", "flag2"]
        }}
        """

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CURRENT:\n{current_text[:6000]}\n\nPREVIOUS:\n{previous_text[:6000]}"}
            ]
        )

        try:
            return ast.literal_eval(response.choices[0].message.content)
        except Exception as e:
            st.error("⚠️ Failed to parse AI output. Please check model formatting.")
            return {}

    def create_pdf_report(company, quarter, ratings, justifications, red_flags):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, f"Management Evaluation Report: {company} - {quarter}", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Arial", size=10)
        for cat in ratings:
            score_display = ratings[cat] if ratings[cat] is not None else "Not Available"
            pdf.cell(0, 10, f"{cat}: {score_display}/5", ln=True)
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

    if uploaded_files and len(uploaded_files) >= 2:
        st.success(f"{len(uploaded_files)} transcripts uploaded. Comparison ready.")
        uploaded_files = sorted(uploaded_files, key=lambda x: x.name)
        current_file = uploaded_files[-1]
        previous_file = uploaded_files[-2]

        current_text = extract_text_from_pdf(current_file)
        previous_text = extract_text_from_pdf(previous_file)

        quarter = extract_quarter_info(current_text)
        company_name = extract_company_name(current_text, fallback=current_file.name)

        st.subheader("Transcript Preview")
        with st.expander("📄 View Extracted Text", expanded=True):
            st.text_area("Current Quarter Text", current_text[:2500], height=200)
            st.text_area("Previous Quarter Text", previous_text[:2500], height=200)

        if st.button("Run AI Comparison and Rating"):
            news_snippets = fetch_recent_news(company_name) + ([news_summary] if news_summary else [])
            insider_flags = []
            if insider_file:
                insider_df = pd.read_csv(insider_file)
                insider_flags = parse_insider_flags(insider_df)

            result = generate_auto_rating(current_text, previous_text, news_snippets, insider_flags, leadership_note)
            ratings_raw = result.get('ratings', {})
            ratings = normalize_ratings(ratings_raw)
            justifications = result.get('justification', {})
            red_flags = result.get('red_flags', [])

            avg_score = round(sum(ratings.values()) / len(ratings), 4)

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
        st.warning("Please upload at least 2 PDF files for comparison.")

    st.subheader("📈 Historical Ratings")
    if not history_df.empty:
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Table View", "📊 Trend Chart", "📈 Average Trend", "🧹 Reset Table"])

        with tab1:
            st.markdown("### 📋 Ratings Table")
            st.dataframe(history_df.sort_values(by="Date", ascending=False), use_container_width=True, height=500)

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
