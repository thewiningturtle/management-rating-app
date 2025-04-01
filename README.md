# 📊 Management Rating System - Ganesh Housing Prototype

A Streamlit app to evaluate management quality using quarterly earnings call transcripts.

## 🧰 Features
- Upload transcript PDFs
- Rate management manually or with GPT-4 auto-rating
- Save historical scores
- View management trend chart (delta)

## 🚀 Setup Instructions

1. **Clone the repo**
```bash
git clone https://github.com/yourusername/management-rating-app.git
cd management-rating-app
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set your OpenAI API key**
```bash
export OPENAI_API_KEY='your-key-here'  # or use a .env file
```

4. **Run the app**
```bash
streamlit run app.py
```

## 📦 Output
- Automatically saves results to `management_ratings.csv`
- Renders summary and trend charts in-browser
