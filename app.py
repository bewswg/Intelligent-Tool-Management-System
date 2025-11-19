# app.py
from flask import Flask, render_template, jsonify, request
import sqlite3
import json
from datetime import datetime, timedelta
import requests # Required for Telegram alerts via n8n

app = Flask(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row # Allows access to columns by name
    return conn

# === AUDIT LOGGING HELPER (FIXED) ===
def log_audit_event(user_id, action, details=""):
    """
    Logs an event to the audit_log table.
    Ensures its own connection is opened and closed properly.
    """
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)',
                     (user_id, action, details))
        conn.commit()
    except Exception as e:
        # Log the error if the audit log itself fails, but don't crash the main operation
        print(f"❌ ERROR: Failed to log audit event: {e}")
    finally:
        conn.close() # Always close the connection


# === TRIGGER OVERDUE ALERT VIA N8N (HANDLED GRACEFULLY) ===
def trigger_overdue_alert(tool_id, user_id):
    """
    Calls the n8n webhook to send a Telegram/WhatsApp alert for overdue checkouts.
    Gracefully handles n8n being unavailable.
    """
    conn = get_db_connection()
    try:
        # Fetch user and tool details for the alert message
        user = conn.execute('SELECT name, contact_id FROM users WHERE id = ?', (user_id,)).fetchone()
        tool = conn.execute('SELECT name FROM tools WHERE id = ?', (tool_id,)).fetchone()
    except Exception as e:
        print(f"❌ ERROR fetching data for alert: {e}")
        return
    finally:
        conn.close()

    if not user or not tool:
        print(f"⚠️ Could not fetch user ({user_id}) or tool ({tool_id}) for alert.")
        return

    # Determine chat ID, defaulting to a placeholder if not set
    chat_id = user["contact_id"] if user["contact_id"] else "DEFAULT_TELEGRAM_USER_ID_FOR_TESTING"
    # IMPORTANT: Replace "DEFAULT_TELEGRAM_USER_ID_FOR_TESTING" with an actual ID or handle gracefully

    payload = {
        "technician_name": user["name"],
        "tool_name": tool["name"],
        "tool_id": tool_id,
        "chat_id": chat_id
    }

    n8n_webhook_url = "http://localhost:5678/webhook/tool-overdue" # Update if n8n is on a different port/IP

    try:
        response = requests.post(n8n_webhook_url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Alert sent for tool {tool_id} to user {user_id} (chat_id: {chat_id})")
        else:
            print(f"❌ Alert failed with status {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        # This handles the specific error you saw: n8n not running
        print("❌ n8n alert failed: Connection refused. Is n8n running on localhost:5678?")
    except Exception as e:
        print(f"❌ n8n alert failed with unexpected error: {e}")

# === UI ROUTES ===
@app.route('/')
def index():
    """Serves the Supervisor Dashboard."""
    return render_template('supervisor_ui.html')

@app.route('/station')
def technician_station():
    """Serves the Technician UI."""
    return render_template('technician_ui.html')

# === TOOL MANAGEMENT (FR-IM) ===
@app.route('/api/tools', methods=['GET', 'POST'])
def manage_tools():
    """
    Handles fetching all tools (GET) and creating a new tool (POST).
    Implements FR-IM-01, FR-IM-03.
    """
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            tools = conn.execute('SELECT * FROM tools').fetchall()
            return jsonify([dict(row) for row in tools])

        elif request.method == 'POST':
            data = request.get_json()
            if not data.get('id') or not data.get('name') or not data.get('calibration_due'):
                return jsonify({'message': 'Missing required fields (id, name, calibration_due)'}), 400
            try:
                conn.execute('''
                    INSERT INTO tools (id, name, status, current_holder, calibration_due, total_checkouts, total_usage_hours)
                    VALUES (?, ?, 'Available', NULL, ?, 0, 0.0)
                ''', (data['id'], data['name'], data['calibration_due']))
                log_audit_event("SYSTEM", 'TOOL_CREATED', json.dumps(data))
                conn.commit()
                return jsonify({'message': 'Tool created successfully'}), 201
            except sqlite3.IntegrityError:
                return jsonify({'message': 'Tool ID already exists'}), 409
    finally:
        conn.close()

@app.route('/api/tools/<tool_id>', methods=['PUT', 'DELETE'])
def update_delete_tool(tool_id):
    """
    Handles updating (PUT) or deleting (DELETE) a specific tool.
    Implements FR-IM-03.
    """
    conn = get_db_connection()
    try:
        if request.method == 'PUT':
            data = request.get_json()
            if not data.get('name') or not data.get('calibration_due'):
                return jsonify({'message': 'Missing required fields (name, calibration_due)'}), 400
            cur = conn.execute('''
                UPDATE tools SET name = ?, calibration_due = ? WHERE id = ?
            ''', (data['name'], data['calibration_due'], tool_id))
            if cur.rowcount == 0:
                return jsonify({'message': 'Tool not found'}), 404
            log_audit_event("SYSTEM", 'TOOL_UPDATED', json.dumps({'tool_id': tool_id, **data}))
            conn.commit()
            return jsonify({'message': 'Tool updated'})

        elif request.method == 'DELETE':
            cur = conn.execute('DELETE FROM tools WHERE id = ?', (tool_id,))
            if cur.rowcount == 0:
                return jsonify({'message': 'Tool not found'}), 404
            log_audit_event("SYSTEM", 'TOOL_DELETED', json.dumps({'tool_id': tool_id}))
            conn.commit()
            return jsonify({'message': 'Tool deleted'})
    finally:
        conn.close()

# === NEW ROUTE: GET SINGLE TOOL DETAILS (FOR CHECKOUT VALIDATION) ===
@app.route('/api/tools/<tool_id>')
def get_single_tool(tool_id):
    """
    Retrieves details for a specific tool.
    Used by Technician UI before checkout to re-validate status.
    """
    conn = get_db_connection()
    try:
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
        if tool is None:
            return jsonify({'error': 'Tool not found'}), 404
        return jsonify(dict(tool))
    finally:
        conn.close()

# === NEW ROUTE: GET AVAILABLE TOOLS (FOR TECHNICIAN UI) ===
@app.route('/api/tools/available')
def get_available_tools():
    """
    Retrieves tools with status 'Available'.
    Used by Technician UI to populate the tool selection grid.
    """
    conn = get_db_connection()
    try:
        tools = conn.execute('SELECT * FROM tools WHERE status = "Available"').fetchall()
        return jsonify([dict(row) for row in tools])
    finally:
        conn.close()

# === MANUAL STATUS UPDATE (FR-IM-03, FR-COCI-12) ===
@app.route('/api/tools/<tool_id>/status', methods=['PUT'])
def update_tool_status(tool_id):
    """
    Allows supervisors to manually update a tool's status.
    Implements FR-COCI-12 (e.g., set to 'Under Maintenance').
    """
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['Available', 'In Use', 'Overdue', 'Under Maintenance']:
        return jsonify({'message': 'Invalid status'}), 400

    conn = get_db_connection()
    try:
        cur = conn.execute('UPDATE tools SET status = ? WHERE id = ?', (new_status, tool_id))
        if cur.rowcount == 0:
            return jsonify({'message': 'Tool not found'}), 404
        log_audit_event("SYSTEM", 'TOOL_STATUS_CHANGED',
                        json.dumps({'tool_id': tool_id, 'new_status': new_status}))
        conn.commit()
        return jsonify({'message': 'Status updated'})
    finally:
        conn.close()

# === USER MANAGEMENT (FR-UM) ===
@app.route('/api/users', methods=['GET', 'POST'])
def manage_users():
    """
    Handles fetching all users (GET) and creating a new user (POST).
    Implements FR-UM-02.
    """
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            users = conn.execute('SELECT * FROM users').fetchall()
            return jsonify([dict(row) for row in users])

        elif request.method == 'POST':
            data = request.get_json()
            if not data.get('id') or not data.get('name') or not data.get('role'):
                return jsonify({'message': 'Missing required fields (id, name, role)'}), 400
            try:
                conn.execute('INSERT INTO users (id, name, role, contact_id) VALUES (?, ?, ?, NULL)',
                             (data['id'], data['name'], data['role']))
                log_audit_event("SYSTEM", 'USER_CREATED', json.dumps(data))
                conn.commit()
                return jsonify({'message': 'User created'}), 201
            except sqlite3.IntegrityError:
                return jsonify({'message': 'User ID already exists'}), 409
    finally:
        conn.close()

@app.route('/api/users/<user_id>', methods=['GET', 'PUT', 'DELETE'])
def single_user(user_id):
    """
    Handles fetching (GET), updating (PUT), or deleting (DELETE) a specific user.
    Implements FR-UM-02.
    """
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if user is None:
                return jsonify({'error': 'User not found'}), 404
            return jsonify(dict(user))

        elif request.method == 'PUT':
            data = request.get_json()
            cur = conn.execute('UPDATE users SET name = ?, role = ?, contact_id = ? WHERE id = ?',
                               (data['name'], data['role'], data.get('contact_id'), user_id))
            if cur.rowcount == 0:
                return jsonify({'message': 'User not found'}), 404
            log_audit_event("SYSTEM", 'USER_UPDATED', json.dumps({'user_id': user_id, **data}))
            conn.commit()
            return jsonify({'message': 'User updated'})

        elif request.method == 'DELETE':
            cur = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            if cur.rowcount == 0:
                return jsonify({'message': 'User not found'}), 404
            log_audit_event("SYSTEM", 'USER_DELETED', json.dumps({'user_id': user_id}))
            conn.commit()
            return jsonify({'message': 'User deleted'})
    finally:
        conn.close()

# === CHECKOUT / CHECKIN (FR-COCI) ===
@app.route('/api/checkout', methods=['POST'])
def checkout_tool():
    """
    Handles the tool checkout process.
    Implements FR-COCI-01 to FR-COCI-05.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    tool_id = data.get('tool_id')
    if not user_id or not tool_id:
        return jsonify({'message': 'Missing user_id or tool_id'}), 400

    conn = get_db_connection()
    try:
        # Validate tool exists, is available, and not overdue
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

        # Update tool status and holder, log transaction
        conn.execute('UPDATE tools SET status = "In Use", current_holder = ? WHERE id = ?',
                     (user_id, tool_id))
        conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkout")',
                     (user_id, tool_id))
        log_audit_event(user_id, 'TOOL_CHECKOUT', json.dumps({'tool_id': tool_id}))
        conn.commit()
        return jsonify({'message': 'Checkout successful'}), 200
    finally:
        conn.close()

@app.route('/api/checkin', methods=['POST'])
def checkin_tool():
    """
    Handles the tool check-in process.
    Implements FR-COCI-10 to FR-COCI-12.
    """
    data = request.get_json()
    tool_id = data.get('tool_id')
    report_issue = data.get('report_issue', False)
    if not tool_id:
        return jsonify({'message': 'Missing tool_id'}), 400

    conn = get_db_connection()
    try:
        # Validate tool exists and is currently in use by the same user (if user is known)
        # For simplicity in this prototype, just check status 'In Use'
        tool = conn.execute('SELECT * FROM tools WHERE id = ? AND status = "In Use"', (tool_id,)).fetchone()
        if not tool:
            return jsonify({'message': 'Tool not checked out or already returned'}), 400

        # Determine new status based on report
        new_status = "Under Maintenance" if report_issue else "Available"
        current_holder = tool['current_holder'] # Capture holder before update

        # Update tool status and holder, log transaction
        conn.execute('UPDATE tools SET status = ?, current_holder = NULL WHERE id = ?',
                     (new_status, tool_id))
        conn.execute('INSERT INTO transactions (user_id, tool_id, type) VALUES (?, ?, "checkin")',
                     (current_holder, tool_id))
        log_audit_event(current_holder, 'TOOL_CHECKIN',
                        json.dumps({'tool_id': tool_id, 'report_issue': report_issue}))
        conn.commit()
        return jsonify({'message': 'Check-in successful'}), 200
    finally:
        conn.close()

# === CALIBRATION CALENDAR (FR-CAL) ===
@app.route('/api/calibration/events')
def get_calibration_events():
    """
    Provides data for the Supervisor UI's calibration calendar.
    Implements FR-CAL-02.
    """
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

# === ALERTS (FR-AFT) ===
@app.route('/api/alerts')
def get_alerts():
    """
    Generates critical alerts for the Supervisor UI.
    Implements FR-AFT-01, FR-AFT-02.
    """
    conn = get_db_connection()
    try:
        # Overdue tools
        overdue = conn.execute('''
            SELECT * FROM tools
            WHERE status != 'Under Maintenance'
            AND date(calibration_due) < date('now')
        ''').fetchall()

        # Long checkouts: triggered 16 hours after the END OF THE DAY the tool was checked out
        long_checkout = conn.execute('''
            SELECT t.*, tr.timestamp
            FROM tools t
            JOIN transactions tr ON t.id = tr.tool_id
            WHERE t.status = 'In Use' AND tr.type = 'checkout'
            AND (
                strftime('%Y-%m-%d', tr.timestamp) || ' 23:59:59' < datetime('now', '-16 hours')
            )
        ''').fetchall()

        # Trigger Telegram alerts for newly detected long checkouts
        # (In a real system, you'd track which alerts were already sent)
        for tool in long_checkout:
            # Note: This triggers on *every* fetch of alerts if the condition is met.
            # For a production system, use a background task or track sent alerts in the DB.
            trigger_overdue_alert(tool['id'], tool['current_holder'])

        return jsonify({
            'overdue': [dict(row) for row in overdue],
            'long_checkout': [dict(row) for row in long_checkout]
        })
    finally:
        conn.close()

# === ACTIVITY LOG ===
@app.route('/api/transactions')
def get_transactions():
    """
    Provides recent transaction history for the Supervisor UI.
    """
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

# === LIVE VIEW ===
@app.route('/api/live-view')
def get_live_view():
    """
    Provides real-time view of currently checked-out tools.
    """
    conn = get_db_connection()
    try:
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
        return jsonify([dict(row) for row in live_tools])
    finally:
        conn.close()

# === AUDIT TRAIL ===
@app.route('/api/audit-trail')
def get_audit_trail():
    """
    Provides the audit trail explorer for compliance and review.
    """
    conn = get_db_connection()
    try:
        logs = conn.execute('''
            SELECT a.*, u.name as user_name
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT 100
        ''').fetchall()
        return jsonify([dict(row) for row in logs])
    finally:
        conn.close()

# === AI CALIBRATION FORECAST (PLACEHOLDER) ===
@app.route('/api/calibration/predict', methods=['POST'])
def trigger_ai_prediction():
    """
    Placeholder for triggering the AI calibration forecast.
    Assumes a script named 'predictive_calibration.py' exists.
    """
    try:
        from predictive_calibration import train_and_predict # Assumes the script is in the same directory
        result = train_and_predict()
        if result is None:
            return jsonify({'message': 'Insufficient data for prediction'}), 400
        return jsonify({'message': 'AI forecast completed', 'updated_tools': len(result)})
    except ImportError:
        return jsonify({'error': 'predictive_calibration module not found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === EMERGENCY UNLOCK (FR-AFT-03/04) ===
@app.route('/api/unlock/emergency', methods=['POST'])
def emergency_unlock():
    """
    Handles emergency manual unlock requests.
    Implements FR-AFT-03, FR-AFT-04.
    """
    data = request.get_json()
    reason = data.get('reason')
    supervisor_id = data.get('supervisor_id', 'USR-001') # Default or get from session in real app
    if not reason:
        return jsonify({'message': 'Reason is required'}), 400

    log_audit_event(supervisor_id, 'EMERGENCY_UNLOCK',
                    json.dumps({'reason': reason, 'timestamp': datetime.now().isoformat()}))

    # In a real system, send command to Pi here
    print(f"[EMERGENCY UNLOCK] Reason: {reason} by {supervisor_id}")
    return jsonify({'message': 'Unlock command sent to Smart Box'})

# === HEALTH CHECK ===
@app.route('/api/health')
def health_check():
    """Simple endpoint to check if the API is running."""
    return jsonify({'status': 'OK', 'time': datetime.now().isoformat()})

# === RUN SERVER ===
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') # host='0.0.0.0' allows access from other devices on the network