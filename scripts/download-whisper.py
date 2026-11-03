#!/usr/bin/env python3
"""Explicit one-time network download; runtime local mode never downloads models."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from governor.config import Config
from faster_whisper import WhisperModel

config = Config.from_env()
WhisperModel(config.whisper_model, device="cpu", compute_type="int8", download_root=str(config.model_dir / "whisper"))
print("Whisper model downloaded. Local speech recognition is ready.")
