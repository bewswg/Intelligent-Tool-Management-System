import sqlite3
import os

def check():
    db_path = 'database.db'
    if not os.path.exists(db_path):
        print(f"❌ ERROR: 'database.db' not found in {os.getcwd()}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Check for the specific demo tool
    tool = conn.execute("SELECT * FROM tools WHERE id = 'TW-999'").fetchone()
    
    if tool:
        print("✅ DATABASE IS WORKING. Found 'TW-999':")
        print(f"   - Usage Hours: {tool['total_usage_hours']} (Should be 800+)")
        print(f"   - Checkouts:   {tool['total_checkouts']}")
        print(f"   - Status:      {tool['status']}")
    else:
        print("❌ DATABASE ERROR: 'TW-999' NOT FOUND.")
        print("   Make sure you are running the injection script in the SAME folder as app.py.")
        
    conn.close()

if __name__ == "__main__":
    check()