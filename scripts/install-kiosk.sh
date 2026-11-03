#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_dir="$(pwd)"
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/governor.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=The Governor CRT
Exec=bash "$project_dir/scripts/kiosk.sh"
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP
echo 'Kiosk enabled for the next desktop login. The server service must also be enabled.'
