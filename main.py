from flask import Flask, render_template, jsonify, request, send_file
import pandas as pd
import json
import plotly.express as px
import plotly.io as pio
from datetime import datetime, date, timedelta
import io
import os

app = Flask(__name__)

def load_data(path="data.json"):
    """Load and process the data from JSON file"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            arr = json.load(f)
        df = pd.DataFrame(arr)
        
        # Data preprocessing
        if "reported_date" in df.columns:
            df["reported_date"] = pd.to_datetime(df["reported_date"], errors="coerce")
        if "age" in df.columns:
            df["age"] = pd.to_numeric(df["age"], errors="coerce")
        if "verified" not in df.columns:
            df["verified"] = False
            
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

@app.route('/')
def index():
    """Main dashboard page"""
    df = load_data()
    
    # Get basic stats for the template
    stats = {
        'total_cases': len(df),
        'total_states': df['state'].nunique() if 'state' in df.columns else 0,
        'date_range': {
            'start': df['reported_date'].min().strftime('%Y-%m-%d') if not df.empty and 'reported_date' in df.columns else 'N/A',
            'end': df['reported_date'].max().strftime('%Y-%m-%d') if not df.empty and 'reported_date' in df.columns else 'N/A'
        }
    }
    
    return render_template('index.html', stats=stats)

@app.route('/api/data')
def get_data():
    """API endpoint to get filtered data"""
    df = load_data()
    
    if df.empty:
        return jsonify({'error': 'No data available'}), 500
    
    # Get filters from request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    states = request.args.getlist('states[]')
    verified_only = request.args.get('verified_only') == 'true'
    min_age = request.args.get('min_age')
    max_age = request.args.get('max_age')
    
    # Apply filters
    mask = pd.Series(True, index=df.index)
    
    if start_date and end_date:
        mask &= (df["reported_date"].dt.date >= pd.to_datetime(start_date).date()) & \
                (df["reported_date"].dt.date <= pd.to_datetime(end_date).date())
    
    if states:
        mask &= df["state"].isin(states)
    
    if verified_only:
        mask &= df["verified"] == True
        
    if min_age:
        mask &= df["age"] >= float(min_age)
        
    if max_age:
        mask &= df["age"] <= float(max_age)
    
    filtered_df = df[mask].copy()
    
    # Calculate additional metrics
    total_cases = len(filtered_df)
    verified_cases = int(filtered_df["verified"].sum()) if "verified" in filtered_df.columns else 0
    states_count = filtered_df["state"].nunique() if "state" in filtered_df.columns else 0
    avg_age = round(filtered_df["age"].mean(skipna=True), 1) if "age" in filtered_df.columns and not filtered_df["age"].isna().all() else "N/A"
    
    # Calculate daily rate
    daily_rate = 0
    if not filtered_df.empty and "reported_date" in filtered_df.columns:
        date_range = (filtered_df["reported_date"].max() - filtered_df["reported_date"].min()).days
        daily_rate = round(total_cases / max(date_range, 1), 2)
    
    # Prepare response data
    response = {
        'total_cases': total_cases,
        'verified_cases': verified_cases,
        'states_count': states_count,
        'average_age': avg_age,
        'daily_rate': daily_rate,
        'verification_rate': round((verified_cases / total_cases * 100), 1) if total_cases > 0 else 0,
        'data': filtered_df.to_dict('records')
    }
    
    return jsonify(response)

@app.route('/api/states')
def get_states():
    """API endpoint to get available states"""
    df = load_data()
    states = sorted(df['state'].dropna().unique().tolist()) if 'state' in df.columns else []
    return jsonify(states)

@app.route('/api/charts/daily-rate')
def daily_rate_chart():
    """API endpoint for daily rate chart"""
    df = load_data()
    
    if df.empty:
        return jsonify({'error': 'No data available'}), 500
    
    # Apply filters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    states = request.args.getlist('states[]')
    verified_only = request.args.get('verified_only') == 'true'
    
    mask = pd.Series(True, index=df.index)
    
    if start_date and end_date:
        mask &= (df["reported_date"].dt.date >= pd.to_datetime(start_date).date()) & \
                (df["reported_date"].dt.date <= pd.to_datetime(end_date).date())
    
    if states:
        mask &= df["state"].isin(states)
    
    if verified_only:
        mask &= df["verified"] == True
    
    filtered_df = df[mask].copy()
    
    if filtered_df.empty:
        return jsonify({'error': 'No data after filtering'}), 404
    
    # Create daily time series
    daily_series = filtered_df.set_index("reported_date").resample("D").size().reset_index(name="daily_count")
    daily_series["7_day_avg"] = daily_series["daily_count"].rolling(window=7, min_periods=1).mean()
    
    fig = px.line(daily_series, x="reported_date", y=["daily_count", "7_day_avg"],
                  title="Daily Death Rate Analysis",
                  labels={"value": "Number of Cases", "reported_date": "Date", "variable": "Metric"})
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#333')
    )
    
    return jsonify(pio.to_json(fig))

@app.route('/api/charts/state-distribution')
def state_distribution_chart():
    """API endpoint for state distribution chart"""
    df = load_data()
    
    if df.empty:
        return jsonify({'error': 'No data available'}), 500
    
    # Apply filters
    mask = pd.Series(True, index=df.index)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    states = request.args.getlist('states[]')
    
    if start_date and end_date:
        mask &= (df["reported_date"].dt.date >= pd.to_datetime(start_date).date()) & \
                (df["reported_date"].dt.date <= pd.to_datetime(end_date).date())
    
    if states:
        mask &= df["state"].isin(states)
    
    filtered_df = df[mask].copy()
    
    if filtered_df.empty:
        return jsonify({'error': 'No data after filtering'}), 404
    
    by_state = filtered_df["state"].value_counts().reset_index()
    by_state.columns = ["state", "count"]
    
    fig = px.bar(by_state, x="state", y="count", title="Cases by State",
                 color="count", color_continuous_scale="Viridis")
    
    fig.update_layout(
        xaxis_title="State",
        yaxis_title="Number of Cases",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return jsonify(pio.to_json(fig))

@app.route('/api/charts/causes')
def causes_chart():
    """API endpoint for causes chart"""
    df = load_data()
    
    if df.empty:
        return jsonify({'error': 'No data available'}), 500
    
    # Apply filters
    mask = pd.Series(True, index=df.index)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        mask &= (df["reported_date"].dt.date >= pd.to_datetime(start_date).date()) & \
                (df["reported_date"].dt.date <= pd.to_datetime(end_date).date())
    
    filtered_df = df[mask].copy()
    
    if filtered_df.empty:
        return jsonify({'error': 'No data after filtering'}), 404
    
    top_causes = filtered_df["cause_of_death"].value_counts().nlargest(10).reset_index()
    top_causes.columns = ["cause", "count"]
    
    fig = px.pie(top_causes, values="count", names="cause", 
                 title="Top 10 Causes of Death", hole=0.4)
    
    return jsonify(pio.to_json(fig))

@app.route('/api/charts/age-distribution')
def age_distribution_chart():
    """API endpoint for age distribution chart"""
    df = load_data()
    
    if df.empty:
        return jsonify({'error': 'No data available'}), 500
    
    # Apply filters
    mask = pd.Series(True, index=df.index)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        mask &= (df["reported_date"].dt.date >= pd.to_datetime(start_date).date()) & \
                (df["reported_date"].dt.date <= pd.to_datetime(end_date).date())
    
    filtered_df = df[mask].copy()
    
    if filtered_df.empty or filtered_df['age'].isna().all():
        return jsonify({'error': 'No age data available'}), 404
    
    fig = px.histogram(filtered_df, x="age", nbins=20, 
                       title="Age Distribution",
                       color_discrete_sequence=['#3498db'])
    
    fig.update_layout(
        xaxis_title="Age",
        yaxis_title="Frequency",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return jsonify(pio.to_json(fig))

@app.route('/api/export/csv')
def export_csv():
    """API endpoint to export data as CSV"""
    df = load_data()
    
    if df.empty:
        return jsonify({'error': 'No data available'}), 500
    
    # Apply filters
    mask = pd.Series(True, index=df.index)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    states = request.args.getlist('states[]')
    verified_only = request.args.get('verified_only') == 'true'
    
    if start_date and end_date:
        mask &= (df["reported_date"].dt.date >= pd.to_datetime(start_date).date()) & \
                (df["reported_date"].dt.date <= pd.to_datetime(end_date).date())
    
    if states:
        mask &= df["state"].isin(states)
    
    if verified_only:
        mask &= df["verified"] == True
    
    filtered_df = df[mask].copy()
    
    # Create CSV
    output = io.StringIO()
    filtered_df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'death_analytics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
