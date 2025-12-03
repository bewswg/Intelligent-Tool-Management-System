# app.py
from flask import Flask, render_template, jsonify, request
import sqlite3
import json
from datetime import datetime, timedelta
import requests

# Import the new Telegram Manager
# (Make sure telegram_manager.py is in the same folder)
try:
    import telegram_manager
except ImportError:
    telegram_manager = None
    print("⚠️ Warning: telegram_manager.py not found. Telegram alerts will be disabled.")

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Logger with Shared Connection Support
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

# === UI ROUTES ===
@app.route('/')
def index():
    return render_template('supervisor_ui.html')

@app.route('/station')
def technician_station():
    return render_template('technician_ui.html')

# === CORE API ENDPOINTS ===

# --- Users Management ---
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    try:
        users = conn.execute('SELECT * FROM users').fetchall()
        return jsonify([dict(row) for row in users])
    finally:
        conn.close()

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if user is None:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(dict(user))
    finally:
        conn.close()

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (id, name, role, contact_id) VALUES (?, ?, ?, ?)',
                     (data['id'], data['name'], data['role'], data.get('contact_id')))
        log_audit_event('USR-001', 'USER_CREATED', json.dumps({'id': data['id'], 'role': data['role']}), conn=conn)
        conn.commit()
        return jsonify({'message': 'User created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'User ID already exists'}), 400
    finally:
        conn.close()

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    conn = get_db_connection()
    try:
        conn.execute('UPDATE users SET name = ?, role = ? WHERE id = ?',
                     (data['name'], data['role'], user_id))
        log_audit_event('USR-001', 'USER_UPDATED', json.dumps({'user_id': user_id, 'updates': data}), conn=conn)
        conn.commit()
        return jsonify({'message': 'User updated'})
    finally:
        conn.close()

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    try:
        active_tools = conn.execute('SELECT count(*) FROM tools WHERE current_holder = ?', (user_id,)).fetchone()[0]
        if active_tools > 0:
            return jsonify({'message': 'Cannot delete user: They are currently holding tools.'}), 400

        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        log_audit_event('USR-001', 'USER_DELETED', json.dumps({'user_id': user_id}), conn=conn)
        conn.commit()
        return jsonify({'message': 'User deleted'})
    finally:
        conn.close()

# --- Tools Management ---
@app.route('/api/tools', methods=['GET'])
def get_tools():
    conn = get_db_connection()
    try:
        tools = conn.execute('SELECT * FROM tools').fetchall()
        return jsonify([dict(row) for row in tools])
    finally:
        conn.close()

@app.route('/api/tools/available', methods=['GET'])
def get_available_tools():
    conn = get_db_connection()
    try:
        tools = conn.execute("SELECT * FROM tools WHERE status = 'Available'").fetchall()
        return jsonify([dict(row) for row in tools])
    finally:
        conn.close()

@app.route('/api/tools/<tool_id>', methods=['GET'])
def get_single_tool(tool_id):
    conn = get_db_connection()
    try:
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
        if tool is None:
            return jsonify({'error': 'Tool not found'}), 404
        return jsonify(dict(tool))
    finally:
        conn.close()

@app.route('/api/tools', methods=['POST'])
def create_tool():
    data = request.get_json()
    status = data.get('status', 'Available')
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO tools (id, name, status, calibration_due) VALUES (?, ?, ?, ?)',
                     (data['id'], data['name'], status, data['calibration_due']))
        log_audit_event('USR-001', 'TOOL_CREATED', json.dumps({'tool_id': data['id'], 'status': status}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Tool created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Tool ID already exists'}), 400
    finally:
        conn.close()

@app.route('/api/tools/<tool_id>', methods=['PUT'])
def update_tool(tool_id):
    data = request.get_json()
    conn = get_db_connection()
    try:
        conn.execute('UPDATE tools SET name = ?, calibration_due = ? WHERE id = ?',
                     (data['name'], data['calibration_due'], tool_id))
        log_audit_event('USR-001', 'TOOL_UPDATED', json.dumps({'tool_id': tool_id, 'updates': data}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Tool updated'})
    finally:
        conn.close()

@app.route('/api/tools/<tool_id>/status', methods=['PUT'])
def update_tool_status(tool_id):
    data = request.get_json()
    conn = get_db_connection()
    try:
        status = data.get('status')
        if status == 'Available':
            conn.execute('UPDATE tools SET status = ?, current_holder = NULL WHERE id = ?', (status, tool_id))
        else:
            conn.execute('UPDATE tools SET status = ? WHERE id = ?', (status, tool_id))
        log_audit_event('USR-001', 'TOOL_STATUS_CHANGE', json.dumps({'tool_id': tool_id, 'new_status': status}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Status updated'})
    finally:
        conn.close()

@app.route('/api/tools/<tool_id>', methods=['DELETE'])
def delete_tool(tool_id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM tools WHERE id = ?', (tool_id,))
        log_audit_event('USR-001', 'TOOL_DELETED', json.dumps({'tool_id': tool_id}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Tool deleted'})
    finally:
        conn.close()

@app.route('/api/tools/batch', methods=['PUT'])
def batch_update_tools():
    data = request.get_json()
    tool_ids = data.get('tool_ids', [])
    updates = data.get('updates', {})
    
    if not tool_ids:
        return jsonify({'message': 'No tool IDs provided'}), 400
        
    conn = get_db_connection()
    try:
        fields = []
        values = []
        
        if 'status' in updates and updates['status']:
            if updates['status'] == 'In Use':
                return jsonify({'message': 'Cannot batch-set status to "In Use" without assigning a holder.'}), 400
            
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

# --- AI Calibration Logic ---

@app.route('/api/calibration/predict', methods=['POST'])
def get_ai_predictions():
    try:
        from predictive_calibration import generate_forecast
        result = generate_forecast()
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/calibration/apply', methods=['POST'])
def apply_ai_predictions():
    data = request.get_json()
    approved_updates = data.get('updates', [])
    
    if not approved_updates:
        return jsonify({'message': 'No updates provided'}), 400

    conn = get_db_connection()
    try:
        count = 0
        tool_ids = []
        for update in approved_updates:
            conn.execute('UPDATE tools SET calibration_due = ? WHERE id = ?',
                         (update['new_date'], update['tool_id']))
            tool_ids.append(update['tool_id'])
            count += 1
            
        log_audit_event('USR-001', 'AI_CALIBRATION_UPDATE', 
                       json.dumps({'count': count, 'tools': tool_ids}), 
                       conn=conn)
        
        conn.commit()
        return jsonify({'message': f'Successfully updated {count} tools based on AI recommendation.'})
    finally:
        conn.close()

# --- Transactions ---
@app.route('/api/checkout', methods=['POST'])
def checkout_tool():
    data = request.get_json()
    user_id = data.get('user_id')
    tool_id = data.get('tool_id')
    if not user_id or not tool_id:
        return jsonify({'message': 'Missing user_id or tool_id'}), 400

    conn = get_db_connection()
    try:
        tool = conn.execute('''
            SELECT *, date(calibration_due) < date('now') as is_overdue
            FROM tools WHERE id = ?
        ''', (tool_id,)).fetchone()
        if not tool:
            return jsonify({'message': 'Tool not found'}), 400
        if tool['status'] != 'Available':
            return jsonify({'message': 'Tool is not available'}), 400
        if tool['is_overdue']:
            return jsonify({'message': 'Tool is overdue for calibration'}), 400

        conn.execute('UPDATE tools SET status = "In Use", current_holder = ? WHERE id = ?',
                     (user_id, tool_id))
        conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkout")',
                     (user_id, tool_id))
        
        log_audit_event(user_id, 'TOOL_CHECKOUT', json.dumps({'tool_id': tool_id}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Checkout successful'}), 200
    finally:
        conn.close()

@app.route('/api/checkin', methods=['POST'])
def checkin_tool():
    data = request.get_json()
    tool_id = data.get('tool_id')
    report_issue = data.get('report_issue', False)
    if not tool_id:
        return jsonify({'message': 'Missing tool_id'}), 400

    conn = get_db_connection()
    try:
        tool = conn.execute('SELECT * FROM tools WHERE id = ? AND status = "In Use"', (tool_id,)).fetchone()
        if not tool:
            return jsonify({'message': 'Tool not checked out or already returned'}), 400

        new_status = "Under Maintenance" if report_issue else "Available"
        current_holder = tool['current_holder']

        conn.execute('UPDATE tools SET status = ?, current_holder = NULL WHERE id = ?',
                     (new_status, tool_id))
        conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkin")',
                     (current_holder, tool_id))
        
        log_audit_event(current_holder, 'TOOL_CHECKIN',
                        json.dumps({'tool_id': tool_id, 'report_issue': report_issue}), conn=conn)
        conn.commit()
        return jsonify({'message': 'Check-in successful'}), 200
    finally:
        conn.close()

# --- Projects ---
@app.route('/api/projects')
def get_projects():
    conn = get_db_connection()
    try:
        projects = conn.execute('SELECT id, name FROM projects ORDER BY name').fetchall()
        return jsonify([dict(row) for row in projects])
    finally:
        conn.close()

@app.route('/api/projects/<project_id>')
def get_project_details(project_id):
    conn = get_db_connection()
    try:
        project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        return jsonify(dict(project))
    finally:
        conn.close()

@app.route('/api/projects/<project_id>/checkout', methods=['POST'])
def checkout_project_batch(project_id):
    data = request.get_json()
    user_id = data.get('user_id')
    tool_ids = data.get('tool_ids', [])
    if not user_id:
        return jsonify({'message': 'Missing user_id'}), 400

    conn = get_db_connection()
    try:
        results = {'checked_out': [], 'unavailable': [], 'errors': []}
        for tool_id in tool_ids:
            tool = conn.execute('''
                SELECT *, date(calibration_due) < date('now') as is_overdue
                FROM tools WHERE id = ?
            ''', (tool_id,)).fetchone()

            if not tool:
                results['errors'].append(f"Tool {tool_id} not found")
                continue
            if tool['status'] != 'Available':
                results['unavailable'].append(tool_id)
                continue
            if tool['is_overdue']:
                results['unavailable'].append(tool_id)
                continue

            conn.execute('UPDATE tools SET status = "In Use", current_holder = ? WHERE id = ?',
                         (user_id, tool_id))
            conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkout")',
                         (user_id, tool_id))
            log_audit_event(user_id, 'BATCH_CHECKOUT', json.dumps({'project_id': project_id, 'tool_id': tool_id}), conn=conn)
            results['checked_out'].append(tool_id)

        conn.commit()
        return jsonify(results)
    finally:
        conn.close()

# --- Alerts & Monitoring (with Telegram Hook) ---
@app.route('/api/alerts')
def get_alerts():
    conn = get_db_connection()
    try:
        overdue = conn.execute('''
            SELECT * FROM tools
            WHERE status != 'Under Maintenance'
            AND date(calibration_due) < date('now')
        ''').fetchall()

        long_checkout = conn.execute('''
            SELECT t.*, tr.timestamp
            FROM tools t
            JOIN transactions tr ON t.id = tr.tool_id
            WHERE t.status = 'In Use' AND tr.type = 'checkout'
            AND tr.timestamp < datetime('now', '-8 hours')
        ''').fetchall()

        # TRIGGER TELEGRAM ALERTS (Passive check)
        if telegram_manager:
            try:
                telegram_manager.check_and_notify_users()
            except Exception as e:
                print(f"Telegram Trigger Failed: {e}")

        return jsonify({
            'overdue': [dict(row) for row in overdue],
            'long_checkout': [dict(row) for row in long_checkout]
        })
    finally:
        conn.close()

@app.route('/api/transactions')
def get_transactions():
    conn = get_db_connection()
    try:
        transactions = conn.execute('''
            SELECT t.id, u.name as user_name, tl.name as tool_name, t.type, t.timestamp
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            JOIN tools tl ON t.tool_id = tl.id
            ORDER BY t.timestamp DESC
            LIMIT 20
        ''').fetchall()
        return jsonify([dict(row) for row in transactions])
    finally:
        conn.close()

@app.route('/api/live-view')
def get_live_view():
    conn = get_db_connection()
    try:
        live_tools = conn.execute('''
            SELECT
                t.id as tool_id,
                t.name as tool_name,
                t.status as tool_status,
                u.id as user_id,
                u.name as user_name,
                MAX(tr.timestamp) as checkout_time,
                (strftime('%s', 'now') - strftime('%s', MAX(tr.timestamp))) as seconds_held
            FROM tools t
            LEFT JOIN users u ON t.current_holder = u.id
            JOIN transactions tr ON t.id = tr.tool_id
            WHERE t.status = 'In Use' AND tr.type = 'checkout'
            GROUP BY t.id
            ORDER BY checkout_time ASC
        ''').fetchall()
        return jsonify([dict(row) for row in live_tools])
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
        query += ' AND (a.details LIKE ? OR a.action LIKE ? OR u.name LIKE ?)'
        term = f'%{search}%'
        params.extend([term, term, term])
    if action:
        query += ' AND a.action = ?'
        params.append(action)
        
    query += ' ORDER BY a.timestamp DESC LIMIT 100'
    conn = get_db_connection()
    try:
        logs = conn.execute(query, params).fetchall()
        return jsonify([dict(row) for row in logs])
    finally:
        conn.close()

@app.route('/api/calibration/events')
def get_calibration_events():
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    conn = get_db_connection()
    try:
        rows = conn.execute('''
            SELECT calibration_due, COUNT(*) as count
            FROM tools
            WHERE calibration_due >= ? AND calibration_due < ?
            GROUP BY calibration_due
        ''', (start, end)).fetchall()
        return jsonify({row['calibration_due']: row['count'] for row in rows})
    finally:
        conn.close()

@app.route('/api/unlock/emergency', methods=['POST'])
def emergency_unlock():
    data = request.get_json()
    reason = data.get('reason')
    supervisor_id = data.get('supervisor_id', 'USR-001')
    if not reason:
        return jsonify({'message': 'Reason is required'}), 400
    
    log_audit_event(supervisor_id, 'EMERGENCY_UNLOCK',
                    json.dumps({'reason': reason, 'timestamp': datetime.now().isoformat()}))
    
    # TELEGRAM: Critical Alert
    if telegram_manager:
        telegram_manager.send_telegram_message(
            telegram_manager.SUPERVISOR_CHAT_ID, 
            f"🚨 **EMERGENCY UNLOCK TRIGGERED**\nUser: {supervisor_id}\nReason: {reason}"
        )

    return jsonify({'message': 'Unlock command sent'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')