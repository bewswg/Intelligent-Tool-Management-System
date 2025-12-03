# migrate_db.py
import sqlite3

def migrate_database():
    db_path = 'database.db'
    print(f"🔌 Connecting to {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Check if column already exists to prevent errors
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'last_alert_sent' not in columns:
            print("🚀 Column missing. Applying migration...")
            
            # 2. Add the new column
            cursor.execute("ALTER TABLE transactions ADD COLUMN last_alert_sent DATETIME")
            conn.commit()
            
            print("✅ SUCCESS: Added 'last_alert_sent' column to 'transactions' table.")
        else:
            print("ℹ️  NOTICE: Column 'last_alert_sent' already exists. No changes needed.")

    except sqlite3.OperationalError as e:
        print(f"❌ ERROR: Database operation failed. Details: {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
    finally:
        if conn:
            conn.close()
            print("🔌 Connection closed.")

if __name__ == "__main__":
    migrate_database()