#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"

echo "=== Gold Rate Notification Setup ==="
echo ""

# ── Step 1: Python virtual environment ──────────────────────────────────────
echo "[1/4] Creating Python virtual environment..."
python3 -m venv "$PROJECT_DIR/venv"
"$PROJECT_DIR/venv/bin/pip" install -q --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"
echo "      Done."

# ── Step 2: Verify .env ──────────────────────────────────────────────────────
echo ""
echo "[2/4] Checking .env credentials..."
source "$PROJECT_DIR/.env" 2>/dev/null || true

if [[ "$TELEGRAM_BOT_TOKEN" == "your_bot_token_here" || -z "$TELEGRAM_BOT_TOKEN" ]]; then
  echo "  ⚠️  TELEGRAM_BOT_TOKEN not set in .env — please fill it in and re-run."
  exit 1
fi
echo "      Credentials found."

# ── Step 3: Test run ─────────────────────────────────────────────────────────
echo ""
echo "[3/4] Sending a test notification to Telegram..."
"$PYTHON" "$PROJECT_DIR/notify.py"
echo "      Check Telegram — you should have received a message!"

# ── Step 4: Install two launchd jobs ─────────────────────────────────────────
echo ""
echo "[4/4] Installing launchd jobs..."
mkdir -p "$HOME/Library/LaunchAgents"

# Helper to write and load a plist
install_job() {
  local label="$1"
  local hour="$2"
  local minute="$3"
  local plist="$HOME/Library/LaunchAgents/${label}.plist"

  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${PROJECT_DIR}/notify.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${hour}</integer>
        <key>Minute</key>
        <integer>${minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/notify.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/notify.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  echo "      Installed: $label → ${hour}:$(printf '%02d' $minute) local time"
}

# Job 1 — 8:00 AM PST  (US morning)
install_job "com.goldrate.notify.us"     8  0

# Job 2 — 6:30 PM PST  (= 8:00 AM IST standard / ≈ 7:00 AM IST daylight)
install_job "com.goldrate.notify.india" 18 30

echo ""
echo "=== Setup complete! ==="
echo ""
echo "  Schedules:"
echo "    08:00 AM PST  — US morning notification"
echo "    06:30 PM PST  — India morning notification (≈ 8 AM IST)"
echo "  Log file : $PROJECT_DIR/notify.log"
echo ""
echo "  Useful commands:"
echo "    Run now    : $PYTHON $PROJECT_DIR/notify.py"
echo "    View log   : tail -f $PROJECT_DIR/notify.log"
echo "    Disable US : launchctl unload ~/Library/LaunchAgents/com.goldrate.notify.us.plist"
echo "    Disable IN : launchctl unload ~/Library/LaunchAgents/com.goldrate.notify.india.plist"
echo ""
