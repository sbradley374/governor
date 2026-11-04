#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$EUID" == 0 ]]; then
  echo 'Run this on the Pi as your normal desktop user, without sudo.' >&2
  exit 1
fi
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y chromium
fi
face_dir="$HOME/.local/share/governor-face"
mkdir -p "$face_dir" "$HOME/.config/autostart"
for file in ambient.html ambient.css ambient.js face.js; do
  install -m 644 "governor/static/$file" "$face_dir/$file"
done
install -m 755 scripts/kiosk-face.sh "$face_dir/launch.sh"
launcher="$HOME/.config/autostart/governor.desktop"
if [[ -f "$launcher" ]]; then cp "$launcher" "$launcher.backup-$(date +%Y%m%d-%H%M%S)"; fi
cat > "$launcher" <<DESKTOP
[Desktop Entry]
Type=Application
Name=The Governor silent face
Exec=bash "$face_dir/launch.sh"
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP
printf '\nInstalled. Start now with:\n  bash "%s/launch.sh"\n' "$face_dir"
echo 'The face will start on future desktop logins. For startup without a keyboard, enable Desktop Autologin in sudo raspi-config and reboot.'
