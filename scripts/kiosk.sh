#!/usr/bin/env bash
set -euo pipefail
# Run inside the Pi desktop session; choose the HDMI output in OS sound settings.
port="${GOVERNOR_PORT:-8765}"
python3 - "$port" <<'PY'
import sys
import time
import urllib.request
for attempt in range(60):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{int(sys.argv[1])}/api/health", timeout=1).close()
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("Governor server did not start. Check the user service before opening the kiosk.")
PY
for browser in chromium chromium-browser; do
  if command -v "$browser" >/dev/null 2>&1; then
    exec "$browser" --kiosk --noerrdialogs --disable-session-crashed-bubble \
      --autoplay-policy=no-user-gesture-required "http://localhost:$port/?display=1"
  fi
done
echo 'Install Chromium and run this script from the desktop session.' >&2
exit 1
