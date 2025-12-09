# telegram_manager.py
import requests
import sqlite3
import json
from datetime import datetime

# --- CONFIGURATION ---
# Your Token
BOT_TOKEN = "7881248009:AAFL7ireDLLl63VXc3XwdEwp1kj49UDDg9Y"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Supervisor ID (Replace if you have a specific ID)
SUPERVISOR_CHAT_ID = "954223496" 

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def send_telegram_message(chat_id, text):
    """Sends a message to a specific Telegram user."""
    if not chat_id:
        return
    try:
        url = f"{BASE_URL}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"⚠️ Telegram Send Error: {e}")

# --- FEATURE 3A: Anti-Spam Notification Logic ---
# telegram_manager.py (Updated Function)

def check_and_notify_users():
    """Checks for tools held too long and warns users (State-Aware)."""
    conn = get_db_connection()
    try:
        # 1. USER WARNINGS (7-8 Hours)
        warnings = conn.execute('''
            SELECT t.name as tool_name, u.contact_id, u.name as user_name, tr.id as tx_id
            FROM tools t
            JOIN users u ON t.current_holder = u.id
            JOIN transactions tr ON t.id = tr.tool_id
            WHERE t.status = 'In Use' 
            AND tr.type = 'checkout'
            -- BUG FIX: Only look at the LATEST checkout transaction
            AND tr.id = (SELECT MAX(id) FROM transactions WHERE tool_id = t.id AND type = 'checkout')
            AND tr.timestamp < datetime('now', '-7 hours')
            AND tr.timestamp > datetime('now', '-8 hours')
            AND (tr.last_alert_sent IS NULL OR tr.last_alert_sent < datetime('now', '-24 hours'))
        ''').fetchall()

        for w in warnings:
            if w['contact_id']:
                msg = f"⚠️ **7-Hour Warning**\nHi {w['user_name']}, you have held the *{w['tool_name']}* for over 7 hours.\nPlease return it soon to avoid a Critical FOD Violation."
                send_telegram_message(w['contact_id'], msg)
                
                conn.execute("UPDATE transactions SET last_alert_sent = datetime('now') WHERE id = ?", (w['tx_id'],))
                conn.commit()
                print(f"Sent warning to {w['user_name']}")

        # 2. CRITICAL ALERTS (> 8 Hours)
        criticals = conn.execute('''
            SELECT t.name as tool_name, u.name as user_name, tr.id as tx_id
            FROM tools t
            JOIN users u ON t.current_holder = u.id
            JOIN transactions tr ON t.id = tr.tool_id
            WHERE t.status = 'In Use' 
            AND tr.type = 'checkout'
            -- BUG FIX: Only look at the LATEST checkout transaction
            AND tr.id = (SELECT MAX(id) FROM transactions WHERE tool_id = t.id AND type = 'checkout')
            AND tr.timestamp < datetime('now', '-8 hours')
            AND (tr.last_alert_sent IS NULL OR tr.last_alert_sent < datetime('now', '-4 hours'))
        ''').fetchall()

        for c in criticals:
            msg = f"🚨 **CRITICAL FOD ALERT**\nTool: *{c['tool_name']}*\nUser: {c['user_name']}\nStatus: **> 8 Hours (Violation)**"
            send_telegram_message(SUPERVISOR_CHAT_ID, msg)
            
            conn.execute("UPDATE transactions SET last_alert_sent = datetime('now') WHERE id = ?", (c['tx_id'],))
            conn.commit()
            print(f"Sent critical alert for {c['tool_name']}")

    except Exception as e:
        print(f"Telegram Loop Error: {e}")
    finally:
        conn.close()

# --- FEATURE 3B: /mytools Logic ---
def handle_my_tools(chat_id):
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE contact_id = ?", (str(chat_id),)).fetchone()
        if not user:
            return "🚫 You are not registered in the system."

        tools = conn.execute("SELECT * FROM tools WHERE current_holder = ?", (user['id'],)).fetchall()
        
        if not tools:
            return f"✅ Hi {user['name']}, you have no tools checked out."
        
        msg = f"🔧 **My Tools ({len(tools)})**\n\n"
        for t in tools:
            msg += f"• *{t['name']}* ({t['id']})\n  Due: {t['calibration_due']}\n"
        
        return msg
    finally:
        conn.close()

# --- FEATURE 3C: Remote Report Logic ---
def handle_report(chat_id, tool_id, issue):
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE contact_id = ?", (str(chat_id),)).fetchone()
        if not user:
            return "🚫 You are not registered."

        tool = conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
        if not tool:
            return "❌ Tool ID not found."

        conn.execute("UPDATE tools SET status = 'Under Maintenance' WHERE id = ?", (tool_id,))
        
        details = json.dumps({"reported_by": user['name'], "issue": issue, "source": "TELEGRAM"})
        conn.execute("INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)", 
                     (user['id'], 'REMOTE_REPORT', details))
        conn.commit()

        alert_msg = f"🛠 **Remote Issue Report**\nTechnician: {user['name']}\nTool: {tool['name']}\nIssue: {issue}"
        send_telegram_message(SUPERVISOR_CHAT_ID, alert_msg)

        return f"✅ Issue reported for {tool['name']}. Supervisor notified."
    finally:
        conn.close()