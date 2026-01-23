import sqlite3
import time
import os
import sys

# Configuration
DB_PATH = 'database.db'
REFRESH_RATE = 1.0  # Seconds

def clear_screen():
    # Clears the terminal window
    os.system('cls' if os.name == 'nt' else 'clear')

def get_db():
    return sqlite3.connect(DB_PATH)

def monitor():
    conn = get_db()
    cursor = conn.cursor()
    
    print("👀 STARTING DATABASE MONITOR...")
    time.sleep(1)

    try:
        while True:
            # 1. Fetch Data (Only showing relevant columns for clarity)
            # We filter for tools that are "In Use" OR your specific demo tools (e.g., TW-001)
            # Change 'TW-001' to whatever tool ID you are testing with.
            cursor.execute("""
                SELECT id, name, status, current_holder, total_checkouts 
                FROM tools 
                WHERE status = 'In Use' OR id IN ('TW-001', 'TW-999')
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()

            # 2. Draw the Interface
            clear_screen()
            print("===================================================================")
            print(f"🔴 LIVE DATABASE MONITOR | {time.strftime('%H:%M:%S')}")
            print("===================================================================")
            print(f"{'ID':<10} | {'STATUS':<12} | {'HOLDER':<10} | {'NAME'}")
            print("-" * 65)

            if not rows:
                print("   (No active tools found matching criteria...)")
            
            for r in rows:
                id_, name, status, holder, checks = r
                
                # Visual Highlight for 'In Use'
                status_str = status
                if status == 'In Use':
                    status_str = f"► {status} ◄" 
                
                holder_str = holder if holder else "---"
                
                print(f"{id_:<10} | {status_str:<12} | {holder_str:<10} | {name}")

            print("\n-------------------------------------------------------------------")
            print("Press Ctrl+C to Stop")
            
            # 3. Wait
            time.sleep(REFRESH_RATE)

    except KeyboardInterrupt:
        print("\nStopping Monitor...")
    finally:
        conn.close()

if __name__ == "__main__":
    monitor()