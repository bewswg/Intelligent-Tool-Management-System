# clean_slate.py
import sqlite3

def force_return_all():
    conn = sqlite3.connect('database.db')
    
    print("🧹 Cleaning up ghost tools...")
    
    # 1. Force all tools to 'Available'
    conn.execute("UPDATE tools SET status = 'Available', current_holder = NULL WHERE status = 'In Use'")
    
    # 2. Clear the 'last_alert_sent' flag we just added so you can test fresh alerts later
    conn.execute("UPDATE transactions SET last_alert_sent = NULL")
    
    conn.commit()
    conn.close()
    print("✅ All tools forced to 'Available'. Spam should stop immediately.")

if __name__ == "__main__":
    force_return_all()