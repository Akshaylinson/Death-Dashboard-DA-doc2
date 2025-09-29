# app.py (UPDATED — adds day-wise line chart, top-states trends, weekday heatmap, advanced UI)
import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import numpy as np

st.set_page_config(page_title="Death Cases Dashboard", layout="wide", initial_sidebar_state="expanded")

# ------------------------
# Load data (unchanged behavior)
# ------------------------
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

# ------------------------
# Header + top-line explanation
# ------------------------
st.title("📊 Death Cases — Interactive Dashboard")
st.markdown(
    """
**Purpose:** Daily monitoring and exploratory analysis of reported death cases (news-sourced).  
This view adds daily trends, top-state comparisons, and weekday heatmaps to help identify temporal patterns and spikes.
"""
)

# ------------------------
# Sidebar filters (existing code kept intact)
# ------------------------
with st.sidebar:
    st.header("Filters")
    min_date = df["reported_date"].min().date() if not df["reported_date"].isna().all() else date(2020,1,1)
    max_date = df["reported_date"].max().date() if not df["reported_date"].isna().all() else date.today()
    start = st.date_input("From", value=min_date)
    end = st.date_input("To", value=max_date)
    states = sorted(df["state"].dropna().unique())
    selected_states = st.multiselect("State", options=states, default=states)
    verified_only = st.checkbox("Verified only", value=False)
    min_age = int(df["age"].min(skipna=True) if not df["age"].isna().all() else 0)
    max_age = int(df["age"].max(skipna=True) if not df["age"].isna().all() else 100)
    age_range = st.slider("Age range", min_value=min_age, max_value=max_age, value=(min_age, max_age))
    st.markdown("---")
    st.write(f"Records total: **{len(df)}**")

# Apply filters (existing behavior)
mask = pd.Series(True, index=df.index)
if "reported_date" in df.columns:
    mask &= (df["reported_date"].dt.date >= start) & (df["reported_date"].dt.date <= end)
if selected_states:
    mask &= df["state"].isin(selected_states)
if verified_only:
    mask &= df["verified"] == True
if "age" in df.columns:
    mask &= (df["age"] >= age_range[0]) & (df["age"] <= age_range[1])

fdf = df[mask].copy()
st.sidebar.write(f"Filtered records: **{len(fdf)}**")

# ------------------------
# Extra KPIs (new)
# ------------------------
kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns([1.2,1,1,1,1])

# Total / Verified / Distinct states / Avg age (existing)
kpi_col1.metric("Total cases (filtered)", len(fdf))
kpi_col2.metric("Verified", int(fdf["verified"].sum()) if "verified" in fdf.columns else 0)
kpi_col3.metric("Distinct states", fdf["state"].nunique() if "state" in fdf.columns else 0)
kpi_col4.metric("Average age", round(fdf["age"].mean(skipna=True),1) if "age" in fdf.columns else "N/A")

# New KPI: Day-over-day change for latest day
def compute_latest_dod(series):
    if len(series) < 2:
        return None
    last = series.iloc[-1]
    prev = series.iloc[-2]
    if prev == 0:
        return None
    return (last - prev) / prev * 100

# prepare daily series for KPI (safe handling)
if not fdf.empty and "reported_date" in fdf.columns:
    daily_all = fdf.assign(date_only=fdf["reported_date"].dt.date).groupby("date_only").size().sort_index()
    dod_pct = compute_latest_dod(daily_all.reset_index(name='count')['count']) if len(daily_all) >= 2 else None
    kpi_col5.metric(
        label="Latest day % change (vs prev)",
        value=f"{dod_pct:.1f}%" if dod_pct is not None else "N/A",
        delta=f"{(daily_all.iloc[-1] - daily_all.iloc[-2]) if len(daily_all) >= 2 else 0}"
    )
else:
    kpi_col5.metric("Latest day % change (vs prev)", "N/A")

st.markdown("---")

# ------------------------
# New advanced visualizations section (keeps old visuals unchanged below)
# ------------------------
st.header("Advanced temporal analysis")

tab_daily, tab_states, tab_heatmap = st.tabs(["Daily trend (day-wise)", "Top states — daily trends", "Weekday heatmap"])

# ---------- DAILY TREND TAB ----------
with tab_daily:
    st.subheader("Daily counts with 7-day rolling average & spike detection")
    if fdf.empty or "reported_date" not in fdf.columns:
        st.info("No date data available for daily trend.")
    else:
        # daily series (ensure continuous date index between start/end)
        daily = fdf.assign(date_only=fdf["reported_date"].dt.date).groupby("date_only").size().sort_index()
        # ensure continuous index
        full_idx = pd.date_range(start= pd.to_datetime(start), end=pd.to_datetime(end))
        daily = daily.reindex(full_idx.date, fill_value=0)
        daily.index = pd.to_datetime(daily.index)
        daily = daily.rename_axis("date").reset_index(name="count")

        # rolling mean (7-day)
        daily["rolling_7d"] = daily["count"].rolling(window=7, min_periods=1, center=False).mean()

        # anomaly detection (simple): count > mean + 2*std (over window or whole series)
        global_mean = daily["count"].mean()
        global_std = daily["count"].std() if daily["count"].std() > 0 else 0
        threshold = global_mean + 2 * global_std
        daily["anomaly"] = daily["count"] > threshold

        # build Plotly figure: bar for daily + line for rolling
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily["date"],
            y=daily["count"],
            name="Daily count",
            hovertemplate="%{x|%Y-%m-%d}: %{y}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=daily["date"],
            y=daily["rolling_7d"],
            mode="lines+markers",
            name="7-day rolling mean",
            hovertemplate="%{x|%Y-%m-%d}: %{y:.2f}<extra></extra>",
            line=dict(width=3)
        ))
        # anomalies as scatter
        anomalies = daily[daily["anomaly"]]
        if not anomalies.empty:
            fig.add_trace(go.Scatter(
                x=anomalies["date"],
                y=anomalies["count"],
                mode="markers",
                marker=dict(color="red", size=10, symbol="x"),
                name=f"Spike (>{threshold:.1f})",
                hovertemplate="%{x|%Y-%m-%d}: %{y}<extra></extra>"
            ))

        fig.update_layout(
            title="Day-wise counts (bars) with 7-day rolling average (line)",
            xaxis_title="Date",
            yaxis_title="Count",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Show small table of top anomalies
        if not anomalies.empty:
            with st.expander("View detected anomaly days"):
                anom_tbl = anomalies[["date","count"]].sort_values("count", ascending=False)
                st.table(anom_tbl.style.format({"date": lambda t: t.strftime("%Y-%m-%d")}))

# ---------- TOP STATES TAB ----------
with tab_states:
    st.subheader("Top states — daily trend comparison (top 5)")
    if fdf.empty or "state" not in fdf.columns or "reported_date" not in fdf.columns:
        st.info("Not enough data for state-level trend.")
    else:
        # select top N states by total count in filtered df
        top_n = 5
        top_states = fdf["state"].value_counts().nlargest(top_n).index.tolist()
        # prepare timeseries per state
        fdf_dates = fdf.assign(date_only=fdf["reported_date"].dt.date)
        per_state = fdf_dates[fdf_dates["state"].isin(top_states)].groupby(["date_only","state"]).size().reset_index(name="count")
        # pivot to wide then reindex date range
        pivot = per_state.pivot(index="date_only", columns="state", values="count").fillna(0)
        pivot.index = pd.to_datetime(pivot.index)
        # reindex to continuous dates
        full_range = pd.date_range(start=pd.to_datetime(start), end=pd.to_datetime(end))
        pivot = pivot.reindex(full_range, fill_value=0)
        pivot = pivot.rename_axis('date').reset_index()

        # plotly multi-line (one line per state)
        fig2 = go.Figure()
        for st_name in top_states:
            if st_name in pivot.columns:
                fig2.add_trace(go.Scatter(x=pivot['date'], y=pivot[st_name], mode='lines+markers', name=st_name))
        fig2.update_layout(
            title=f"Daily trend for top {top_n} states",
            xaxis_title="Date",
            yaxis_title="Count",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("**Tip:** Use the date filter on the left to zoom in on a specific window.")

# ---------- WEEKDAY HEATMAP TAB ----------
with tab_heatmap:
    st.subheader("Weekday heatmap (week × weekday) — spot weekly patterns")
    if fdf.empty or "reported_date" not in fdf.columns:
        st.info("No date data to build heatmap.")
    else:
        heat = fdf.assign(date_only=fdf["reported_date"].dt.date)
        heat["date_dt"] = pd.to_datetime(heat["date_only"])
        heat["week"] = heat["date_dt"].dt.isocalendar().week
        heat["year"] = heat["date_dt"].dt.isocalendar().year
        # combine year-week to avoid overlap between years
        heat["year_week"] = heat["year"].astype(str) + "-" + heat["week"].astype(str).str.zfill(2)
        heat_pivot = heat.groupby(["year_week", heat["date_dt"].dt.weekday]).size().unstack(fill_value=0)
        # weekday order 0=Mon .. 6=Sun
        weekday_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        # ensure columns in proper order
        heat_pivot = heat_pivot.reindex(columns=list(range(7)), fill_value=0)
        heat_pivot.columns = weekday_names

        # Plotly heatmap
        fig3 = go.Figure(data=go.Heatmap(
            z=heat_pivot.values,
            x=heat_pivot.columns,
            y=heat_pivot.index,
            colorscale="YlOrRd",
            hoverongaps=False
        ))
        fig3.update_layout(title="Weekly heatmap: counts by weekday (rows = year-week)")
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ------------------------
# Keep your original charts and table unchanged — insert them after the new advanced visuals
# (Below I paste your original layout; nothing removed, only added above.)
# ------------------------

# Two-column charts area (your original content)
left, right = st.columns([2,1])

with left:
    st.subheader("Deaths by State")
    if not fdf.empty and "state" in fdf.columns:
        by_state = fdf["state"].value_counts().reset_index()
        by_state.columns = ["state","count"]
        fig_state = px.bar(by_state, x="state", y="count", text="count", title="Cases by State")
        fig_state.update_layout(xaxis_title=None, yaxis_title="Count")
        st.plotly_chart(fig_state, use_container_width=True)
    else:
        st.info("No state data to show.")

    st.subheader("Monthly Time Series")
    if not fdf.empty and "reported_date" in fdf.columns and not fdf["reported_date"].isna().all():
        ts = fdf.set_index("reported_date").resample("M").size().reset_index(name="count")
        ts["month"] = ts["reported_date"].dt.strftime("%Y-%m")
        fig_ts = px.line(ts, x="month", y="count", title="Monthly cases", markers=True)
        fig_ts.update_layout(xaxis_title="Month", yaxis_title="Count")
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.info("No time-series data available.")

with right:
    st.subheader("Top Causes (Top 10)")
    if not fdf.empty and "cause_of_death" in fdf.columns:
        top_causes = fdf["cause_of_death"].value_counts().nlargest(10).reset_index()
        top_causes.columns = ["cause","count"]
        fig_cause = px.bar(top_causes, x="count", y="cause", orientation="h", title="Top causes")
        fig_cause.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_cause, use_container_width=True)
    else:
        st.info("No cause data available.")

    st.subheader("Age distribution")
    if not fdf.empty and "age" in fdf.columns and not fdf["age"].isna().all():
        fig_age = px.histogram(fdf, x="age", nbins=20, title="Age distribution")
        st.plotly_chart(fig_age, use_container_width=True)
    else:
        st.info("No age data available.")

st.markdown("----")

# Data table + details panel (unchanged)
st.subheader("Case records (table)")
if not fdf.empty:
    display_cols = ["case_id","reported_date","state","district","gender","age","cause_of_death","verified","source_name","source_url"]
    present = [c for c in display_cols if c in fdf.columns]
    table = fdf[present].sort_values(by="reported_date", ascending=False)
    st.dataframe(table, use_container_width=True)

    st.markdown("### Select a case to view details")
    sel = st.selectbox("Choose case_id", options=table["case_id"].tolist())
    selected_row = fdf[fdf["case_id"] == sel].iloc[0]
    st.markdown(f"**Case ID:** {selected_row.get('case_id','-')}")
    st.markdown(f"**Reported date:** {selected_row.get('reported_date','-')}")
    st.markdown(f"**Location:** {selected_row.get('district','-')}, {selected_row.get('state','-')}")
    st.markdown(f"**Age / Gender:** {selected_row.get('age','-')} / {selected_row.get('gender','-')}")
    st.markdown(f"**Cause:** {selected_row.get('cause_of_death','-')}")
    st.markdown(f"**Context:** {selected_row.get('reason_or_context','-')}")
    url = selected_row.get("source_url","")
    if isinstance(url, str) and url.strip():
        st.markdown(f"[Source link]({url})")
else:
    st.info("No records for the chosen filters.")

st.markdown("----")
st.markdown("### Download filtered dataset")
st.download_button("Download CSV", data=fdf.to_csv(index=False).encode("utf-8"), file_name="filtered_deathdata.csv")
st.caption("Tip: To use a map/choropleth you can add a GeoJSON and map state names to GeoJSON IDs.")

