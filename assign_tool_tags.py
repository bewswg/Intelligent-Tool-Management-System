# assign_tool_tags.py
import sqlite3
import time

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def assign_tag():
    print("🏷️  TOOL TAGGING STATION")
    print("-------------------------")
    
    conn = get_db()
    
    while True:
        # 1. Ask for the Tool ID
        tool_id = input("\n🛠  Enter Tool ID (e.g. TW-001) or 'q' to quit: ").strip().upper()
        if tool_id == 'Q': 
            break
            
        # Check if tool exists
        tool = conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
        if not tool:
            print(f"❌ Error: Tool '{tool_id}' not found in database.")
            continue
            
        print(f"   Found: {tool['name']} (Model: {tool['model']})")
        
        # 2. Ask for the NFC UID
        # (If you have a USB reader, tap it now. If using stickers, read the UID with your phone and type it here)
        nfc_uid = input(f"📲 Enter NFC Sticker UID for {tool_id}: ").strip()
        
        if not nfc_uid:
            print("⚠️ Skipped.")
            continue

        # 3. Save it
        try:
            conn.execute("UPDATE tools SET nfc_id = ? WHERE id = ?", (nfc_uid, tool_id))
            conn.commit()
            print(f"✅ SUCCESS: Linked Sticker '{nfc_uid}' -> Tool '{tool_id}'")
        except Exception as e:
            print(f"❌ Error saving: {e}")

    conn.close()
    print("Exiting...")

if __name__ == "__main__":
    assign_tag()