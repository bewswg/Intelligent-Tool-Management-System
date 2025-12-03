# bot_listener.py
import time
import requests
from telegram_manager import handle_my_tools, handle_report, BOT_TOKEN

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates?timeout=100"
    if offset:
        url += f"&offset={offset}"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        print(f"Connection Error: {e}")
        return {}

def send_reply(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

def main():
    print("🤖 Technician Assistant Bot is Running...")
    last_update_id = None

    while True:
        updates = get_updates(last_update_id)
        if "result" in updates:
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1
                
                if "message" not in update: continue
                
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")
                
                print(f"📩 Received: {text} from {chat_id}")

                if text.startswith("/mytools"):
                    response = handle_my_tools(chat_id)
                    send_reply(chat_id, response)
                
                elif text.startswith("/report"):
                    # Expected format: /report TW-001 Broken handle
                    parts = text.split(" ", 2)
                    if len(parts) < 3:
                        send_reply(chat_id, "⚠️ Usage: `/report <TOOL_ID> <ISSUE>`\nExample: `/report TW-001 Screen cracked`")
                    else:
                        response = handle_report(chat_id, parts[1], parts[2])
                        send_reply(chat_id, response)
                        
                elif text.startswith("/start"):
                    send_reply(chat_id, "👋 **Welcome to AeroTool Bot!**\n\nCommands:\n`/mytools` - Check what you are holding\n`/report <ID> <Issue>` - Report broken tool")

        time.sleep(1)

if __name__ == "__main__":
    main()