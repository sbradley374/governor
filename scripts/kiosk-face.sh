#!/usr/bin/env bash
set -euo pipefail
# Run as the desktop user, not root. Works from desktop autostart or SSH into it.
face_dir="${GOVERNOR_FACE_DIR:-$HOME/.local/share/governor-face}"
if [[ ! -f "$face_dir/ambient.html" ]]; then
  echo 'Run bash scripts/install-face.sh first.' >&2
  exit 1
fi
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  for socket in "$XDG_RUNTIME_DIR"/wayland-*; do
    if [[ -S "$socket" ]]; then
      export WAYLAND_DISPLAY="$(basename "$socket")"
      break
    fi
  done
  if [[ -z "${WAYLAND_DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
  fi
fi
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo 'No desktop session found. Enable Desktop Autologin with sudo raspi-config, then reboot.' >&2
  exit 1
fi
face_url="$(python3 - "$face_dir/ambient.html" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve().as_uri())
PY
)"
platform_flags=()
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then platform_flags+=(--ozone-platform=wayland); fi
for browser in chromium chromium-browser; do
  if command -v "$browser" >/dev/null 2>&1; then
    exec "$browser" "${platform_flags[@]}" --kiosk --no-first-run --noerrdialogs --disable-session-crashed-bubble \
      --user-data-dir="$face_dir/browser-profile" "$face_url"
  fi
done
echo 'Chromium is missing. Run bash scripts/install-face.sh.' >&2
exit 1
