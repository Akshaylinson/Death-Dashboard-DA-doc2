
st.set_page_config(page_title="Death Cases Dashboard", layout="wide")

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

st.title("📊 Death Cases — Interactive Dashboard")
st.markdown("Data source: news reports (each record includes `source_name` and `source_url`).")

# Sidebar filters
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

fdf = df[mask].copy()
st.sidebar.write(f"Filtered records: **{len(fdf)}**")

# Layout: KPIs
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total cases", len(fdf))
col2.metric("Verified", int(fdf["verified"].sum()) if "verified" in fdf.columns else 0)
col3.metric("Distinct states", fdf["state"].nunique() if "state" in fdf.columns else 0)
col4.metric("Average age", round(fdf["age"].mean(skipna=True),1) if "age" in fdf.columns else "N/A")

st.markdown("----")

# Two-column charts area
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

# Data table + details panel
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

