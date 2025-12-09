# migrate_nfc.py
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE users ADD COLUMN nfc_id TEXT")
    print("✅ Added 'nfc_id' column to users table.")
    
    # FOR TESTING: Let's assign your specific card to a user
    # Replace 'YOUR_CARD_UID' with the actual ID your friend sees (e.g., "0x04 0xA2...")
    # cursor.execute("UPDATE users SET nfc_id = 'YOUR_CARD_UID' WHERE id = 'USR-002'")
    
    conn.commit()
except Exception as e:
    print(f"Info: {e}")

conn.close()