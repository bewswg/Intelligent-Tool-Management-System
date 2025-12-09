import sqlite3

def update_nfc_id():
    # Connect to the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # The exact command to run
    # Note: We use the EXACT format you provided: "0xd4 0x81 0x4d 0x5"
    query = "UPDATE users SET nfc_id = ? WHERE name = ?"
    
    try:
        # Execute the update
        cursor.execute(query, ('0xd4 0x81 0x4d 0x5', 'Thanadol'))
        
        # Check if it actually found the user
        if cursor.rowcount > 0:
            conn.commit()
            print("✅ Success! Card ID assigned to Thanadol.")
        else:
            print("❌ Error: User 'Thanadol' not found in the database. Check the spelling.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_nfc_id()