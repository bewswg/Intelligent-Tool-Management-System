# init_db.py
import sqlite3
from datetime import datetime, timedelta

connection = sqlite3.connect('database.db')
with open('schema.sql') as f:
    connection.executescript(f.read())

cur = connection.cursor()

# === USERS ===
cur.execute("INSERT INTO users (id, name, role, contact_id) VALUES (?, ?, ?, ?)",
            ('USR-001', 'Sarah Adams', 'Supervisor', None))
cur.execute("INSERT INTO users (id, name, role, contact_id) VALUES (?, ?, ?, ?)",
            ('USR-002', 'John Doe', 'Technician', '954223496'))
cur.execute("INSERT INTO users (id, name, role, contact_id) VALUES (?, ?, ?, ?)",
            ('USR-003', 'Maya Lin', 'Technician', None))
cur.execute("INSERT INTO users (id, name, role, contact_id) VALUES (?, ?, ?, ?)",
            ('USR-004', 'David Chen', 'Technician', None))

# === HELPERS FOR DATES ===
today = datetime.today()
in_7_days = (today + timedelta(days=7)).strftime('%Y-%m-%d')
in_30_days = (today + timedelta(days=30)).strftime('%Y-%m-%d')
in_90_days = (today + timedelta(days=90)).strftime('%Y-%m-%d')
in_180_days = (today + timedelta(days=180)).strftime('%Y-%m-%d')
overdue_date = (today - timedelta(days=10)).strftime('%Y-%m-%d')
long_checkout_time = (today - timedelta(hours=10)).strftime('%Y-%m-%d %H:%M:%S')

# === TOOLS ===
tools_data = [
    ('TW-001', 'Digital Torque Wrench (High Use)', 'Available', None, in_30_days, 45, 180.5),
    ('TW-002', 'Digital Torque Wrench', 'Available', None, in_90_days, 12, 48.0),
    ('TW-003', 'Analog Torque Wrench', 'In Use', 'USR-002', in_180_days, 8, 32.0),
    ('TW-004', 'Heavy-Duty Torque Wrench', 'Overdue', None, overdue_date, 20, 80.0),
    ('TW-005', 'Digital Torque Wrench (New)', 'Pending Verification', None, in_30_days, 0, 0.0),
    ('MM-001', 'Digital Multimeter', 'Available', None, in_90_days, 15, 45.0),
    ('MM-002', 'Digital Multimeter', 'Under Maintenance', None, in_180_days, 5, 15.0),
    ('CL-001', 'Current Clamp Meter', 'In Use', 'USR-003', in_30_days, 10, 30.0),
    ('PS-001', 'DC Power Supply', 'Overdue', 'USR-004', overdue_date, 25, 75.0),
    ('BO-001', 'Borescope Camera', 'Available', None, '2026-06-15', 3, 8.2),
    ('VT-001', 'Video Inspection Probe', 'Available', None, '2026-08-20', 2, 5.0),
    ('FLUX-01', 'Flux Detector', 'Under Maintenance', None, '2026-03-10', 18, 54.0),
    ('CAL-001', 'Pressure Calibrator', 'Available', None, in_30_days, 30, 90.0),
    ('GAUGE-01', 'Precision Thickness Gauge', 'Available', None, in_90_days, 7, 21.0),
    ('SOCK-01', 'Socket Wrench Set', 'In Use', 'USR-002', in_180_days, 22, 66.0),
    ('TACH-01', 'Digital Tachometer', 'Overdue', None, overdue_date, 14, 42.0),
    ('DUP-001', 'Torque Wrench', 'Available', None, in_30_days, 5, 20.0),
    ('DUP-002', 'Torque Wrench', 'Available', None, in_90_days, 3, 12.0),
    ('AI-TEST', 'AI Calibration Test Tool', 'Available', None, in_7_days, 50, 200.0),
    ('ALERT-01', 'Overdue Checkout Tool', 'In Use', 'USR-002', in_90_days, 5, 20.0),
    ('ALERT-02', 'Recent Checkout Tool', 'In Use', 'USR-003', in_90_days, 3, 12.0),
    ('ALERT-03', 'Today Checkout Tool', 'In Use', 'USR-004', in_90_days, 1, 4.0),
]

for tool in tools_data:
    cur.execute("""
        INSERT INTO tools (id, name, status, current_holder, calibration_due, total_checkouts, total_usage_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, tool)

# === TRANSACTIONS ===
cur.execute("""
    INSERT INTO transactions (user_id, tool_id, type, timestamp)
    VALUES (?, ?, ?, ?)
""", ('USR-002', 'ALERT-01', 'checkout', long_checkout_time))

cur.execute("""
    INSERT INTO transactions (user_id, tool_id, type, timestamp)
    VALUES (?, ?, ?, datetime('now', '-2 hours'))
""", ('USR-003', 'CL-001', 'checkout'))

cur.execute("""
    INSERT INTO transactions (user_id, tool_id, type, timestamp)
    VALUES (?, ?, ?, datetime('now', '-1 hour'))
""", ('USR-002', 'TW-001', 'checkin'))

# === AUDIT LOG ENTRIES ===
cur.execute('''
    INSERT INTO audit_log (user_id, action, details)
    VALUES (?, ?, ?)
''', ('USR-001', 'EMERGENCY_UNLOCK', '{"reason": "NFC reader failure", "tool_id": "TW-004"}'))

cur.execute('''
    INSERT INTO audit_log (user_id, action, details)
    VALUES (?, ?, ?)
''', ('USR-002', 'TOOL_CHECKOUT', '{"tool_id": "TW-003"}'))

# === PROJECTS ===
projects_data = [
    ('PROJ-A', 'A320 Wing Inspection', 'Perform a detailed visual and torque inspection on the left wing of the A320. Ensure all access panels are secure and torque settings are within tolerance.', '["TW-001", "MM-001", "BO-001"]'),
    ('PROJ-B', 'Engine Overhaul Prep', 'Prepare the CFM56 engine for scheduled overhaul. Perform pre-removal checks and document all sensor readings.', '["CAL-001", "TACH-01", "PS-001"]'),
    ('PROJ-C', 'Landing Gear Service', 'Service and inspect the main landing gear. Check hydraulic fluid levels, inspect for leaks, and verify locking mechanism.', '["GAUGE-01", "FLUX-01", "VT-001"]')
]

for project in projects_data:
    cur.execute("""
        INSERT INTO projects (id, name, briefing, tool_list)
        VALUES (?, ?, ?, ?)
    """, project)

# === COMMIT ===
connection.commit()
connection.close()

print("✅ Database initialized with 23 tools, 4 users, 3 projects, transactions, and audit log.")