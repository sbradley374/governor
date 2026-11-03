#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Run this installer on the Raspberry Pi.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev espeak-ng libportaudio2 alsa-utils chromium
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e '.[audio,camera,wake]'
if [[ ! -f .env ]]; then cp .env.example .env; chmod 600 .env; fi
.venv/bin/governor doctor
printf '\nReady. Run .venv/bin/governor, then open http://localhost:8765\n'
