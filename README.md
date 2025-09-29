📰 Death Dashboard – Data Analytics Project


📌 Overview

This project is a data analytics pipeline + dashboard for tracking and visualizing daily reported death cases in India from public news sources.

It consists of three main parts:

Scraper (death_scraper.py) – Collects daily death-related cases from Google News RSS feeds and saves them into scrap_data.json.

MCP Server (death_mcp_server.py) – Wraps the scraper as a tool for integration with MCP-compatible assistants.

Dashboard (app.py) – An interactive Streamlit dashboard that loads cases from JSON (data.json or scrap_data.json) and provides analytics (charts, filters, tables).



📂 Project Structure
Death-Dashboard-DA_Doc2/
│
├─ venv/                     # Python virtual environment
├─ app.py                    # Streamlit dashboard
├─ data.json                 # Sample dataset (for testing)
├─ scrap_data.json           # Auto-generated dataset (from scraper)
├─ death_scraper.py          # Scraper (news -> scrap_data.json)
├─ death_mcp_server.py       # MCP server wrapper around scraper
├─ requirements.txt          # Dependencies list
└─ README.md                 # Project documentation

## ✨ Features
- 📅 **Season → Month Mapping**: Flexible parsing of `start_date` (e.g., *"Summer 2026"* → **July 2026** or **June 2026**).  
- 🗓 **Year Range Selector**: Limit visualizations to a specific year range.  
- 🏢 **Top Companies Ranking**: Bar chart showing companies with the most programs.  
- 📈 **Monthly Timeline**: Stacked area chart of program counts by company.  
- 🔥 **Heatmap**: Compare companies vs months to see hosting intensity.  
- 🌟 **Top-Month per Company**: Automatically highlights each company’s busiest month.  
- 🕵️ **Drill-Down & Comparison**:  
  - Focus on one company.  
  - Compare multiple companies side-by-side.  
- 📊 **Domain & Program Type Breakdown**: Pie chart and bar chart analysis.  
- 📥 **Download CSV**: Export filtered/processed dataset.  

---

The dashboard allows users to:
- Analyze **which companies host the most programs**.
- Identify **seasonal and monthly trends** in hosted programs.
- Compare **domains** (AI, Data Analyst, Python, Go, etc.) and **program types** (Internship, Training, Fellowship).
- Drill down into a **single company** or **compare multiple companies** over time.
- Visualize results with **bar charts, area charts, heatmaps, and pie charts**.

This tool is designed for **students, analysts, or career researchers** who want insights into **how different companies release programs across months and years**.

---

⚙️ Installation

Clone repo / open project

git clone <your-repo-url>
cd Death-Dashboard-DA_Doc2


Create & activate virtual environment

python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate


Install dependencies

pip install -r requirements.txt

📦 Dependencies

requirements.txt includes:

streamlit
pandas
plotly
requests
beautifulsoup4
feedparser
python-dateutil

▶️ Usage
1. Run the Scraper

Interactive scraper that asks for a target date (default: today), collects >=15 cases, and saves them into scrap_data.json.

python death_scraper.py


Logs show RSS queries, articles processed, and accepted records.

2. Run the MCP Server

Wraps the scraper as a MCP tool for assistant integration.
The tool scrape_daily can be invoked to refresh daily records.

python death_mcp_server.py

3. Run the Dashboard

Streamlit dashboard to visualize the cases.

streamlit run app.py


Then open http://localhost:8501
 in your browser.

By default, it loads from scrap_data.json (if available) or data.json (sample).

📊 Dashboard Features

Filters: Date range, states, verified only, age range.

KPIs: Total cases, verified cases, distinct states, average age.

Charts:

Deaths by state (bar chart)

Monthly time series (line chart)

Top causes of death (horizontal bar)

Age distribution (histogram)

Table view with source links.

CSV download of filtered data.

🔄 Workflow

Run death_scraper.py → generates scrap_data.json.

Run app.py → interactive analytics dashboard.

Optionally run death_mcp_server.py → expose scraper via MCP for automation.

🛡️ Notes

The scraper collects publicly available news reports only.

Records include verified flag based on source credibility mapping.

This project is for research, analysis, and educational purposes – not for official reporting.

🚀 Roadmap / Next Steps

 Add India state-level geo-visualization (choropleth map).

 Automate daily scraping with a scheduler (cron/Task Scheduler).

 Enhance NLP extraction for state/district detection.

 Export to SQL/NoSQL databases for long-term analytics.

 Dockerize the project for easier deployment.

 summaries.

