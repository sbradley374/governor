#!/usr/bin/env python3
"""Download official OpenCV Zoo models; validate each against its Git LFS SHA-256."""
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

REPO = "https://api.github.com/repos/opencv/opencv_zoo/commits/main"
# Resolve a single immutable revision, record it, then use it for both metadata and bytes.
# Set OPENCV_ZOO_REVISION to reuse a reviewed revision from models/manifest.json.
revision = os.getenv("OPENCV_ZOO_REVISION")
if not revision:
    with urllib.request.urlopen(REPO, timeout=30) as response:
        revision = json.load(response)["sha"]
if not re.fullmatch(r"[0-9a-f]{40}", revision):
    raise SystemExit("Expected a 40-character Git commit hash")
root = Path(os.getenv("GOVERNOR_MODEL_DIR", "models"))
root.mkdir(parents=True, exist_ok=True)
models = {
    "yunet.onnx": "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface.onnx": "models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
manifest = {"repository": "opencv/opencv_zoo", "revision": revision, "files": {}}
for name, path in models.items():
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/opencv/opencv_zoo/{revision}/{path}", timeout=30) as response:
        pointer = response.read().decode()
    expected = re.search(r"oid sha256:([0-9a-f]{64})", pointer).group(1)
    with urllib.request.urlopen(f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{revision}/{path}", timeout=120) as response:
        data = response.read(50 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit(f"Checksum mismatch for {name}; refusing to install")
    target = root / name
    temp = target.with_suffix(".part")
    temp.write_bytes(data)
    temp.replace(target)
    manifest["files"][name] = {"sha256": expected, "source": path}
    print(f"Verified {name}: {len(data):,} bytes")
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Models installed. See OpenCV Zoo for each model's license and attribution.")
