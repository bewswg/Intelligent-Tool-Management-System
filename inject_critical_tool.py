import sqlite3
from datetime import datetime, timedelta
import uuid
import os

def get_db_connection():
    # Ensure we are connecting to the correct file
    db_path = os.path.join(os.getcwd(), 'database.db')
    return sqlite3.connect(db_path)

def inject_nightmare_tool():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("💉 INJECTING CRITICAL TOOL DATA...")

    # --- 1. DEFINE THE TARGET ---
    # We use "TW" (Torque Wrench) because the AI logic assigns it High Criticality (Score 5/5)
    tool_id = "TW-CRITICAL"
    tool_name = "Safety Hazard Torque Wrench"
    
    # --- 2. THE TRAP (Calendar vs Reality) ---
    # CALENDAR: We set the due date to 6 months from now (180 days).
    # The Supervisor thinks this tool is safe.
    calendar_due_date = (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d')
    
    # REALITY: We give it 1,200 hours of usage. 
    # (Normal tool = 100 hours). This is 12x normal wear.
    # The AI will see this and scream "CALIBRATE NOW".
    
    # Clean up previous attempts
    cursor.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
    cursor.execute("DELETE FROM issue_reports WHERE tool_id = ?", (tool_id,))
    
    # Insert the Tool
    cursor.execute("""
        INSERT INTO tools (id, model, name, status, current_holder, calibration_due, total_checkouts, total_usage_hours)
        VALUES (?, 'M-TW-DIG', ?, 'Available', NULL, ?, 150, 1200.0)
    """, (tool_id, tool_name, calendar_due_date))

    # --- 3. THE "LEMON" FACTOR (Reliability Penalty) ---
    # We inject 5 past failure reports.
    # The Model learns that >2 failures = High Risk. 5 failures = "Do Not Use".
    
    failure_reasons = [
        'Calibration Drift > 5%', 
        'Ratchet Mechanism Jammed', 
        'Dropped from wing height', 
        'Digital Screen Flickering', 
        'Battery Corrosion'
    ]
    
    print(f"   - Injecting {len(failure_reasons)} past failure reports...")
    
    for reason in failure_reasons:
        report_id = f"REP-{str(uuid.uuid4())[:8]}"
        cursor.execute("""
            INSERT INTO issue_reports (id, tool_id, defect_type, description, status, created_at)
            VALUES (?, ?, 'Legacy Defect', ?, 'Closed', datetime('now', '-30 days'))
        """, (report_id, tool_id, reason))

    conn.commit()
    
    # --- 4. VERIFICATION (Prove it worked) ---
    print("\n🔎 VERIFYING DATABASE UPDATE...")
    tool = cursor.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    report_count = cursor.execute("SELECT count(*) FROM issue_reports WHERE tool_id = ?", (tool_id,)).fetchone()[0]
    
    conn.close()
    
    if tool:
        print(f"✅ SUCCESS! Tool '{tool_id}' is in the database.")
        print(f"   - Status:    {tool[3]}")
        print(f"   - Due Date:  {tool[5]} (Far Future)")
        print(f"   - Usage:     {tool[7]} Hours (Critical Level)")
        print(f"   - Failures:  {report_count} Reports (High Risk)")
        print("\n👉 NOW: Go to Supervisor Dashboard > Click 'Run AI Calibration Forecast'.")
        print("   This tool WILL appear with a recommendation to calibrate immediately.")
    else:
        print("❌ ERROR: Data injection failed. Check file permissions.")

if __name__ == "__main__":
    inject_nightmare_tool()