#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_dir="$(pwd)"
# Generate a user service rather than hard-coding a pi user or running as root.
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/governor.service" <<SERVICE
[Unit]
Description=The Governor CRT companion
After=network.target

[Service]
Type=simple
WorkingDirectory="$project_dir"
ExecStart="$project_dir/.venv/bin/governor" serve
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=default.target
SERVICE
systemctl --user daemon-reload
systemctl --user enable --now governor.service
printf '\nService installed. Logs: journalctl --user -u governor -f\n'
