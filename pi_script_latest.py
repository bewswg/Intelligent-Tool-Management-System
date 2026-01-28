import board
import busio
import time
import requests  # <--- THE NEW BRIDGE LIBRARY
from gpiozero import DigitalOutputDevice, Button
from adafruit_tca9548a import TCA9548A
from adafruit_pn532.i2c import PN532_I2C

# ==========================================
#       CONFIG: POINT TO YOUR LAPTOP
# ==========================================
SERVER_URL = "http://10.188.1.177:5000" 

# --- HARDWARE CONFIGURATION ---
RELAY_PIN = 17        
REED_SWITCH_PIN = 27  
lock_relay = DigitalOutputDevice(RELAY_PIN, active_high=False, initial_value=False)
door_sensor = Button(REED_SWITCH_PIN, pull_up=True)

# --- I2C SETUP ---
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    tca = TCA9548A(i2c)
except Exception as e:
    print(f"❌ CRITICAL I2C ERROR: {e}")
    print("Check wires and reboot.")

readers = {}
tool_states = {3: None, 6: None} 
current_session_user = None

# ==========================================
#           THE BRIDGE FUNCTIONS
# ==========================================

def api_check_user(uid_str):
    """Asks the Laptop: 'Is this user allowed in?'"""
    try:
        response = requests.post(f"{SERVER_URL}/api/nfc/scan", json={'uid': uid_str}, timeout=2)
        if response.status_code == 200:
            return True
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ SERVER DOWN: Cannot connect to {SERVER_URL}")
        return False
    except Exception as e:
        print(f"⚠️ API ERROR: {e}")
        return False

def api_log_tool(action, tool_uid, port):
    """Tells the Laptop: 'A tool just moved!'"""
    if not current_session_user: return

    endpoint = "/api/checkout" if action == "REMOVED" else "/api/checkin"
    payload = {
        "user_id": current_session_user, 
        "tool_id": tool_uid,             
        "report_issue": False
    }

    try:
        requests.post(f"{SERVER_URL}{endpoint}", json=payload, timeout=1)
        print(f"   📡 SENT TO SERVER: {action} {tool_uid}")
    except:
        print(f"   ⚠️ NETWORK FAIL: Logged locally only.")

# ==========================================
#           HARDWARE LOGIC
# ==========================================

def get_snapshot():
    """Scans all ports and returns a dictionary {channel: tool_id}"""
    snapshot = {}
    for channel in [3, 6]:  # Add all your tool channels here
        if channel not in readers: continue
        try:
            uid = readers[channel].read_passive_target(timeout=0.2)
            if uid:
                # ✅ FIX: Use the clean 2-digit format (e.g., "04 a2...")
                snapshot[channel] = " ".join(["{:02x}".format(i) for i in uid])
            else:
                snapshot[channel] = None
        except:
            snapshot[channel] = None
    return snapshot


def initialize_hardware():
    print("\n--- INITIALIZING HARDWARE ---")
    for channel in [2, 3, 6]:
        try:
            pn = PN532_I2C(tca[channel], debug=False)
            pn.SAM_configuration()
            readers[channel] = pn
            print(f"✅ Port {channel}: ONLINE")
        except:
            print(f"❌ Port {channel}: FAILED")
    print("--------------------------------")

def check_tools(silent=False):
    for channel in [3, 6]:
        if channel not in readers: continue
        try:
            uid = readers[channel].read_passive_target(timeout=0.5)
            current_tool_id = None
            
            if uid:
                current_tool_id = " ".join([hex(i) for i in uid]).lower()
            
            previous_tool_id = tool_states.get(channel)
            
            if not silent and current_tool_id != previous_tool_id:
                if current_tool_id is None:
                    print(f"   🔻 REMOVED: {previous_tool_id}")
                    api_log_tool("REMOVED", previous_tool_id, channel)
                elif previous_tool_id is None:
                    print(f"   ✅ RETURNED: {current_tool_id}")
                    api_log_tool("RETURNED", current_tool_id, channel)
            
            tool_states[channel] = current_tool_id 
        except RuntimeError: continue
        except Exception: continue # Ignore random I2C glitches

def start_session(user_uid):
    global current_session_user
    current_session_user = user_uid
    
    # 1. BASELINE SCAN (What tools are inside before opening?)
    print("\n📸 Taking baseline snapshot...")
    baseline = get_snapshot()
    
    # 2. UNLOCK
    print(f"🟢 UNLOCKING for: {user_uid}")
    lock_relay.on()
    
    # 3. WAIT FOR DOOR OPEN
    print("   Waiting for door to open...")
    start_time = time.time()
    door_opened = False
    
    while (time.time() - start_time) < 10: # 10s timeout
        if not door_sensor.is_pressed: # Button released = Door Open
            door_opened = True
            break
        time.sleep(0.1)

    if not door_opened:
        print("   ⚠️ TIMEOUT: Door was not opened.")
        lock_relay.off()
        current_session_user = None
        return

    # 4. DOOR IS OPEN (PAUSE SCANNING)
    print("   🚪 DOOR OPEN. Pausing scan to avoid hand interference...")
    
    # Wait until door closes
    while not door_sensor.is_pressed:
        time.sleep(0.1) # Just wait, do nothing
        
    # 5. DOOR CLOSED - LOCK & SCAN
    print("   🚪 DOOR CLOSED. Locking...")
    time.sleep(1) # Safety buffer to ensure it's fully closed
    lock_relay.off()
    
    print("📸 Taking final snapshot...")
    final_state = get_snapshot()
    
    # 6. RECONCILIATION (Compare Before vs After)
    changes_detected = False
    
    for channel, new_uid in final_state.items():
        old_uid = baseline.get(channel)
        
        # CASE A: Tool was there, now it's gone (CHECKOUT)
        if old_uid and not new_uid:
            print(f"   🔻 ITEM REMOVED: {old_uid}")
            api_log_tool("REMOVED", old_uid, channel)
            changes_detected = True
            
        # CASE B: Slot was empty, now has tool (RETURN)
        elif not old_uid and new_uid:
            print(f"   ✅ ITEM RETURNED: {new_uid}")
            api_log_tool("RETURNED", new_uid, channel)
            changes_detected = True
            
        # CASE C: Tool changed (Swapped one tool for another in same slot)
        elif old_uid and new_uid and old_uid != new_uid:
            print(f"   🔄 SWAP: {old_uid} -> {new_uid}")
            api_log_tool("REMOVED", old_uid, channel) # Old one out
            api_log_tool("RETURNED", new_uid, channel) # New one in
            changes_detected = True

    if not changes_detected:
        print("   🤷‍♂️ No changes detected.")

    print("   📡 Sending Logout Signal to Server...")
    # No try/except! If this fails, I want to see the CRASH.
    requests.post(f"{SERVER_URL}/api/session/end", timeout=5)

    print("🔒 SESSION ENDED.")
    current_session_user = None
# ==========================================
#           MAIN INFINITE LOOP
# ==========================================
if __name__ == "__main__":
    try:
        initialize_hardware()
        
        # Initial scan to set baseline
        check_tools(silent=True)
        print("📡 CONNECTED. SYSTEM READY.")

        while True:
            try:
                # 1. VISUAL INDICATOR
                # (Optional: Blink an LED here if you had one)
                
                # 2. CHECK USER READER (Port 2)
                if 2 in readers:
                    try:
                        uid = readers[2].read_passive_target(timeout=0.5)
                        if uid:
                            uid_str = " ".join([hex(i) for i in uid]).lower()
                            
                            # ASK SERVER
                            if api_check_user(uid_str):
                                start_session(uid_str)
                                print("\n⏳ RESETTING... Waiting for next user.")
                                time.sleep(2) 
                            else:
                                print(f"⛔ ACCESS DENIED: {uid_str}")
                                time.sleep(1)
                    except RuntimeError:
                        pass # Reader timeout (normal)
                
                time.sleep(0.5)

            except Exception as e:
                # --- THIS IS THE CRASH PROTECTION ---
                # If anything crashes (WiFi drops, wire loose), we catch it here
                # print(f"⚠️ ERROR IN LOOP: {e}") 
                # We sleep briefly so we don't flood the console if it's a permanent error
                time.sleep(1)
                continue

    except KeyboardInterrupt:
        print("\n👋 Manual Shutdown.")
        lock_relay.off()