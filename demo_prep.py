# demo_prep.py
import sqlite3
from datetime import datetime, timedelta

def prepare_demo_data():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    print("🎭 Setting the stage for the Demo...")

    # --- 1. SETUP FOR "FOD ALERT" (Telegram & Dashboard) ---
    # Create a transaction from 9 hours ago so it triggers the "> 8 Hours" alert
    # We use 'TW-001' which is usually available
    nine_hours_ago = (datetime.now() - timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE tools SET status = 'In Use', current_holder = 'USR-002' WHERE id = 'TW-001'")
    cursor.execute("""
        INSERT INTO transactions (user_id, tool_id, type, timestamp)
        VALUES ('USR-002', 'TW-001', 'checkout', ?)
    """, (nine_hours_ago,))
    print(f"✅ Created FOD Risk: TW-001 held for 9 hours by John Doe.")

    # --- 2. SETUP FOR "CALIBRATION OVERDUE" (Dashboard) ---
    # Set a tool's due date to yesterday
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute("UPDATE tools SET status = 'Overdue', calibration_due = ? WHERE id = 'CAL-001'", (yesterday,))
    print(f"✅ Created Overdue Tool: CAL-001 expired yesterday.")

    # --- 3. SETUP FOR "AI PREDICTION" ---
    # The AI looks for "Usage Density" (High Hours / Low Checkouts).
    # We will create a "Stressed Tool" that fits this pattern perfectly.
    cursor.execute("DELETE FROM tools WHERE id = 'AI-DEMO-OBJ'")
    cursor.execute("""
        INSERT INTO tools (id, model, name, status, current_holder, calibration_due, total_checkouts, total_usage_hours)
        VALUES ('AI-DEMO-OBJ', 'M-TW-DIG', 'High-Stress Torque Wrench', 'Available', NULL, ?, 10, 500.0)
    """, ((datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d'),))
    # 500 hours / 10 checkouts = 50 hours per use (Very High Intensity) -> AI should flag this.
    print(f"✅ Created AI Candidate: AI-DEMO-OBJ (High Usage Intensity).")

    # --- 4. SETUP FOR CALENDAR ---
    # Ensure there is a tool due TODAY so you can demo the "Mark Calibrated" feature
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("UPDATE tools SET calibration_due = ?, status = 'Available' WHERE id = 'MM-001'", (today,))
    print(f"✅ Created Calendar Task: MM-001 due today.")

    conn.commit()
    conn.close()
    print("\n🚀 DEMO DATA READY! Start app.py now.")

if __name__ == "__main__":
    prepare_demo_data()