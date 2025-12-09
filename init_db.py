# init_db.py
import sqlite3
import json
import random
from datetime import datetime, timedelta

connection = sqlite3.connect('database.db')
cursor = connection.cursor()

# 1. DROP Tables
cursor.executescript("""
    DROP TABLE IF EXISTS issue_reports;
    DROP TABLE IF EXISTS transactions;
    DROP TABLE IF EXISTS projects;
    DROP TABLE IF EXISTS audit_log;
    DROP TABLE IF EXISTS tools;
    DROP TABLE IF EXISTS users;
    
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        contact_id TEXT,
        nfc_id TEXT
    );

    CREATE TABLE tools (
        id TEXT PRIMARY KEY,
        model TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        current_holder TEXT,
        calibration_due TEXT,
        total_checkouts INTEGER DEFAULT 0,
        total_usage_hours REAL DEFAULT 0.0
    );

    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        tool_id TEXT NOT NULL,
        type TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_alert_sent DATETIME,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(tool_id) REFERENCES tools(id)
    );

    CREATE TABLE issue_reports (
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
    );

    CREATE TABLE projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        briefing TEXT NOT NULL,
        tool_list TEXT NOT NULL
    );
    
    CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_id TEXT,
        action TEXT NOT NULL,
        details TEXT
    );
""")

# 2. SEED USERS (Added more techs to simulate a busy shift)
users = [
    ('USR-001', 'Sarah Adams', 'Supervisor', '954223496', None),
    ('USR-002', 'John Doe', 'Technician', '954223496', '0xd4 0x81 0x4d 0x5'), # Matches NFC
    ('USR-003', 'Maya Lin', 'Technician', None, None),
    ('USR-004', 'David Chen', 'Technician', None, None),
    ('USR-005', 'Thanadol', 'Technician', None, '0xd4 0x81 0x4d 0x5'),
    ('USR-006', 'Alex Rogan', 'Technician', None, None),
    ('USR-007', 'Ellen Ripley', 'Technician', None, None),
    ('USR-008', 'Cooper', 'Technician', None, None)
]
cursor.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)

# 3. DATE HELPERS
today = datetime.today()
cal_good = (today + timedelta(days=120)).strftime('%Y-%m-%d')
cal_soon = (today + timedelta(days=15)).strftime('%Y-%m-%d')
cal_bad  = (today - timedelta(days=5)).strftime('%Y-%m-%d')

# 4. GENERATE TOOLS (The Fleet)
tools_data = []

def generate_tools(prefix, model, name, count):
    for i in range(1, count + 1):
        tool_id = f"{prefix}-{i:03d}" # e.g., DR-001, DR-002
        
        # 90% chance tool is perfect, 10% chance it has issues
        r = random.random()
        if r > 0.95:
            status = 'Under Maintenance'
            cal = cal_good
        elif r > 0.90:
            status = 'Overdue'
            cal = cal_bad
        else:
            status = 'Available'
            cal = cal_good if r > 0.2 else cal_soon
            
        tools_data.append((tool_id, model, name, status, None, cal))

# --- FLEET CONFIGURATION ---
# We need enough for 20 concurrent users. 
# If everyone needs a drill, we need 20+ drills.

generate_tools('DR', 'M-DRILL', 'Pneumatic Drill', 25)           # 25 Drills
generate_tools('RT', 'M-RIVET', 'Rivet Gun (Pneumatic)', 25)     # 25 Rivet Guns
generate_tools('TW', 'M-TW-DIG', 'Digital Torque Wrench', 25)    # 25 Torque Wrenches
generate_tools('MM', 'M-MULTI', 'Digital Multimeter', 25)        # 25 Multimeters
generate_tools('CAL', 'M-CAL', 'Pressure Calibrator', 20)        # 20 Calibrators
generate_tools('SK', 'M-SOCK', 'Socket Wrench Set', 20)          # 20 Socket Sets
generate_tools('CL', 'M-CLAMP', 'Current Clamp Meter', 10)       # 10 Clamp Meters
generate_tools('BO', 'M-BORE', 'Borescope Camera', 8)            # 8 Borescopes
generate_tools('VT', 'M-VID', 'Video Inspection Probe', 5)       # 5 Video Probes

# Add a few specific ones for testing alerts/specific scenarios
tools_data.append(('ALERT-01', 'M-TEST', 'Overdue Checkout Tool', 'In Use', 'USR-002', cal_good))
tools_data.append(('AI-TEST', 'M-AI', 'AI Calibration Test Tool', 'Available', None, (today + timedelta(days=7)).strftime('%Y-%m-%d')))

# Insert all generated tools
for tool in tools_data:
    cursor.execute("""
        INSERT INTO tools (id, model, name, status, current_holder, calibration_due)
        VALUES (?, ?, ?, ?, ?, ?)
    """, tool)

# 5. SEED PROJECTS (Full List 001-017)
projects_data = [
    ('PROJ-001', 'T-Profile with Cutout', 'Standard operating procedure for T-Profile with Cutout', 
     json.dumps(["M-MULTI", "M-TW-DIG", "M-RIVET"])),

    ('PROJ-002', 'Cutting Exercise', 'Standard operating procedure for Cutting Exercise', 
     json.dumps(["M-CAL", "M-MULTI", "M-RIVET", "M-DRILL"])),

    ('PROJ-003', 'Riveting by Hand', 'Standard operating procedure for Riveting by Hand', 
     json.dumps(["M-CAL", "M-TW-DIG", "M-DRILL", "M-RIVET"])),

    ('PROJ-004', 'Sandwich', 'Standard operating procedure for Sandwich', 
     json.dumps(["M-DRILL", "M-MULTI", "M-RIVET", "M-TW-DIG"])),

    ('PROJ-005', 'Sheet Metal Shape', 'Standard operating procedure for Sheet Metal Shape', 
     json.dumps(["M-DRILL", "M-MULTI", "M-RIVET"])),

    ('PROJ-006', 'Screw Installation', 'Standard operating procedure for Screw Installation', 
     json.dumps(["M-CAL", "M-DRILL", "M-TW-DIG"])),

    ('PROJ-007', 'Drill Panel 3/4/5', 'Standard operating procedure for Drill Panel 3/4/5', 
     json.dumps(["M-DRILL", "M-MULTI", "M-TW-DIG", "M-CAL"])),

    ('PROJ-008', 'Third Hand Assembly', 'Standard operating procedure for Third Hand Assembly', 
     json.dumps(["M-RIVET", "M-DRILL", "M-MULTI"])),

    ('PROJ-009', 'Drill Panel 1', 'Standard operating procedure for Drill Panel 1', 
     json.dumps(["M-TW-DIG", "M-RIVET", "M-MULTI"])),

    ('PROJ-010', 'Drill Plate Aluminium', 'Standard operating procedure for Drill Plate Aluminium', 
     json.dumps(["M-RIVET", "M-TW-DIG"])),

    ('PROJ-011', 'Drill Panel 2', 'Standard operating procedure for Drill Panel 2', 
     json.dumps(["M-RIVET", "M-CAL", "M-TW-DIG"])),

    ('PROJ-012', 'Drill Plate Plexiglass', 'Standard operating procedure for Drill Plate Plexiglass', 
     json.dumps(["M-RIVET", "M-TW-DIG"])),

    ('PROJ-013', 'Structure Project', 'Standard operating procedure for Structure Project', 
     json.dumps(["M-CAL", "M-MULTI", "M-DRILL"])),

    ('PROJ-014', 'Hi-Lok', 'Standard operating procedure for Hi-Lok', 
     json.dumps(["M-CAL", "M-RIVET"])),

    ('PROJ-015', 'Hydraulic Jack Project', 'Standard operating procedure for Hydraulic Jack Project', 
     json.dumps(["M-MULTI", "M-TW-DIG", "M-DRILL"])),

    ('PROJ-016', 'SPS- Stabilised Power Supply', 'Standard operating procedure for SPS', 
     json.dumps(["M-MULTI", "M-CAL", "M-TW-DIG", "M-RIVET"])),

    ('PROJ-017', 'FMP - Flap Mechanism Project', 'Standard operating procedure for FMP', 
     json.dumps(["M-RIVET", "M-MULTI"]))
]

for project in projects_data:
    cursor.execute("INSERT INTO projects (id, name, briefing, tool_list) VALUES (?, ?, ?, ?)", project)

# 6. SEED AUDIT LOG
cursor.execute("INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)", 
               ('USR-001', 'SYSTEM_RESET', f'Mass Inventory Generated: {len(tools_data)} Tools'))

connection.commit()
connection.close()

print(f"✅ Database initialized with {len(tools_data)} tools (High Volume) and {len(projects_data)} projects.")