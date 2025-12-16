import sqlite3
import pandas as pd
import numpy as np
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from datetime import datetime, timedelta

# Define features (Must match your CSV headers)
MODEL_FEATURES = [
    'Total_Checkouts', 
    'Total_Usage_Hours', 
    'Avg_Duration_Hours', 
    'Days_Since_Last_Cal',
    'Tool_Age_Days', 
    'Unique_Users', 
    'Past_Failures', 
    'Env_Stress_Index', 
    'Criticality_Score'
]

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def train_and_evaluate():
    """
    Trains the model and returns performance metrics.
    """
    csv_path = 'historical_training_data.csv'
    
    if not os.path.exists(csv_path):
        print("⚠️ Training data not found. Run 'generate_training_data.py' first.")
        return None, None

    try:
        # 1. Load Data
        df = pd.read_csv(csv_path)
        X = df[MODEL_FEATURES]
        y = df['Label_Recommended_Days_Until_Cal']

        # 2. Split Data (80% Train, 20% Test) to validate performance
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 3. Train Model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        # Add this after model.fit(X_train, y_train)
        importances = model.feature_importances_
        print("\n🔍 WHAT DRIVES FAILURE? (Feature Importance):")
        for feature, importance in zip(MODEL_FEATURES, importances):
        print(f"   - {feature}: {importance:.2%}")

        # 4. Evaluate (The "Proof" for your Supervisor)
        predictions = model.predict(X_test)
        accuracy = r2_score(y_test, predictions)
        error_margin = mean_absolute_error(y_test, predictions)

        print("-" * 40)
        print(f"🤖 AI MODEL EVALUATION REPORT")
        print(f"   - Training Data: {len(df)} records")
        print(f"   - Model Accuracy (R² Score): {accuracy:.4f} (Target: > 0.80)")
        print(f"   - Avg Prediction Error: ±{error_margin:.1f} days")
        print("-" * 40)

        return model, accuracy

    except Exception as e:
        print(f"❌ Model Training Failed: {e}")
        return None, 0

def generate_forecast():
    """
    Runs the full prediction pipeline.
    """
    # 1. Train & Evaluate
    model, accuracy = train_and_evaluate()
    if not model:
        return {"status": "error", "message": "Model training failed."}

    # 2. Fetch Live Data
    conn = get_db_connection()
    tools = conn.execute("SELECT * FROM tools WHERE status != 'Under Maintenance'").fetchall()
    
    # Fetch failure history
    issues = conn.execute("SELECT tool_id, COUNT(*) as count FROM issue_reports GROUP BY tool_id").fetchall()
    issue_map = {row['tool_id']: row['count'] for row in issues}
    
    conn.close()

    proposals = []
    print(f"🔍 Scanning {len(tools)} live tools for high-stress patterns...")

    for tool in tools:
        try:
            # --- FEATURE MAPPING (Live DB -> Model Input) ---
            total_checkouts = tool['total_checkouts']
            total_hours = tool['total_usage_hours']
            avg_duration = (total_hours / total_checkouts) if total_checkouts > 0 else 0
            
            # Dates
            current_due = datetime.strptime(tool['calibration_due'], '%Y-%m-%d')
            days_since_last = max(0, 180 - (current_due - datetime.now()).days)
            
            # Inferred Metrics (Simulated Logic for Prototype)
            unique_users = int(total_checkouts * 0.4) 
            past_failures = issue_map.get(tool['id'], 0)
            
            # Estimate Age from ID (Simulation Hack)
            try:
                tool_seq = int(tool['id'].split('-')[1]) 
                age_days = 365 + (tool_seq * 10) 
            except:
                age_days = 365

            # Context Mapping (Model -> Stress Score)
            if "TW" in tool['id']: # Torque Wrench (Precision)
                crit_score = 5; env_score = 40
            elif "DR" in tool['id']: # Drill (Vibration)
                crit_score = 3; env_score = 80 
            else:
                crit_score = 2; env_score = 30

            # Create Feature Vector
            features = pd.DataFrame([{
                'Total_Checkouts': total_checkouts,
                'Total_Usage_Hours': total_hours,
                'Avg_Duration_Hours': avg_duration,
                'Days_Since_Last_Cal': days_since_last,
                'Tool_Age_Days': age_days,
                'Unique_Users': unique_users,
                'Past_Failures': past_failures,
                'Env_Stress_Index': env_score,
                'Criticality_Score': crit_score
            }])

            # --- PREDICTION ---
            days_until_cal = model.predict(features)[0]
            recommended_date = datetime.now() + timedelta(days=days_until_cal)
            
            # THRESHOLD LOGIC: Only flag if significantly earlier (e.g. > 2 weeks diff)
            if recommended_date.date() < (current_due.date() - timedelta(days=14)):
                
                # Determine primary reason for the "Why?" column
                reason = "High Usage Intensity"
                if past_failures > 0: reason = "Recurring Defect History"
                elif env_score > 70: reason = "High Environmental Stress"
                elif total_hours > 200: reason = "Excessive Operational Hours"

                proposals.append({
                    "tool_id": tool['id'],
                    "tool_name": tool['name'],
                    "current_date": tool['calibration_due'],
                    "recommended_date": recommended_date.strftime('%Y-%m-%d'),
                    "reason": f"{reason} (AI Confidence: {int(accuracy*100)}%)"
                })

        except Exception as e:
            continue

    return {"status": "success", "proposals": proposals}