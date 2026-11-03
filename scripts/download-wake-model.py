#!/usr/bin/env python3
"""Download a pinned, checksummed Vosk model; never starts a microphone."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile
from dotenv import load_dotenv

load_dotenv()
NAME = 'vosk-model-small-en-us-0.15'
URL = f'https://alphacephei.com/vosk/models/{NAME}.zip'
# Verified against the publisher's archive on 2026-11-02.
SHA256 = '30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498'
root = Path(os.getenv('GOVERNOR_MODEL_DIR', 'models')).resolve()
root.mkdir(parents=True, exist_ok=True)
if (root / NAME).exists():
    raise SystemExit(f'{root / NAME} already exists. Move it aside to download a clean copy.')
with tempfile.TemporaryDirectory(dir=root) as temporary:
    temp = Path(temporary)
    archive = temp / 'model.zip'
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > 60 * 1024 * 1024:
                raise SystemExit('Unexpected model archive size')
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != SHA256:
        raise SystemExit('Model checksum mismatch; nothing installed')
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            destination = (temp / item.filename).resolve()
            if temp not in destination.parents or not item.filename.startswith(NAME + '/'):
                raise SystemExit('Unsafe model archive path')
        zipped.extractall(temp)
    if not (temp / NAME / 'am' / 'final.mdl').is_file():
        raise SystemExit('Model is incomplete')
    shutil.move(str(temp / NAME), str(root / NAME))
(root / 'wake-model.sha256').write_text(SHA256 + '  ' + NAME + '.zip\n')
print(f'Installed {NAME}. No microphone was opened.')
