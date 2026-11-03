"""Readiness checks without opening devices, making network calls, or revealing keys."""
import importlib.util
import platform
import shutil


def inspect_setup(config, camera):
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    add("Conversation", "ready" if config.provider != "demo" else "demo",
        {"demo": "Offline rehearsal is active. Cloud setup can wait.",
         "openai": "Cloud mode configured. Account access has not been tested by this check.",
         "local": "Local AI configured. The model server has not been tested by this check."}[config.provider])
    synth = shutil.which("espeak-ng") or shutil.which("espeak")
    add("Speaker", "ready" if synth else "optional",
        "Local speech engine installed; use Test voice to check playback."
        if synth else "Browser voice fallback available where supported. Install espeak-ng on the Pi for native speech.")
    add("Microphone", "manual", "Use Check microphone below. It measures sound locally, without recording or uploading it.")
    audio_installed = importlib.util.find_spec("sounddevice") is not None
    add("Hands-free audio", "ready" if audio_installed else "optional",
        "Native audio package installed; devices still need calibration."
        if audio_installed else "Optional native microphone worker is not installed on this machine.")
    wake_ready = importlib.util.find_spec("vosk") is not None and (config.model_dir / "vosk-model-small-en-us-0.15" / "am" / "final.mdl").is_file()
    add("Wake phrase", "ready" if wake_ready else "optional",
        "Say Governor, pause, then speak. Run governor listen after calibrating the microphone."
        if wake_ready else "Install wake extras and run scripts/download-wake-model.py. Detection runs locally.")
    if camera["status"] == "running":
        add("Camera", "ready", f"Running locally; {camera['face_count']} face(s) visible.")
    elif not config.camera:
        add("Camera", "optional", "Off. Add a USB webcam and enroll a consenting person when ready.")
    else:
        add("Camera", "attention", camera["status"])
    add("Face models", "ready" if all((config.model_dir / f).is_file() for f in ("yunet.onnx", "sface.onnx")) else "optional",
        "Recognition uses local model files. Download them with scripts/download-face-models.py if needed.")
    add("Display", "manual", "Use the palette, brightness, and inset controls to fit the face to your CRT.")
    return {"system": f"{platform.system()} / {platform.machine()}", "provider": config.provider, "checks": checks}
