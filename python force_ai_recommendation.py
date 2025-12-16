import sqlite3
from datetime import datetime, timedelta
import uuid

def inject_stressed_tool():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    print("🧪 Injecting 'High Risk' Tool for AI Demo...")

    # --- 1. CONFIGURATION ---
    # We use "TW" (Torque Wrench) because the logic assigns it High Criticality
    tool_id = "TW-999" 
    tool_name = "AI Demo Torque Wrench"
    
    # Set a "Healthy" calendar date (6 months from now)
    # The AI will see the high usage and recommend bringing this FORWARD to next month.
    current_due_date = (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d')
    
    # --- 2. CREATE/RESET THE TOOL ---
    # We give it EXTREME stats: 80 checkouts, 600 hours (7.5 hours per use!)
    # This creates a huge "Usage Density" that will trigger the outlier detection.
    cursor.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
    cursor.execute("""
        INSERT INTO tools (id, model, name, status, current_holder, calibration_due, total_checkouts, total_usage_hours)
        VALUES (?, 'M-TW-DIG', ?, 'Available', NULL, ?, 80, 600.0)
    """, (tool_id, tool_name, current_due_date))

    # --- 3. ADD PAST FAILURES (For Robust Model) ---
    # We inject 2 past "Calibration Error" reports. 
    # The Robust AI sees "Past Failures > 0" and penalizes the tool heavily.
    cursor.execute("DELETE FROM issue_reports WHERE tool_id = ?", (tool_id,))
    
    # Report 1
    cursor.execute("""
        INSERT INTO issue_reports (id, tool_id, defect_type, description, status, created_at)
        VALUES (?, ?, 'Calibration Error', 'Drifted out of spec', 'Closed', datetime('now', '-6 months'))
    """, (f"REP-{str(uuid.uuid4())[:8]}", tool_id))
    
    # Report 2
    cursor.execute("""
        INSERT INTO issue_reports (id, tool_id, defect_type, description, status, created_at)
        VALUES (?, ?, 'Physical Damage', 'Dropped on concrete', 'Closed', datetime('now', '-3 months'))
    """, (f"REP-{str(uuid.uuid4())[:8]}", tool_id))

    conn.commit()
    conn.close()
    
    print(f"✅ SUCCESS: Created tool '{tool_id}'.")
    print(f"   - Stats: 80 Checkouts, 600 Hours (High Usage Density)")
    print(f"   - History: 2 Past Failures injected")
    print(f"   - Current Due Date: {current_due_date}")
    print("\n👉 Now go to the Supervisor Dashboard and click 'Run AI Calibration Forecast'.")
    print("   The AI should recommend moving the date FORWARD significantly.")

if __name__ == "__main__":
    inject_stressed_tool()