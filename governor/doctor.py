import importlib.util
import platform
import shutil
from .config import Config


def run():
    print("THE GOVERNOR / device check")
    print(f"System: {platform.system()} {platform.machine()} / Python {platform.python_version()}")
    try:
        config = Config.from_env()
    except ValueError as exc:
        print(f"Configuration: {exc}")
        return
    print(f"Provider: {config.provider} / API key: {'configured' if config.api_key else 'not configured'}")
    print(f"Speech engine: {shutil.which('espeak-ng') or shutil.which('espeak') or 'missing (browser fallback only)'}")
    print(f"Data: {config.data_dir.resolve()}")
    for package in ['sounddevice', 'cv2', 'faster_whisper']:
        print(f"{package}: {'installed' if importlib.util.find_spec(package) else 'not installed (optional)'}")
    for name in ['yunet.onnx', 'sface.onnx']:
        print(f"{name}: {'found' if (config.model_dir / name).exists() else 'not downloaded'}")
    if importlib.util.find_spec('sounddevice'):
        import sounddevice
        try:
            print(sounddevice.query_devices())
        except Exception as exc:
            print(f"Audio device query failed: {exc}")
    print("Camera is not opened by doctor. Use the console after enabling it in .env.")
