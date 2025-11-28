# predictive_calibration.py
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta

def generate_forecast():
    conn = sqlite3.connect('database.db')
    
    # Fetch data including current due date and name
    df = pd.read_sql_query("""
        SELECT id, name, calibration_due, total_checkouts, total_usage_hours
        FROM tools
        WHERE status != 'Under Maintenance'
    """, conn)
    conn.close()

    if len(df) < 5:
        return {"status": "error", "message": "Insufficient data (need at least 5 tools to train model)."}

    # --- 1. Feature Engineering ---
    # Calculate "Usage Density" (Avg hours per checkout). 
    # High density means the tool is used intensively when taken out.
    df['usage_density'] = df['total_usage_hours'] / (df['total_checkouts'] + 1)
    
    # --- 2. The "AI" Logic ---
    # We train the model to understand the relationship between general usage and density
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    X = df[['total_checkouts', 'total_usage_hours', 'usage_density']]
    
    # We fit the model to predict "usage_density" based on the other factors
    # This helps identify tools that are statistical outliers in how hard they are worked
    model.fit(X, df['usage_density']) 
    
    # Get the "predicted stress" score
    df['predicted_stress'] = model.predict(X)
    
    proposals = []
    
    # --- 3. Generate Proposals ---
    # Calculate the 80th percentile threshold for "High Stress"
    high_stress_threshold = df['predicted_stress'].quantile(0.8)

    for i, row in df.iterrows():
        try:
            current_due = datetime.strptime(row['calibration_due'], '%Y-%m-%d')
        except ValueError:
            continue # Skip invalid dates

        # If stress is high (> 80th percentile), suggest earlier calibration
        if row['predicted_stress'] > high_stress_threshold:
            # Suggest bringing it forward by 30 days
            new_date = current_due - timedelta(days=30)
            
            # Safety: Don't suggest a date in the past. If calculated date is past, set to 7 days from now.
            if new_date < datetime.now():
                new_date = datetime.now() + timedelta(days=7)
            
            # Only propose if the new date is actually different/earlier
            if new_date.date() < current_due.date():
                proposals.append({
                    "tool_id": row['id'],
                    "tool_name": row['name'],
                    "current_date": row['calibration_due'],
                    "recommended_date": new_date.strftime('%Y-%m-%d'),
                    "reason": f"High Usage Intensity (Score: {row['predicted_stress']:.2f})"
                })

    return {"status": "success", "proposals": proposals}