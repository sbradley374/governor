import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    provider: str = "demo"
    api_key: str = ""
    model: str = "gpt-5.4-mini"
    local_model: str = "qwen2.5:1.5b"
    whisper_model: str = "tiny.en"
    transcribe_model: str = "gpt-transcribe"
    data_dir: Path = Path("data")
    model_dir: Path = Path("models")
    camera: bool = False
    camera_index: int = 0
    face_threshold: float = 0.5
    voice: str = "en-gb"
    speech_rate: int = 145

    @classmethod
    def from_env(cls):
        load_dotenv()
        config = cls(
            provider=os.getenv("GOVERNOR_PROVIDER", "demo"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("GOVERNOR_MODEL", "gpt-5.4-mini"),
            local_model=os.getenv("GOVERNOR_LOCAL_MODEL", "qwen2.5:1.5b"),
            whisper_model=os.getenv("GOVERNOR_WHISPER_MODEL", "tiny.en"),
            transcribe_model=os.getenv("GOVERNOR_TRANSCRIBE_MODEL", "gpt-transcribe"),
            data_dir=Path(os.getenv("GOVERNOR_DATA_DIR", "data")),
            model_dir=Path(os.getenv("GOVERNOR_MODEL_DIR", "models")),
            camera=os.getenv("GOVERNOR_CAMERA", "false").lower() == "true",
            camera_index=int(os.getenv("GOVERNOR_CAMERA_INDEX", "0")),
            face_threshold=float(os.getenv("GOVERNOR_FACE_THRESHOLD", "0.5")),
            voice=os.getenv("GOVERNOR_VOICE", "en-gb"),
            speech_rate=int(os.getenv("GOVERNOR_SPEECH_RATE", "145")),
        )
        if config.provider not in {"demo", "openai", "local"}:
            raise ValueError("GOVERNOR_PROVIDER must be demo, openai, or local")
        if config.provider == "openai" and not config.api_key:
            raise ValueError("Set OPENAI_API_KEY in .env, or use GOVERNOR_PROVIDER=demo")
        if not 0 < config.face_threshold < 1:
            raise ValueError("Face threshold must be between 0 and 1")
        return config
