# predictive_calibration.py
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta
import json

def train_and_predict():
    # Load data
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("""
        SELECT 
            id,
            total_checkouts,
            total_usage_hours,
            julianday('now') - julianday(calibration_due) AS days_since_cal,
            CASE 
                WHEN name LIKE '%Torque%' THEN 'torque'
                WHEN name LIKE '%Multimeter%' THEN 'electrical'
                ELSE 'other'
            END AS tool_category
        FROM tools
        WHERE status != 'Under Maintenance'
    """, conn)
    conn.close()

    # Skip if not enough data
    if len(df) < 5:
        print("⚠️ Not enough data to run AI forecast.")
        return

    # Create target: days until next calibration (assume 180-day cycle)
    df['target_days'] = 180 - df['days_since_cal'].clip(lower=0)

    # One-hot encode category
    df = pd.get_dummies(df, columns=['tool_category'])

    # Features
    feature_cols = ['total_checkouts', 'total_usage_hours'] + \
                   [col for col in df.columns if col.startswith('tool_category_')]
    X = df[feature_cols]
    y = df['target_days']

    # Train model
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)

    # Predict
    predictions = model.predict(X)
    results = []
    for i, row in df.iterrows():
        next_cal_days = max(7, int(predictions[i]))  # min 7 days
        next_cal_date = (datetime.now() + timedelta(days=next_cal_days)).strftime('%Y-%m-%d')
        results.append((next_cal_date, row['id']))

    # Update DB
    conn = sqlite3.connect('database.db')
    conn.executemany("UPDATE tools SET calibration_due = ? WHERE id = ?", results)
    conn.commit()
    conn.close()

    print(f"✅ AI Calibration Forecast: Updated {len(results)} tools.")
    return results