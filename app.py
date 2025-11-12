# app.py
from flask import Flask, render_template, jsonify, request
import sqlite3
import json
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# === AUDIT LOGGING HELPER ===
def log_audit_event(user_id, action, details=""):
    conn = get_db_connection()
    conn.execute('INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)',
                 (user_id, action, details))
    conn.commit()
    conn.close()

# === UI ROUTES ===
@app.route('/')
def index():
    return render_template('supervisor_ui.html')

@app.route('/station')
def technician_station():
    return render_template('technician_ui.html')

# === TOOL MANAGEMENT ===
@app.route('/api/tools', methods=['GET', 'POST'])
def manage_tools():
    conn = get_db_connection()
    if request.method == 'GET':
        tools = conn.execute('SELECT * FROM tools').fetchall()
        conn.close()
        return jsonify([dict(row) for row in tools])
    elif request.method == 'POST':
        data = request.get_json()
        if not data.get('id') or not data.get('name') or not data.get('calibration_due'):
            conn.close()
            return jsonify({'message': 'Missing required fields'}), 400
        try:
            conn.execute('''
                INSERT INTO tools (id, name, status, current_holder, calibration_due)
                VALUES (?, ?, 'Available', NULL, ?)
            ''', (data['id'], data['name'], data['calibration_due']))
            log_audit_event("SYSTEM", 'TOOL_CREATED', json.dumps(data))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Tool created'}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'message': 'Tool ID already exists'}), 409

@app.route('/api/tools/<tool_id>', methods=['PUT', 'DELETE'])
def update_delete_tool(tool_id):
    conn = get_db_connection()
    if request.method == 'PUT':
        data = request.get_json()
        if not data.get('name') or not data.get('calibration_due'):
            conn.close()
            return jsonify({'message': 'Missing required fields'}), 400
        cur = conn.execute('UPDATE tools SET name = ?, calibration_due = ? WHERE id = ?',
                           (data['name'], data['calibration_due'], tool_id))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({'message': 'Tool not found'}), 404
        log_audit_event("SYSTEM", 'TOOL_UPDATED', json.dumps({'tool_id': tool_id, **data}))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Tool updated'})
    elif request.method == 'DELETE':
        cur = conn.execute('DELETE FROM tools WHERE id = ?', (tool_id,))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({'message': 'Tool not found'}), 404
        log_audit_event("SYSTEM", 'TOOL_DELETED', json.dumps({'tool_id': tool_id}))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Tool deleted'})

# === MANUAL STATUS UPDATE ===
@app.route('/api/tools/<tool_id>/status', methods=['PUT'])
def update_tool_status(tool_id):
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['Available', 'In Use', 'Overdue', 'Under Maintenance']:
        return jsonify({'message': 'Invalid status'}), 400
    conn = get_db_connection()
    cur = conn.execute('UPDATE tools SET status = ? WHERE id = ?', (new_status, tool_id))
    if cur.rowcount == 0:
        conn.close()
        return jsonify({'message': 'Tool not found'}), 404
    log_audit_event("SYSTEM", 'TOOL_STATUS_CHANGED', json.dumps({'tool_id': tool_id, 'new_status': new_status}))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Status updated'})

# === USER MANAGEMENT ===
@app.route('/api/users', methods=['GET', 'POST'])
def manage_users():
    conn = get_db_connection()
    if request.method == 'GET':
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()
        return jsonify([dict(row) for row in users])
    elif request.method == 'POST':
        data = request.get_json()
        if not data.get('id') or not data.get('name') or not data.get('role'):
            conn.close()
            return jsonify({'message': 'Missing required fields'}), 400
        try:
            conn.execute('INSERT INTO users (id, name, role) VALUES (?, ?, ?)',
                         (data['id'], data['name'], data['role']))
            log_audit_event("SYSTEM", 'USER_CREATED', json.dumps(data))
            conn.commit()
            conn.close()
            return jsonify({'message': 'User created'}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'message': 'User ID already exists'}), 409

@app.route('/api/users/<user_id>', methods=['GET', 'PUT', 'DELETE'])
def single_user(user_id):
    conn = get_db_connection()
    if request.method == 'GET':
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if user is None:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(dict(user))
    elif request.method == 'PUT':
        data = request.get_json()
        cur = conn.execute('UPDATE users SET name = ?, role = ? WHERE id = ?',
                           (data['name'], data['role'], user_id))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({'message': 'User not found'}), 404
        log_audit_event("SYSTEM", 'USER_UPDATED', json.dumps({'user_id': user_id, **data}))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User updated'})
    elif request.method == 'DELETE':
        cur = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        if cur.rowcount == 0:
            conn.close()
            return jsonify({'message': 'User not found'}), 404
        log_audit_event("SYSTEM", 'USER_DELETED', json.dumps({'user_id': user_id}))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User deleted'})

# === CHECKOUT / CHECKIN ===
@app.route('/api/checkout', methods=['POST'])
def checkout_tool():
    data = request.get_json()
    user_id = data.get('user_id')
    tool_id = data.get('tool_id')
    if not user_id or not tool_id:
        return jsonify({'message': 'Missing user_id or tool_id'}), 400
    conn = get_db_connection()
    tool = conn.execute('''
        SELECT *, date(calibration_due) < date('now') as is_overdue
        FROM tools WHERE id = ?
    ''', (tool_id,)).fetchone()
    if not tool:
        conn.close()
        return jsonify({'message': 'Tool not found'}), 400
    if tool['status'] != 'Available':
        conn.close()
        return jsonify({'message': 'Tool is not available'}), 400
    if tool['is_overdue']:
        conn.close()
        return jsonify({'message': 'Tool is overdue for calibration'}), 400
    conn.execute('UPDATE tools SET status = "In Use", current_holder = ? WHERE id = ?',
                 (user_id, tool_id))
    conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkout")',
                 (user_id, tool_id))
    log_audit_event(user_id, 'TOOL_CHECKOUT', json.dumps({'tool_id': tool_id}))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Checkout successful'}), 200

@app.route('/api/checkin', methods=['POST'])
def checkin_tool():
    data = request.get_json()
    tool_id = data.get('tool_id')
    report_issue = data.get('report_issue', False)
    if not tool_id:
        return jsonify({'message': 'Missing tool_id'}), 400
    conn = get_db_connection()
    tool = conn.execute('SELECT * FROM tools WHERE id = ? AND status = "In Use"', (tool_id,)).fetchone()
    if not tool:
        conn.close()
        return jsonify({'message': 'Tool not checked out or already returned'}), 400
    # Calculate usage duration
    checkout_time = conn.execute('''
        SELECT timestamp FROM transactions 
        WHERE tool_id = ? AND type = 'checkout' 
        ORDER BY timestamp DESC LIMIT 1
    ''', (tool_id,)).fetchone()
    duration_hours = 0.0
    if checkout_time:
        try:
            checkout_dt = datetime.fromisoformat(checkout_time[0].replace('Z', '+00:00'))
            checkin_dt = datetime.now()
            duration_hours = (checkin_dt - checkout_dt).total_seconds() / 3600.0
        except:
            duration_hours = 0.0
    new_status = "Under Maintenance" if report_issue else "Available"
    conn.execute('''
        UPDATE tools 
        SET status = ?, current_holder = NULL,
            total_checkouts = total_checkouts + 1,
            total_usage_hours = total_usage_hours + ?
        WHERE id = ?
    ''', (new_status, duration_hours, tool_id))
    conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkin")',
                 (tool['current_holder'], tool_id))
    log_audit_event(tool['current_holder'], 'TOOL_CHECKIN', 
                    json.dumps({'tool_id': tool_id, 'report_issue': report_issue}))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Check-in successful'}), 200

# === CALENDAR & ALERTS ===
@app.route('/api/calibration/events')
def get_calibration_events():
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT calibration_due, COUNT(*) as count
        FROM tools
        WHERE calibration_due >= ? AND calibration_due < ?
        GROUP BY calibration_due
    ''', (start, end)).fetchall()
    conn.close()
    return jsonify({row['calibration_due']: row['count'] for row in rows})

@app.route('/api/alerts')
def get_alerts():
    conn = get_db_connection()
    
    # Overdue tools
    overdue = conn.execute('''
        SELECT * FROM tools
        WHERE status != 'Under Maintenance'
        AND date(calibration_due) < date('now')
    ''').fetchall()

    # Long checkouts: triggered 16 hours after end of the day of checkout
    long_checkout = conn.execute('''
        SELECT t.*, tr.timestamp
        FROM tools t
        JOIN transactions tr ON t.id = tr.tool_id
        WHERE t.status = 'In Use' AND tr.type = 'checkout'
        AND (
            strftime('%Y-%m-%d', tr.timestamp) || ' 23:59:59' < datetime('now', '-16 hours')
        )
    ''').fetchall()

    conn.close()
    return jsonify({
        'overdue': [dict(row) for row in overdue],
        'long_checkout': [dict(row) for row in long_checkout]
    })

# === ACTIVITY LOG ===
@app.route('/api/transactions')
def get_transactions():
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT t.id, u.name as user_name, tl.name as tool_name, t.type, t.timestamp
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        JOIN tools tl ON t.tool_id = tl.id
        ORDER BY t.timestamp DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in transactions])

# === LIVE VIEW ===
@app.route('/api/live-view')
def get_live_view():
    conn = get_db_connection()
    live_tools = conn.execute('''
        SELECT 
            t.id as tool_id,
            t.name as tool_name,
            t.status as tool_status,
            u.id as user_id,
            u.name as user_name,
            tr.timestamp as checkout_time,
            (strftime('%s', 'now') - strftime('%s', tr.timestamp)) as seconds_held
        FROM tools t
        JOIN users u ON t.current_holder = u.id
        JOIN transactions tr ON t.id = tr.tool_id
        WHERE t.status = 'In Use' AND tr.type = 'checkout'
        ORDER BY tr.timestamp ASC
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in live_tools])

# === AUDIT TRAIL ===
@app.route('/api/audit-trail')
def get_audit_trail():
    conn = get_db_connection()
    logs = conn.execute('''
        SELECT a.*, u.name as user_name
        FROM audit_log a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT 100
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in logs])

# === AI CALIBRATION FORECAST ===
@app.route('/api/calibration/predict', methods=['POST'])
def trigger_ai_prediction():
    try:
        from predictive_calibration import train_and_predict
        result = train_and_predict()
        if result is None:
            return jsonify({'message': 'Insufficient data for prediction'}), 400
        return jsonify({'message': 'AI forecast completed', 'updated_tools': len(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === EMERGENCY UNLOCK ===
@app.route('/api/unlock/emergency', methods=['POST'])
def emergency_unlock():
    data = request.get_json()
    reason = data.get('reason')
    supervisor_id = "USR-001"
    if not reason:
        return jsonify({'message': 'Reason is required'}), 400
    log_audit_event(supervisor_id, 'EMERGENCY_UNLOCK', json.dumps({'reason': reason}))
    print(f"[EMERGENCY UNLOCK] Reason: {reason}")
    return jsonify({'message': 'Unlock command sent'})

# === HEALTH CHECK ===
@app.route('/api/health')
def health_check():
    return jsonify({'status': 'OK', 'time': datetime.now().isoformat()})

# === RUN SERVER ===
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')