"""Optional hands-free, half-duplex microphone worker (explicitly started by user)."""
import base64
import collections
import io
import os
import time
import wave

import httpx


class Segmenter:
    """30ms PCM blocks, 300ms pre-roll, 150ms onset, 900ms trailing silence."""
    def __init__(self, threshold=0.025):
        self.threshold = threshold
        self.reset()

    def reset(self):
        self.pre = collections.deque(maxlen=10)
        self.blocks = []
        self.onset = self.silent = 0
        self.active = False

    def feed(self, block, rms):
        voiced = rms >= self.threshold
        if not self.active:
            self.pre.append(block)
            self.onset = self.onset + 1 if voiced else 0
            if self.onset >= 5:
                self.active = True
                self.blocks = list(self.pre)
            return None
        self.blocks.append(block)
        self.silent = 0 if voiced else self.silent + 1
        if self.silent >= 30 or len(self.blocks) >= 1000:
            result = b"".join(self.blocks)
            self.reset()
            return result
        return None


def device(name):
    value = os.getenv(name, "")
    return int(value) if value.isdigit() else value or None


def run(port):
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        raise SystemExit("Install audio extras first: pip install -e '.[audio,wake]'")
    from pathlib import Path
    from .wake import WakeDetector
    # An OS file lock prevents two workers competing for mic/playback ownership.
    import fcntl
    data_dir = Path(os.getenv("GOVERNOR_DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    worker_lock = (data_dir / "audio-worker.lock").open("w")
    try:
        fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another Governor audio worker is already running")
    wake = WakeDetector(Path(os.getenv("GOVERNOR_MODEL_DIR", "models")) / "vosk-model-small-en-us-0.15")
    segmenter = Segmenter(float(os.getenv("GOVERNOR_VAD_THRESHOLD", "0.025")))
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=180, headers={"X-Governor-Client": "1"})
    print("Say 'Governor', pause until the face says listening, then speak. Wake detection stays local.")
    print("Camera greetings are controlled in the console. Say 'this is NAME' to select your archive.")
    print("Do not also record in the browser. Ctrl-C stops capture.")

    def play(result):
        try:
            current = client.get("/api/state").raise_for_status().json()
            if current["paused"] or current["turn_id"] != result["turn_id"]:
                return
            if not result["audio"]:
                print("Install espeak-ng for native voice; the reply is visible on the CRT.")
                return
            with wave.open(io.BytesIO(base64.b64decode(result["audio"]))) as wav:
                samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).reshape(-1, wav.getnchannels())
                sd.play(samples, wav.getframerate(), device=device("GOVERNOR_OUTPUT_DEVICE"))
                while sd.get_stream().active:
                    current = client.get("/api/state").raise_for_status().json()
                    if current["paused"] or current["turn_id"] != result["turn_id"]:
                        break
                    time.sleep(0.1)
        finally:
            sd.stop()
            client.post("/api/playback/done", json={"turn_id": result["turn_id"]}).raise_for_status()
            time.sleep(0.35)  # Let the TV finish before reopening the microphone.

    try:
        while True:
            try:
                state = client.get("/api/state").raise_for_status().json()
                if state["paused"] or state["status"] != "idle":
                    time.sleep(0.25)
                    continue
                result = client.post("/api/room/check").raise_for_status().json()["greeting"]
                if result:
                    play(result)
                    continue
                session_id = state["session_id"]
                awake = state.get("awake", False)
                pcm = None
                capture_reserved = False
                segmenter.reset()
                wake.reset()
                # Close capture before playback to prevent the Governor waking itself.
                with sd.RawInputStream(samplerate=16000, blocksize=480, channels=1, dtype="int16", device=device("GOVERNOR_INPUT_DEVICE")) as mic:
                    blocks = 0
                    while pcm is None and result is None:
                        chunk, overflow = mic.read(480)
                        if overflow:
                            segmenter.reset()
                            wake.reset()
                            continue
                        block = bytes(chunk)
                        if awake:
                            samples = np.frombuffer(block, dtype=np.int16).astype(np.float32) / 32768
                            pcm = segmenter.feed(block, float(np.sqrt(np.mean(samples * samples))))
                            if segmenter.active and not capture_reserved:
                                client.post("/api/capture", json={"session_id": session_id}).raise_for_status()
                                capture_reserved = True
                        elif wake.feed(block):
                            state = client.post("/api/activate", json={"session_id": session_id}).raise_for_status().json()
                            session_id, awake = state["session_id"], True
                            print("Listening. Say your message, or 'this is NAME'.")
                            segmenter.reset()
                        blocks += 1
                        if blocks % 10 == 0 or pcm:
                            state = client.get("/api/state").raise_for_status().json()
                            if state["paused"] or state["status"] != "idle" or state["session_id"] != session_id:
                                pcm = None
                                break
                            if not awake and blocks % 30 == 0:
                                result = client.post("/api/room/check").raise_for_status().json()["greeting"]
                if result:
                    play(result)
                    continue
                if not pcm:
                    continue
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(pcm)
                result = client.post("/api/audio", data={"session_id": session_id}, files={"file": ("speech.wav", buf.getvalue(), "audio/wav")}).raise_for_status().json()
                play(result)
            except (httpx.HTTPError, sd.PortAudioError) as exc:
                print(f"Audio worker waiting: {type(exc).__name__}. Check server, devices, and provider settings.")
                time.sleep(2)
    except KeyboardInterrupt:
        print("Microphone stopped.")
    finally:
        sd.stop()
        client.close()
        worker_lock.close()
