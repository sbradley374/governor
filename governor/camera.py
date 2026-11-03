"""Optional local YuNet/SFace recognition. Camera frames never leave this module."""
import threading
import time


def choose_match(scores, threshold=0.5, margin=0.08):
    """Reject weak or ambiguous matches; never force a nearest identity."""
    ranked = sorted(scores, key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < threshold:
        return None
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < margin:
        return None
    return ranked[0][0]


class Camera:
    def __init__(self, config, memory):
        self.config, self.memory = config, memory
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.status = "disabled"
        self.present = []
        self.face_count = 0
        self.feature = None
        self.updated = 0.0

    def start(self):
        if self.config.camera:
            self.status = "starting"
            self.thread = threading.Thread(target=self.run, daemon=True, name="governor-camera")
            self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=4)

    def snapshot(self):
        with self.lock:
            fresh = time.monotonic() - self.updated < 3
            return {"status": self.status, "present": self.present if fresh else [], "face_count": self.face_count if fresh else 0}

    def enroll(self, ident):
        with self.lock:
            if self.status != "running" or self.face_count != 1 or self.feature is None or time.monotonic() - self.updated > 2:
                raise ValueError("Enrollment needs exactly one clearly visible face in the camera right now")
            self.memory.enroll(ident, self.feature)

    def run(self):
        capture = None
        try:
            import cv2
            import numpy as np
            detector = cv2.FaceDetectorYN.create(str(self.config.model_dir / "yunet.onnx"), "", (640, 480), 0.9)
            recognizer = cv2.FaceRecognizerSF.create(str(self.config.model_dir / "sface.onnx"), "")
            capture = cv2.VideoCapture(self.config.camera_index)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if not capture.isOpened():
                raise RuntimeError("Camera unavailable; check index and permissions")
            streaks = {}
            while not self.stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Camera disconnected; restart after reconnecting")
                h, w = frame.shape[:2]
                detector.setInputSize((w, h))
                _, faces = detector.detect(frame)
                faces = [] if faces is None else faces
                vectors = self.memory.embeddings()
                found, features = set(), []
                for face in faces:
                    feature = recognizer.feature(recognizer.alignCrop(frame, face))
                    features.append(feature.flatten().tolist())
                    scores = [(ident, float(recognizer.match(feature, np.array(vector, dtype=np.float32).reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE))) for ident, vector in vectors]
                    match = choose_match(scores, self.config.face_threshold)
                    if match:
                        found.add(match)
                streaks = {ident: streaks.get(ident, 0) + 1 for ident in found}
                with self.lock:
                    self.status = "running"
                    self.face_count = len(faces)
                    self.feature = features[0] if len(features) == 1 else None
                    self.present = [ident for ident, count in streaks.items() if count >= 3]
                    self.updated = time.monotonic()
                self.stop_event.wait(0.35)
        except ImportError:
            self.status = "Install camera extras: pip install -e '.[camera]'"
        except Exception as exc:
            # Avoid dumping huge OpenCV internals into the UI.
            self.status = str(exc)[:160] if isinstance(exc, RuntimeError) else "Camera setup failed: check models, camera index, and OpenCV installation"
        finally:
            if capture is not None:
                capture.release()
            with self.lock:
                self.present, self.feature, self.face_count = [], None, 0
