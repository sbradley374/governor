#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_dir="$(pwd)"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Run this installer on the Raspberry Pi.' >&2
  exit 1
fi
# Opt-in: run only after testing governor listen with the actual TV and microphone.
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/governor-audio.service" <<SERVICE
[Unit]
Description=Governor local wake word and room audio
After=governor.service sound.target
Requires=governor.service

[Service]
Type=simple
WorkingDirectory="$project_dir"
ExecStart="$project_dir/.venv/bin/governor" listen
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=default.target
SERVICE
systemctl --user daemon-reload
systemctl --user enable --now governor-audio.service
printf '\nAudio enabled. Stop: systemctl --user disable --now governor-audio\n'
