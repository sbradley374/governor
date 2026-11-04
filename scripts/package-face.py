#!/usr/bin/env python3
"""Build the tiny standalone face bundle. No Python environment or API on the Pi."""
from pathlib import Path
import hashlib
import tarfile
root=Path(__file__).resolve().parent.parent
output=root/'dist/governor-face.tar.gz'
output.parent.mkdir(exist_ok=True)
files=['governor/static/'+name for name in ('ambient.html','ambient.css','ambient.js','face.js')]
files+=['scripts/install-face.sh','scripts/kiosk-face.sh','docs/FACE_ONLY.md']
with tarfile.open(output,'w:gz') as archive:
    for name in files: archive.add(root/name,arcname='governor-face/'+name)
output.with_suffix('.gz.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(f'{output} ({output.stat().st_size:,} bytes)')
