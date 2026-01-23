@echo off
TITLE AeroTool MRO Launcher

:: 1. Start the Server (Hidden)
echo Starting MRO Server...
start "MRO Server" /min python app.py

:: 2. Start the Telegram Bot (Hidden)
echo Starting Telegram Bot...
start "Telegram Bot" /min python bot_listener.py

:: 3. Wait for server to boot
echo Waiting for system warmup...
timeout /t 3 /nobreak >nul

:: 4. Launch SUPERVISOR Dashboard (Window 1)
echo Launching Supervisor Dashboard...
start msedge --new-window --app=http://127.0.0.1:5000

:: 5. Launch TECHNICIAN Station (Window 2)
echo Launching Technician Kiosk...
start msedge --new-window --app=http://127.0.0.1:5000/station

:: 6. Cleanup
exit