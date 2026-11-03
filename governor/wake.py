"""Offline wake phrase spotting using Vosk's small English model."""
import json


def is_wake(result, phrase="governor", confidence=0.75):
    text = result.get("text", "").strip().lower()
    words = result.get("result", [])
    return text in {phrase, "hey " + phrase} and bool(words) and all(
        word.get("conf", 0) >= confidence for word in words)


class WakeDetector:
    def __init__(self, path, phrase="governor"):
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
        except ImportError:
            raise SystemExit("Install wake extras: pip install -e '.[audio,wake]'") from None
        if not (path / "am" / "final.mdl").exists():
            raise SystemExit("Run python scripts/download-wake-model.py before governor listen")
        SetLogLevel(-1)
        self.phrase = phrase.strip().lower()
        self.model = Model(str(path))
        self.recognizer = KaldiRecognizer(self.model, 16000, json.dumps([self.phrase, "hey " + self.phrase, "[unk]"]))
        self.recognizer.SetWords(True)

    def reset(self):
        self.recognizer.Reset()

    def feed(self, block):
        if self.recognizer.AcceptWaveform(block):
            detected = is_wake(json.loads(self.recognizer.Result()), self.phrase)
            self.reset()
            return detected
        return False
