# app.py
from flask import Flask, render_template, jsonify, request
import sqlite3
import json
import uuid
from datetime import datetime, timedelta
import requests

# --- TELEGRAM INTEGRATION ---
try:
    import telegram_manager
except ImportError:
    telegram_manager = None
    print("⚠️ Warning: telegram_manager.py not found. Telegram alerts will be disabled.")

app = Flask(__name__)

# --- GLOBAL STATE (NFC BRIDGE) ---
latest_nfc_scan = {
    "user_id": None,
    "timestamp": 0
}

# --- DATABASE HELPER ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- AUDIT LOGGER ---
def log_audit_event(user_id, action, details="", conn=None):
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True
    
    try:
        conn.execute('INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)',
                     (user_id, action, details))
        if should_close:
            conn.commit()
    except Exception as e:
        print(f"❌ ERROR: Failed to log audit event: {e}")
    finally:
        if should_close:
            conn.close()

# ==========================================
#               UI ROUTES
# ==========================================

@app.route('/')
def index():
    return render_template('supervisor_ui.html')

@app.route('/station')
def technician_station():
    return render_template('technician_ui.html')

# ==========================================
#           NFC BRIDGE API
# ==========================================

@app.route('/api/nfc/scan', methods=['POST'])
def receive_nfc_scan():
    data = request.get_json()
    card_uid = data.get('uid')
    
    if not card_uid:
        return jsonify({'error': 'No UID provided'}), 400

    # Store this scan GLOBALLY so the UI can find it
    global latest_nfc_scan
    latest_nfc_scan['uid'] = card_uid
    latest_nfc_scan['timestamp'] = datetime.now().timestamp()
    latest_nfc_scan['type'] = 'unknown' # Default

    conn = get_db_connection()
    try:
        # Check if it's a User
        user = conn.execute('SELECT * FROM users WHERE nfc_id = ?', (card_uid,)).fetchone()
        if user:
            latest_nfc_scan['type'] = 'user'
            latest_nfc_scan['id'] = user['id']
            return jsonify({'message': 'User identified', 'user': user['name']})
        
        # Check if it's an existing Tool
        tool = conn.execute('SELECT * FROM tools WHERE nfc_id = ?', (card_uid,)).fetchone()
        if tool:
            latest_nfc_scan['type'] = 'tool'
            latest_nfc_scan['id'] = tool['id']
            return jsonify({'message': 'Tool identified', 'tool': tool['name']})

        # If neither, it's a NEW TAG (Perfect for registration)
        print(f"🆕 NEW TAG DISCOVERED: {card_uid}")
        return jsonify({'message': 'New tag detected', 'uid': card_uid})
    finally:
        conn.close()

@app.route('/api/nfc/poll', methods=['GET'])
def poll_nfc_scan():
    now = datetime.now().timestamp()
    # Return scan if it happened in the last 5 seconds
    if (now - latest_nfc_scan['timestamp'] < 5):
        return jsonify(latest_nfc_scan)
    return jsonify({'type': None})

# ==========================================
#           USER MANAGEMENT
# ==========================================

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return jsonify([dict(row) for row in users])

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(dict(user))

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (id, name, role, contact_id, nfc_id) VALUES (?, ?, ?, ?, ?)',
                     (data['id'], data['name'], data['role'], data.get('contact_id'), data.get('nfc_id')))
        log_audit_event('USR-001', 'USER_CREATED', json.dumps({'id': data['id'], 'role': data['role']}), conn=conn)
        conn.commit()
        return jsonify({'message': 'User created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'User ID already exists'}), 400
    finally:
        conn.close()

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    try:
        active_tools = conn.execute('SELECT count(*) FROM tools WHERE current_holder = ?', (user_id,)).fetchone()[0]
        if active_tools > 0:
            return jsonify({'message': 'Cannot delete: User is currently holding tools'}), 400
        
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        log_audit_event('USR-001', 'USER_DELETED', json.dumps({'user_id': user_id}), conn=conn)
        conn.commit()
        return jsonify({'message': 'User deleted'})
    finally:
        conn.close()

# ==========================================
#           TOOL INVENTORY
# ==========================================

@app.route('/api/tools', methods=['GET'])
def get_tools():
    conn = get_db_connection()
    tools = conn.execute('SELECT * FROM tools').fetchall()
    conn.close()
    return jsonify([dict(row) for row in tools])

@app.route('/api/tools/available', methods=['GET'])
def get_available_tools():
    conn = get_db_connection()
    tools = conn.execute("SELECT * FROM tools WHERE status = 'Available'").fetchall()
    conn.close()
    return jsonify([dict(row) for row in tools])

# In app.py - Replace the existing create_tool function with this:

@app.route('/api/tools', methods=['POST'])
def create_tool():
    data = request.get_json()
    conn = get_db_connection()
    try:
        # 1. DEBUG PRINT: See what the frontend is actually sending
        print(f"📥 RECEIVED DATA: {data}")

        # 2. VALIDATION: Check for missing fields before insertion
        required_fields = ['id', 'name', 'calibration_due']
        for field in required_fields:
            if field not in data or not data[field]:
                print(f"❌ MISSING FIELD: {field}")
                return jsonify({'message': f'Missing required field: {field}'}), 400

        # 3. INSERTION (Fixed to include 'model')
        # We default 'model' to 'Standard' if the frontend didn't send it, 
        # just to stop the database from crashing.
        model_value = data.get('model', 'Standard-Tool') 
        
        conn.execute('''
            INSERT INTO tools (id, model, name, status, calibration_due) 
            VALUES (?, ?, ?, ?, ?)
        ''', (data['id'], model_value, data['name'], data.get('status', 'Available'), data['calibration_due']))
        
        # 4. AUDIT LOG
        log_audit_event('USR-001', 'TOOL_CREATED', json.dumps({'tool_id': data['id']}), conn=conn)
        
        conn.commit()
        print(f"✅ SUCCESS: Created tool {data['id']}")
        return jsonify({'message': 'Tool created'}), 201

    except sqlite3.IntegrityError as e:
        print(f"⚠️ INTEGRITY ERROR: {e}")
        return jsonify({'message': 'Tool ID already exists'}), 400
        
    except Exception as e:
        # This catches the 500 error and prints the REAL reason to your terminal
        print(f"❌ CRITICAL SERVER ERROR: {e}")
        import traceback
        traceback.print_exc() # Prints the full line number of the crash
        return jsonify({'message': str(e)}), 500
        
    finally:
        conn.close()

        
@app.route('/api/tools/batch', methods=['POST'])
def batch_create_tools():
    data = request.get_json()
    base_name = data.get('name')
    model = data.get('model')
    cal_due = data.get('calibration_due')
    tags = data.get('nfc_tags', []) # List of UIDs

    if not tags or not base_name:
        return jsonify({'message': 'Missing data'}), 400

    conn = get_db_connection()
    try:
        created_count = 0
        
        # Find the highest existing ID number to continue sequence (e.g., DR-005 -> DR-006)
        # This is a simple heuristic; for production, use a dedicated sequence table.
        prefix = "TL" # Default prefix
        
        for nfc_id in tags:
            # Generate Unique ID (Simple Random or Sequential)
            tool_id = f"{model[:3].upper()}-{str(uuid.uuid4())[:4].upper()}"
            
            conn.execute('''
                INSERT INTO tools (id, model, name, status, calibration_due, nfc_id) 
                VALUES (?, ?, ?, 'Available', ?, ?)
            ''', (tool_id, model, base_name, cal_due, nfc_id))
            created_count += 1

        log_audit_event('USR-001', 'BATCH_TOOL_CREATE', json.dumps({'count': created_count, 'model': model}), conn=conn)
        conn.commit()
        return jsonify({'message': f'Successfully registered {created_count} tools!'})
        
    except Exception as e:
        print(f"❌ BATCH ERROR: {e}")
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/tools/<tool_id>', methods=['PUT'])
def update_tool(tool_id):
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('UPDATE tools SET name = ?, calibration_due = ? WHERE id = ?',
                 (data['name'], data['calibration_due'], tool_id))
    log_audit_event('USR-001', 'TOOL_UPDATED', json.dumps({'tool_id': tool_id}), conn=conn)
    conn.commit()
    conn.close()
    return jsonify({'message': 'Tool updated'})

@app.route('/api/tools/<tool_id>/status', methods=['PUT'])
def update_tool_status(tool_id):
    data = request.get_json()
    status = data.get('status')
    conn = get_db_connection()
    
    if status == 'Available':
        conn.execute('UPDATE tools SET status = ?, current_holder = NULL WHERE id = ?', (status, tool_id))
    else:
        conn.execute('UPDATE tools SET status = ? WHERE id = ?', (status, tool_id))
        
    log_audit_event('USR-001', 'TOOL_STATUS_CHANGE', json.dumps({'tool_id': tool_id, 'status': status}), conn=conn)
    conn.commit()
    conn.close()
    return jsonify({'message': 'Status updated'})

@app.route('/api/tools/<tool_id>', methods=['DELETE'])
def delete_tool(tool_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tools WHERE id = ?', (tool_id,))
    log_audit_event('USR-001', 'TOOL_DELETED', json.dumps({'tool_id': tool_id}), conn=conn)
    conn.commit()
    conn.close()
    return jsonify({'message': 'Tool deleted'})

@app.route('/api/tools/batch', methods=['PUT'])
def batch_update_tools():
    data = request.get_json()
    tool_ids = data.get('tool_ids', [])
    updates = data.get('updates', {})
    
    conn = get_db_connection()
    try:
        fields = []
        values = []
        
        if 'status' in updates and updates['status']:
            if updates['status'] == 'In Use':
                return jsonify({'message': 'Cannot batch-set status to "In Use" without holder.'}), 400
            fields.append("status = ?")
            values.append(updates['status'])
            if updates['status'] == 'Available':
                fields.append("current_holder = NULL")
        
        if 'calibration_due' in updates and updates['calibration_due']:
            fields.append("calibration_due = ?")
            values.append(updates['calibration_due'])
            
        if not fields:
            return jsonify({'message': 'No valid fields to update'}), 400
             
        sql = f"UPDATE tools SET {', '.join(fields)} WHERE id IN ({','.join(['?']*len(tool_ids))})"
        values.extend(tool_ids)
        
        conn.execute(sql, values)
        log_audit_event('USR-001', 'BATCH_UPDATE', json.dumps({'count': len(tool_ids), 'updates': updates}), conn=conn)
        conn.commit()
        return jsonify({'message': f'Successfully updated {len(tool_ids)} tools'})
    finally:
        conn.close()

# ==========================================
#           PROJECT MANAGEMENT
# ==========================================

@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn = get_db_connection()
    projects = conn.execute('SELECT * FROM projects ORDER BY name').fetchall()
    conn.close()
    return jsonify([dict(row) for row in projects])

@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project_details(project_id):
    conn = get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    conn.close()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(dict(project))

@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    conn = get_db_connection()
    try:
        tool_list_json = json.dumps(data.get('tool_list', []))
        conn.execute('INSERT INTO projects (id, name, briefing, tool_list) VALUES (?, ?, ?, ?)',
                     (data['id'], data['name'], data['briefing'], tool_list_json))
        log_audit_event('USR-001', 'PROJECT_CREATED', json.dumps({'id': data['id']}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Project created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Project ID already exists'}), 400
    finally:
        conn.close()

@app.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    data = request.get_json()
    conn = get_db_connection()
    tool_list_json = json.dumps(data.get('tool_list', []))
    conn.execute('UPDATE projects SET name = ?, briefing = ?, tool_list = ? WHERE id = ?',
                 (data['name'], data['briefing'], tool_list_json, project_id))
    log_audit_event('USR-001', 'PROJECT_UPDATED', json.dumps({'id': project_id}), conn=conn)
    conn.commit()
    conn.close()
    return jsonify({'message': 'Project updated'})

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    log_audit_event('USR-001', 'PROJECT_DELETED', json.dumps({'id': project_id}), conn=conn)
    conn.commit()
    conn.close()
    return jsonify({'message': 'Project deleted'})

# ==========================================
#      TRANSACTIONS (CHECKOUT / CHECKIN)
# ==========================================

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    conn = get_db_connection()
    try:
        query = '''
            SELECT t.timestamp, u.name as user_name, tl.name as tool_name, t.type, t.id
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN tools tl ON t.tool_id = tl.id
            ORDER BY t.timestamp DESC
            LIMIT 10
        '''
        txs = conn.execute(query).fetchall()
        return jsonify([dict(row) for row in txs])
    finally:
        conn.close()

# --- FIXED CHECKOUT LOGIC ---
@app.route('/api/checkout', methods=['POST'])
def checkout_tool():
    data = request.get_json()
    user_id = data.get('user_id')
    tool_id = data.get('tool_id')
    
    conn = get_db_connection()
    try:
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
        if not tool or tool['status'] != 'Available':
            return jsonify({'message': 'Tool unavailable'}), 400

        # UPDATE: Added 'total_checkouts = total_checkouts + 1'
        conn.execute('''
            UPDATE tools 
            SET status = "In Use", 
                current_holder = ?, 
                total_checkouts = total_checkouts + 1 
            WHERE id = ?
        ''', (user_id, tool_id))
        
        conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkout")',
                     (user_id, tool_id))
        
        log_audit_event(user_id, 'TOOL_CHECKOUT', json.dumps({'tool_id': tool_id}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Checkout successful'})
    finally:
        conn.close()

# --- FIXED BATCH CHECKOUT ---
@app.route('/api/projects/<project_id>/checkout', methods=['POST'])
def checkout_project_batch(project_id):
    data = request.get_json()
    user_id = data.get('user_id')
    tool_ids = data.get('tool_ids', [])
    
    conn = get_db_connection()
    try:
        results = {'checked_out': [], 'unavailable': []}
        for tool_id in tool_ids:
            tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
            
            if tool and tool['status'] == 'Available':
                # UPDATE: Added 'total_checkouts = total_checkouts + 1'
                conn.execute('''
                    UPDATE tools 
                    SET status = "In Use", 
                        current_holder = ?, 
                        total_checkouts = total_checkouts + 1 
                    WHERE id = ?
                ''', (user_id, tool_id))
                
                conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkout")',
                             (user_id, tool_id))
                results['checked_out'].append(tool_id)
            else:
                results['unavailable'].append(tool_id)

        log_audit_event(user_id, 'BATCH_CHECKOUT', json.dumps({'project': project_id, 'count': len(results['checked_out'])}), conn=conn)
        conn.commit()
        return jsonify(results)
    finally:
        conn.close()

# --- FIXED CHECKIN LOGIC (USAGE HOURS) ---
@app.route('/api/checkin', methods=['POST'])
def checkin_tool():
    data = request.get_json()
    tool_id = data.get('tool_id')
    report_issue = data.get('report_issue', False)
    
    conn = get_db_connection()
    try:
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
        if not tool:
            return jsonify({'message': 'Tool not found'}), 404

        new_status = 'Under Maintenance' if report_issue else 'Available'
        current_holder = tool['current_holder'] or 'UNKNOWN'

        # 1. CALCULATE DURATION
        # Find the last time this tool was checked out (most recent 'checkout' record)
        last_tx = conn.execute('''
            SELECT timestamp FROM transactions 
            WHERE tool_id = ? AND type = 'checkout' 
            ORDER BY timestamp DESC LIMIT 1
        ''', (tool_id,)).fetchone()

        duration_hours = 0.0
        if last_tx:
            try:
                # SQLite returns strings like "2023-10-25 14:30:00"
                start_time = datetime.strptime(last_tx['timestamp'], '%Y-%m-%d %H:%M:%S')
                end_time = datetime.now()
                # Calculate hours (seconds / 3600)
                duration_hours = (end_time - start_time).total_seconds() / 3600.0
            except Exception as e:
                print(f"Error calculating duration: {e}")

        # 2. UPDATE TOOL (Add duration to total_usage_hours)
        conn.execute('''
            UPDATE tools 
            SET status = ?, 
                current_holder = NULL, 
                total_usage_hours = total_usage_hours + ? 
            WHERE id = ?
        ''', (new_status, duration_hours, tool_id))

        conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkin")',
                     (current_holder, tool_id))
        
        log_audit_event(current_holder, 'TOOL_CHECKIN', json.dumps({'tool_id': tool_id, 'reported_issue': report_issue}), conn=conn)
        
        if report_issue and telegram_manager:
            telegram_manager.send_telegram_message(
                telegram_manager.SUPERVISOR_CHAT_ID,
                f"🚨 **TOOL REPORTED DAMAGED DURING RETURN**\nTool: {tool['name']} ({tool_id})\nUser: {current_holder}"
            )

        conn.commit()
        return jsonify({'message': 'Check-in successful'})
    finally:
        conn.close()

# ==========================================
#           ISSUE TRACKING SYSTEM
# ==========================================

@app.route('/api/issues', methods=['GET'])
def get_issues():
    conn = get_db_connection()
    try:
        issues = conn.execute('''
            SELECT i.*, t.name as tool_name, u.name as reporter_name 
            FROM issue_reports i
            LEFT JOIN tools t ON i.tool_id = t.id
            LEFT JOIN users u ON i.reporter_id = u.id
            ORDER BY i.created_at DESC
        ''').fetchall()
        return jsonify([dict(row) for row in issues])
    finally:
        conn.close()

@app.route('/api/issues', methods=['POST'])
def report_issue():
    data = request.get_json()
    report_id = f"REP-{str(uuid.uuid4())[:8].upper()}"
    
    conn = get_db_connection()
    try:
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (data['tool_id'],)).fetchone()
        if not tool:
            return jsonify({'message': 'Tool not found'}), 404

        if tool['current_holder'] == data['reporter_id']:
            conn.execute('UPDATE tools SET current_holder = NULL WHERE id = ?', (data['tool_id'],))
            conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkin")',
                         (data['reporter_id'], data['tool_id']))
        
        conn.execute("UPDATE tools SET status = 'Under Maintenance' WHERE id = ?", (data['tool_id'],))

        conn.execute('''
            INSERT INTO issue_reports (id, tool_id, reporter_id, defect_type, description, status)
            VALUES (?, ?, ?, ?, ?, 'New')
        ''', (report_id, data['tool_id'], data['reporter_id'], data['defect_type'], data['description']))

        log_audit_event(data['reporter_id'], 'ISSUE_REPORTED', json.dumps({'report_id': report_id}), conn=conn)
        
        if telegram_manager:
            telegram_manager.send_telegram_message(
                telegram_manager.SUPERVISOR_CHAT_ID, 
                f"🚨 **ISSUE REPORTED**\nReport ID: {report_id}\nTool: {tool['name']}\nDefect: {data['defect_type']}\nDesc: {data['description']}"
            )

        conn.commit()
        return jsonify({'message': 'Issue reported', 'report_id': report_id})
    finally:
        conn.close()

@app.route('/api/issues/<report_id>/status', methods=['PUT'])
def update_issue_status(report_id):
    data = request.get_json()
    new_status = data.get('status')
    make_available = data.get('make_tool_available', False)
    
    conn = get_db_connection()
    try:
        updates = "status = ?"
        params = [new_status]
        
        if new_status == 'Closed':
            updates += ", closed_at = CURRENT_TIMESTAMP"
            
        params.append(report_id)
        conn.execute(f"UPDATE issue_reports SET {updates} WHERE id = ?", params)

        if new_status == 'Closed' and make_available:
            report = conn.execute("SELECT tool_id FROM issue_reports WHERE id = ?", (report_id,)).fetchone()
            if report:
                conn.execute("UPDATE tools SET status = 'Available' WHERE id = ?", (report['tool_id'],))

        conn.commit()
        return jsonify({'message': 'Status updated'})
    finally:
        conn.close()

# ==========================================
#           MONITORING & ALERTS
# ==========================================

@app.route('/api/alerts')
def get_alerts():
    conn = get_db_connection()
    try:
        overdue = conn.execute("SELECT * FROM tools WHERE status != 'Under Maintenance' AND date(calibration_due) < date('now')").fetchall()
        
        long_checkout = conn.execute('''
            SELECT t.*, tr.timestamp 
            FROM tools t 
            JOIN transactions tr ON t.id = tr.tool_id 
            WHERE t.status = 'In Use' AND tr.type = 'checkout' 
            AND tr.timestamp < datetime('now', '-8 hours')
        ''').fetchall()
        
        if telegram_manager:
            try:
                telegram_manager.check_and_notify_users()
            except Exception as e:
                print(f"Telegram check failed: {e}")

        return jsonify({
            'overdue': [dict(row) for row in overdue],
            'long_checkout': [dict(row) for row in long_checkout]
        })
    finally:
        conn.close()

@app.route('/api/live-view')
def get_live_view():
    conn = get_db_connection()
    try:
        tools = conn.execute('''
            SELECT 
                t.id as tool_id, 
                t.name as tool_name, 
                t.status, 
                u.name as user_name, 
                u.id as user_id,
                tr.timestamp as checkout_time
            FROM tools t 
            JOIN users u ON t.current_holder = u.id 
            JOIN transactions tr ON tr.tool_id = t.id 
            WHERE t.status = 'In Use' 
            AND tr.id = (
                SELECT MAX(id) FROM transactions 
                WHERE tool_id = t.id AND type = 'checkout'
            )
        ''').fetchall()

        results = []
        for row in tools:
            r = dict(row)
            if r['checkout_time']:
                r['checkout_time'] = r['checkout_time'].replace(" ", "T") + "Z"
            results.append(r)

        return jsonify(results)
    finally:
        conn.close()

@app.route('/api/audit-trail')
def get_audit_trail():
    search = request.args.get('search', '')
    action = request.args.get('action', '')
    
    query = '''
        SELECT a.*, u.name as user_name 
        FROM audit_log a 
        LEFT JOIN users u ON a.user_id = u.id 
        WHERE 1=1
    '''
    params = []
    
    if search: 
        query += " AND (a.details LIKE ? OR u.name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    if action:
        query += " AND a.action = ?"
        params.append(action)
        
    query += " ORDER BY a.timestamp DESC LIMIT 100"
    
    conn = get_db_connection()
    logs = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in logs])

# ==========================================
#           EMERGENCY & UTILS
# ==========================================

@app.route('/api/unlock/emergency', methods=['POST'])
def emergency_unlock():
    data = request.get_json()
    reason = data.get('reason')
    supervisor_id = data.get('supervisor_id', 'USR-001')
    
    if not reason:
        return jsonify({'message': 'Reason required'}), 400

    log_audit_event(supervisor_id, 'EMERGENCY_UNLOCK', json.dumps({'reason': reason}))
    
    if telegram_manager:
        telegram_manager.send_telegram_message(
            telegram_manager.SUPERVISOR_CHAT_ID, 
            f"🚨 **EMERGENCY UNLOCK**\nUser: {supervisor_id}\nReason: {reason}"
        )

    return jsonify({'message': 'Unlock command sent'})

@app.route('/api/calibration/events')
def get_calibration_events():
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)
    
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT calibration_due, COUNT(*) as count
            FROM tools
            WHERE calibration_due >= ? AND calibration_due < ?
            GROUP BY calibration_due
        ''', (start_date, end_date)).fetchall()
        return jsonify({row['calibration_due']: row['count'] for row in rows})
    finally:
        conn.close()

@app.route('/api/calibration/predict', methods=['POST'])
def get_ai_predictions():
    try:
        from predictive_calibration import generate_forecast
        result = generate_forecast()
        return jsonify(result)
    except ImportError:
        return jsonify({'status': 'error', 'message': 'AI Module Missing'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/calibration/apply', methods=['POST'])
def apply_ai_predictions():
    data = request.get_json()
    updates = data.get('updates', [])
    
    conn = get_db_connection()
    try:
        count = 0
        ids = []
        for u in updates:
            conn.execute('UPDATE tools SET calibration_due = ? WHERE id = ?', (u['new_date'], u['tool_id']))
            ids.append(u['tool_id'])
            count += 1
            
        log_audit_event('USR-001', 'AI_CALIBRATION_UPDATE', json.dumps({'count': count, 'tools': ids}), conn=conn)
        conn.commit()
        return jsonify({'message': f'Updated {count} tools'})
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)