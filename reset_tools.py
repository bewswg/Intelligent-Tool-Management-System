import sqlite3

def reset_inventory():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    print("🧹 Cleaning up stale checkouts...")
    
    # 1. Mark all tools as Available
    cursor.execute("UPDATE tools SET status = 'Available', current_holder = NULL")
    
    # 2. Clear the transaction alerts so they don't fire again immediately
    cursor.execute("UPDATE transactions SET last_alert_sent = NULL")
    
    conn.commit()
    conn.close()
    print("✅ All tools forced to 'Available'. Alerts should stop.")

if __name__ == "__main__":
    reset_inventory()