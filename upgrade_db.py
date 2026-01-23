# upgrade_db.py
import sqlite3

def upgrade():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        # Add the new column to the tools table
        cursor.execute("ALTER TABLE tools ADD COLUMN nfc_id TEXT")
        print("✅ Success: Added 'nfc_id' column to 'tools' table.")
    except sqlite3.OperationalError:
        print("ℹ️ Note: Column 'nfc_id' already exists.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    upgrade()