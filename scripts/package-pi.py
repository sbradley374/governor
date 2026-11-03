#!/usr/bin/env python3
"""Build a portable source archive without local data, secrets, models, or venvs."""
from pathlib import Path
import hashlib
import tarfile

root = Path(__file__).resolve().parent.parent
output = root / 'dist' / 'governor-pi.tar.gz'
output.parent.mkdir(exist_ok=True)
files = [root / name for name in ('README.md', 'pyproject.toml', '.env.example', '.gitignore')]
for directory in ('governor', 'scripts', 'docs', 'tests', '.github'):
    files.extend(p for p in (root / directory).rglob('*')
                 if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.name != '.DS_Store')
with tarfile.open(output, 'w:gz') as archive:
    for path in sorted(files):
        archive.add(path, arcname='governor/' + str(path.relative_to(root)), recursive=False)
digest = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n')
print(f'{output}\n{output.stat().st_size:,} bytes; SHA-256 {digest}')
