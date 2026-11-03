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
        raise SystemExit("Install audio extras first: pip install -e '.[audio]'")
    threshold = float(os.getenv("GOVERNOR_VAD_THRESHOLD", "0.025"))
    segmenter = Segmenter(threshold)
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=180, headers={"X-Governor-Client": "1"})
    print("Hands-free microphone ON. All detected utterances are processed; there is no wake word.")
    print("Use the console to select a speaker or pause. Ctrl-C stops capture. Do not also record in the browser.")
    try:
        while True:
            try:
                state = client.get("/api/state").raise_for_status().json()
                if state["provider"] == "demo":
                    raise SystemExit("Use openai or local mode for microphone transcription.")
                if state["paused"] or state["status"] != "idle":
                    time.sleep(0.25)
                    continue
                pcm = None
                session_id = state["session_id"]
                segmenter.reset()
                # Closing input before speaking prevents self-triggering and stale audio queues.
                with sd.RawInputStream(samplerate=16000, blocksize=480, channels=1, dtype="int16", device=device("GOVERNOR_INPUT_DEVICE")) as mic:
                    blocks = 0
                    while pcm is None:
                        chunk, overflow = mic.read(480)
                        if overflow:
                            segmenter.reset()
                            continue
                        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768
                        pcm = segmenter.feed(bytes(chunk), float(np.sqrt(np.mean(samples * samples))))
                        blocks += 1
                        if blocks % 10 == 0 or pcm:
                            state = client.get("/api/state").raise_for_status().json()
                            if state["paused"] or state["status"] != "idle" or state["session_id"] != session_id:
                                pcm = None
                                break
                if not pcm:
                    continue
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(pcm)
                response = client.post("/api/audio", data={"session_id": session_id}, files={"file": ("speech.wav", buf.getvalue(), "audio/wav")})
                response.raise_for_status()
                result = response.json()
                try:
                    if not result["audio"]:
                        print("No server voice available. Install espeak-ng; reply is visible on the CRT.")
                    else:
                        with wave.open(io.BytesIO(base64.b64decode(result["audio"]))) as wav:
                            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).reshape(-1, wav.getnchannels())
                            sd.play(samples, wav.getframerate(), device=device("GOVERNOR_OUTPUT_DEVICE"))
                            # Allow pause/speaker switch to stop playback promptly.
                            while sd.get_stream().active:
                                current = client.get("/api/state").raise_for_status().json()
                                if current["paused"] or current["turn_id"] != result["turn_id"]:
                                    sd.stop()
                                    break
                                time.sleep(0.1)
                finally:
                    sd.stop()
                    client.post("/api/playback/done", json={"turn_id": result["turn_id"]})
                time.sleep(0.35)
            except (httpx.HTTPError, sd.PortAudioError) as exc:
                print(f"Audio worker waiting: {type(exc).__name__}. Check server, devices, and provider settings.")
                time.sleep(2)
    except KeyboardInterrupt:
        print("Microphone stopped.")
    finally:
        sd.stop()
        client.close()
