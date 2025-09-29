# app.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Death Cases Analytics Dashboard", 
    layout="wide",
    page_icon="📊"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .section-header {
        color: #1f77b4;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(path="data.json"):
    with open(path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    df = pd.DataFrame(arr)
    # normalize columns
    if "reported_date" in df.columns:
        df["reported_date"] = pd.to_datetime(df["reported_date"], errors="coerce")
    if "age" in df.columns:
        df["age"] = pd.to_numeric(df["age"], errors="coerce")
    if "verified" not in df.columns:
        df["verified"] = False
    return df

df = load_data()

# Header
st.markdown('<h1 class="main-header">📈 Death Cases Analytics Dashboard</h1>', unsafe_allow_html=True)
st.markdown("""
<div style='text-align: center; margin-bottom: 2rem;'>
    <p>Advanced analytics platform for monitoring and analyzing death case patterns</p>
</div>
""", unsafe_allow_html=True)

# Sidebar filters
with st.sidebar:
    st.markdown("### 🔍 Data Filters")
    
    # Date range
    min_date = df["reported_date"].min().date() if not df["reported_date"].isna().all() else date(2020,1,1)
    max_date = df["reported_date"].max().date() if not df["reported_date"].isna().all() else date.today()
    date_range = st.date_input(
        "Date Range", 
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start, end = date_range
    else:
        start, end = min_date, max_date
    
    # State filter
    states = sorted(df["state"].dropna().unique())
    selected_states = st.multiselect("State", options=states, default=states)
    
    # Advanced filters in expander
    with st.expander("Advanced Filters"):
        verified_only = st.checkbox("Verified only", value=False)
        
        min_age = int(df["age"].min(skipna=True) if not df["age"].isna().all() else 0)
        max_age = int(df["age"].max(skipna=True) if not df["age"].isna().all() else 100)
        age_range = st.slider("Age range", min_value=min_age, max_value=max_age, value=(min_age, max_age))
        
        if "gender" in df.columns:
            genders = sorted(df["gender"].dropna().unique())
            selected_genders = st.multiselect("Gender", options=genders, default=genders)
        else:
            selected_genders = []
    
    # Statistics
    st.markdown("---")
    st.markdown("### 📊 Dataset Overview")
    st.write(f"**Total records:** {len(df):,}")
    st.write(f"**Date range:** {df['reported_date'].min().strftime('%Y-%m-%d') if not df['reported_date'].isna().all() else 'N/A'} to {df['reported_date'].max().strftime('%Y-%m-%d') if not df['reported_date'].isna().all() else 'N/A'}")
    st.write(f"**States covered:** {df['state'].nunique() if 'state' in df.columns else 0}")

# Apply filters
mask = pd.Series(True, index=df.index)
if "reported_date" in df.columns:
    mask &= (df["reported_date"].dt.date >= start) & (df["reported_date"].dt.date <= end)
if selected_states:
    mask &= df["state"].isin(selected_states)
if verified_only:
    mask &= df["verified"] == True
if "age" in df.columns:
    mask &= (df["age"] >= age_range[0]) & (df["age"] <= age_range[1])
if selected_genders and "gender" in df.columns:
    mask &= df["gender"].isin(selected_genders)

fdf = df[mask].copy()

# Enhanced KPIs
st.markdown("## 📈 Key Performance Indicators")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Total Cases", f"{len(fdf):,}")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    verified_count = int(fdf["verified"].sum()) if "verified" in fdf.columns else 0
    verification_rate = (verified_count / len(fdf)) * 100 if len(fdf) > 0 else 0
    st.metric("Verified Cases", f"{verified_count:,}", f"{verification_rate:.1f}%")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    states_count = fdf["state"].nunique() if "state" in fdf.columns else 0
    st.metric("States Covered", states_count)
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    avg_age = round(fdf["age"].mean(skipna=True), 1) if "age" in fdf.columns and not fdf["age"].isna().all() else "N/A"
    st.metric("Average Age", avg_age)
    st.markdown('</div>', unsafe_allow_html=True)

with col5:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    if not fdf.empty and "reported_date" in fdf.columns:
        days_span = (fdf["reported_date"].max() - fdf["reported_date"].min()).days
        daily_rate = len(fdf) / max(days_span, 1)
        st.metric("Daily Rate", f"{daily_rate:.1f}")
    else:
        st.metric("Daily Rate", "N/A")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# NEW: Day-wise Death Rate Chart
st.markdown("## 📅 Daily Death Rate Analysis")

if not fdf.empty and "reported_date" in fdf.columns and not fdf["reported_date"].isna().all():
    # Create daily time series
    daily_series = fdf.set_index("reported_date").resample("D").size().reset_index(name="daily_count")
    daily_series["7_day_avg"] = daily_series["daily_count"].rolling(window=7, min_periods=1).mean()
    daily_series["14_day_avg"] = daily_series["daily_count"].rolling(window=14, min_periods=1).mean()
    
    # Create subplot for daily rates
    fig_daily = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Daily Death Cases', 'Moving Averages (7-day & 14-day)'),
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3]
    )
    
    # Daily counts
    fig_daily.add_trace(
        go.Bar(x=daily_series["reported_date"], y=daily_series["daily_count"], 
               name="Daily Cases", marker_color='lightcoral'),
        row=1, col=1
    )
    
    # Moving averages
    fig_daily.add_trace(
        go.Scatter(x=daily_series["reported_date"], y=daily_series["7_day_avg"], 
                  name="7-day Moving Avg", line=dict(color='blue', width=2)),
        row=2, col=1
    )
    
    fig_daily.add_trace(
        go.Scatter(x=daily_series["reported_date"], y=daily_series["14_day_avg"], 
                  name="14-day Moving Avg", line=dict(color='green', width=2)),
        row=2, col=1
    )
    
    fig_daily.update_layout(height=600, showlegend=True, title_text="Daily Death Rate Analysis")
    fig_daily.update_xaxes(title_text="Date", row=2, col=1)
    fig_daily.update_yaxes(title_text="Cases", row=1, col=1)
    fig_daily.update_yaxes(title_text="Moving Average", row=2, col=1)
    
    st.plotly_chart(fig_daily, use_container_width=True)
    
    # Daily statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Peak Daily Cases", int(daily_series["daily_count"].max()))
    with col2:
        st.metric("Average Daily Cases", f"{daily_series['daily_count'].mean():.1f}")
    with col3:
        st.metric("Current 7-day Avg", f"{daily_series['7_day_avg'].iloc[-1]:.1f}")
    with col4:
        st.metric("Total Days", len(daily_series))
else:
    st.info("No time-series data available for daily analysis.")

st.markdown("---")

# Enhanced Charts Layout
st.markdown("## 📊 Advanced Analytics")

# First row of charts
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### Regional Distribution")
    if not fdf.empty and "state" in fdf.columns:
        by_state = fdf["state"].value_counts().reset_index()
        by_state.columns = ["state", "count"]
        
        fig_state = px.bar(
            by_state, x="state", y="count", text="count",
            title="Cases by State",
            color="count",
            color_continuous_scale="Viridis"
        )
        fig_state.update_layout(
            xaxis_title=None, 
            yaxis_title="Count",
            showlegend=False
        )
        fig_state.update_traces(
            texttemplate='%{text}', 
            textposition='outside',
            marker_line_color='black',
            marker_line_width=0.5
        )
        st.plotly_chart(fig_state, use_container_width=True)
    else:
        st.info("No state data to show.")

with col2:
    st.markdown("### Age Demographics")
    if not fdf.empty and "age" in fdf.columns and not fdf["age"].isna().all():
        # Age distribution with box plot
        fig_age = px.histogram(
            fdf, x="age", nbins=20, 
            title="Age Distribution",
            color_discrete_sequence=['lightseagreen']
        )
        st.plotly_chart(fig_age, use_container_width=True)
        
        # Age statistics
        age_stats = fdf["age"].describe()
        st.metric("Median Age", f"{age_stats['50%']:.1f}")
    else:
        st.info("No age data available.")

# Second row of charts
col3, col4 = st.columns([1, 2])

with col3:
    st.markdown("### Top Causes")
    if not fdf.empty and "cause_of_death" in fdf.columns:
        top_causes = fdf["cause_of_death"].value_counts().nlargest(10).reset_index()
        top_causes.columns = ["cause", "count"]
        
        fig_cause = px.pie(
            top_causes, 
            values="count", 
            names="cause",
            title="Top 10 Causes of Death",
            hole=0.4
        )
        fig_cause.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_cause, use_container_width=True)
    else:
        st.info("No cause data available.")

with col4:
    st.markdown("### Monthly Trend Analysis")
    if not fdf.empty and "reported_date" in fdf.columns and not fdf["reported_date"].isna().all():
        # Monthly time series with trend line
        monthly = fdf.set_index("reported_date").resample("M").size().reset_index(name="count")
        monthly["month"] = monthly["reported_date"].dt.strftime("%Y-%m")
        monthly["trend"] = monthly["count"].rolling(window=3, min_periods=1).mean()
        
        fig_monthly = go.Figure()
        fig_monthly.add_trace(go.Bar(
            x=monthly["month"], y=monthly["count"],
            name="Monthly Cases",
            marker_color='lightsalmon'
        ))
        fig_monthly.add_trace(go.Scatter(
            x=monthly["month"], y=monthly["trend"],
            name="3-Month Trend",
            line=dict(color='red', width=3)
        ))
        fig_monthly.update_layout(
            title="Monthly Cases with Trend Line",
            xaxis_title="Month",
            yaxis_title="Count"
        )
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.info("No time-series data available.")

# Third row: Advanced analytics
st.markdown("## 🔍 Advanced Insights")

col5, col6 = st.columns(2)

with col5:
    st.markdown("### Gender Distribution")
    if not fdf.empty and "gender" in fdf.columns:
        gender_data = fdf["gender"].value_counts().reset_index()
        gender_data.columns = ["gender", "count"]
        
        fig_gender = px.pie(
            gender_data, 
            values="count", 
            names="gender",
            title="Gender Distribution",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_gender, use_container_width=True)
    else:
        st.info("No gender data available.")

with col6:
    st.markdown("### Verification Status")
    if not fdf.empty and "verified" in fdf.columns:
        verified_data = fdf["verified"].value_counts().reset_index()
        verified_data.columns = ["verified", "count"]
        verified_data["verified"] = verified_data["verified"].map({True: "Verified", False: "Unverified"})
        
        fig_verified = px.bar(
            verified_data,
            x="verified",
            y="count",
            title="Verification Status",
            color="verified",
            color_discrete_map={"Verified": "green", "Unverified": "orange"}
        )
        st.plotly_chart(fig_verified, use_container_width=True)
    else:
        st.info("No verification data available.")

st.markdown("---")

# Enhanced Data Explorer
st.markdown("## 📋 Data Explorer")

tab1, tab2, tab3 = st.tabs(["Case Records", "Detailed Analysis", "Export Data"])

with tab1:
    st.markdown("### Case Records Table")
    if not fdf.empty:
        display_cols = ["case_id", "reported_date", "state", "district", "gender", "age", "cause_of_death", "verified", "source_name", "source_url"]
        present = [c for c in display_cols if c in fdf.columns]
        table = fdf[present].sort_values(by="reported_date", ascending=False)
        
        # Add search functionality
        search_term = st.text_input("🔍 Search in table...")
        if search_term:
            mask = table.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            table = table[mask]
        
        st.dataframe(
            table,
            use_container_width=True,
            height=400
        )
        
        # Case details
        st.markdown("### Case Details Viewer")
        if not table.empty:
            sel = st.selectbox("Select case_id for details", options=table["case_id"].tolist())
            selected_row = fdf[fdf["case_id"] == sel].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Basic Information**")
                st.write(f"**Case ID:** {selected_row.get('case_id', '-')}")
                st.write(f"**Reported date:** {selected_row.get('reported_date', '-')}")
                st.write(f"**Location:** {selected_row.get('district', '-')}, {selected_row.get('state', '-')}")
                st.write(f"**Age / Gender:** {selected_row.get('age', '-')} / {selected_row.get('gender', '-')}")
            
            with col2:
                st.markdown("**Case Details**")
                st.write(f"**Cause:** {selected_row.get('cause_of_death', '-')}")
                st.write(f"**Verified:** {selected_row.get('verified', '-')}")
                st.write(f"**Context:** {selected_row.get('reason_or_context', '-')}")
                url = selected_row.get("source_url", "")
                if isinstance(url, str) and url.strip():
                    st.markdown(f"**Source:** [Link]({url})")
    else:
        st.info("No records for the chosen filters.")

with tab2:
    st.markdown("### Statistical Summary")
    if not fdf.empty:
        st.dataframe(fdf.describe(include='all'), use_container_width=True)
    
    st.markdown("### Data Quality Check")
    if not fdf.empty:
        quality_data = {
            'Field': ['Total Records', 'Missing Dates', 'Missing Ages', 'Missing States', 'Missing Causes'],
            'Count': [
                len(fdf),
                fdf['reported_date'].isna().sum(),
                fdf['age'].isna().sum() if 'age' in fdf.columns else 0,
                fdf['state'].isna().sum() if 'state' in fdf.columns else 0,
                fdf['cause_of_death'].isna().sum() if 'cause_of_death' in fdf.columns else 0
            ]
        }
        quality_df = pd.DataFrame(quality_data)
        st.dataframe(quality_df, use_container_width=True)

with tab3:
    st.markdown("### Export Filtered Data")
    st.download_button(
        "📥 Download CSV", 
        data=fdf.to_csv(index=False).encode("utf-8"), 
        file_name=f"death_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    # Data summary for export
    st.markdown("#### Export Summary")
    st.json({
        "total_records": len(fdf),
        "date_range": f"{start} to {end}",
        "states_included": selected_states,
        "export_timestamp": datetime.now().isoformat()
    })

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Death Cases Analytics Dashboard • Built with Streamlit • Data updated automatically</p>
</div>
""", unsafe_allow_html=True)
