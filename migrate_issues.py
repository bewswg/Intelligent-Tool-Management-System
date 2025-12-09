# migrate_issues.py
import sqlite3

def migrate():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    print("🔧 Migrating Database for Issue Tracking...")
    
    # Create the new table
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issue_reports (
                id TEXT PRIMARY KEY,
                tool_id TEXT,
                reporter_id TEXT,
                defect_type TEXT,
                description TEXT,
                status TEXT DEFAULT 'New',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY(tool_id) REFERENCES tools(id),
                FOREIGN KEY(reporter_id) REFERENCES users(id)
            )
        ''')
        print("✅ Table 'issue_reports' created.")
    except Exception as e:
        print(f"⚠️ Table creation error: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()