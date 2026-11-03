import asyncio
import base64
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Literal

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .brain import Brain
from .camera import Camera
from .config import Config
from .memory import Memory
from .diagnostics import inspect_setup


class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None


class DisplaySettings(BaseModel):
    palette: Literal["green", "amber", "ice"] = "green"
    brightness: float = Field(default=0.85, ge=0.2, le=1)
    inset: float = Field(default=0.04, ge=0, le=0.15)
    idle_seconds: int = Field(default=120, ge=30, le=3600)


class FacePreview(BaseModel):
    emotion: Literal["neutral", "happy", "curious", "thinking", "sad", "surprised"]


class SessionInput(BaseModel):
    session_id: Optional[str] = None


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    consent: bool = False


class Selection(BaseModel):
    person_id: Optional[str] = None


class Consent(BaseModel):
    consent: bool = False


class Playback(BaseModel):
    turn_id: str


class Power(BaseModel):
    paused: bool


class Controller:
    def __init__(self, config):
        self.config = config
        self.memory = Memory(config.data_dir)
        self.brain = Brain(config)
        self.camera = Camera(config, self.memory)
        self.lock = asyncio.Lock()
        self.selected = None
        self.history = []  # Ephemeral and erased on every speaker switch.
        self.epoch = 0
        self.session_id = str(uuid.uuid4())
        self.paused = False
        self.status = "idle"
        self.emotion = "neutral"
        self.caption = "THE GOVERNOR IS IN RESIDENCE."
        self.transcript = ""
        self.error = None
        self.turn_id = None
        self.speaking_until = 0
        self.last_turn = float("-inf")
        self.last_activity = time.monotonic()
        self.preview = None
        self.preview_until = 0
        self.display = DisplaySettings(**self.memory.setting("display", {}))

    def state(self):
        if self.status == "speaking" and time.monotonic() > self.speaking_until:
            self.status = "idle"
        now = time.monotonic()
        preview = self.preview if now < self.preview_until and self.status == "idle" else None
        return {"status": self.status, "emotion": self.emotion, "caption": self.caption,
                "transcript": self.transcript, "error": self.error, "paused": self.paused,
                "selected": self.selected, "provider": self.config.provider,
                "turn_id": self.turn_id, "camera": self.camera.snapshot(),
                "session_id": self.session_id, "display": self.display.model_dump(),
                "preview": preview, "dimmed": self.status == "idle" and now - self.last_activity > self.display.idle_seconds}

    def invalidate(self):
        self.epoch += 1
        self.session_id = str(uuid.uuid4())
        self.history = []
        self.status = "paused" if self.paused else "idle"
        self.turn_id = None
        self.caption = "STANDING BY."
        self.transcript = ""
        self.error = None
        self.last_activity = time.monotonic()
        self.preview = None

    async def turn(self, text=None, audio=None, session_id=None, voice_test=False):
        self.state()
        if session_id is not None and session_id != self.session_id:
            raise HTTPException(409, "The speaker or session changed. Please start a new recording or message.")
        if self.paused:
            raise HTTPException(409, "The Governor is paused")
        if self.lock.locked() or self.status == "speaking":
            raise HTTPException(409, "The Governor is finishing a turn")
        if time.monotonic() - self.last_turn < 0.5:
            raise HTTPException(429, "Please wait a moment before the next turn")
        async with self.lock:
            epoch, person_id = self.epoch, self.selected
            self.error = None
            self.last_turn = time.monotonic()
            self.last_activity = self.last_turn
            self.preview = None
            try:
                if audio:
                    self.status = "listening"
                    text = await self.brain.transcribe(*audio)
                if epoch != self.epoch:
                    raise HTTPException(409, "Turn cancelled")
                text = (text or "").strip()
                if not text:
                    raise HTTPException(422, "No speech or text received")
                if len(text) > 2000:
                    raise HTTPException(422, "Please keep each turn under 2000 characters")
                self.status, self.emotion, self.transcript = "thinking", "thinking", text
                profile = self.memory.person(person_id) if person_id else None
                remember = re.match(r"^remember that\s+(.+)$", text, re.I | re.S)
                if voice_test:
                    result = {"text": "The Governor is in residence. One, two, three. This is a local speaker test.", "emotion": "happy"}
                elif remember:
                    if person_id:
                        self.memory.remember(person_id, remember.group(1))
                        result = {"text": "Filed in your personal archive. A small victory for organized thought.", "emotion": "happy"}
                    else:
                        result = {"text": "Choose or create a profile first, so I know whose archive this belongs in.", "emotion": "curious"}
                else:
                    result = await self.brain.reply(text, profile, self.memory.facts(person_id) if person_id else [], self.history)
                if epoch != self.epoch:
                    raise HTTPException(409, "Turn cancelled")
                # Speech synthesis failure should not discard a good text reply.
                try:
                    wav = await self.brain.speech(result["text"])
                except (OSError, asyncio.TimeoutError):
                    wav = None
                if epoch != self.epoch:
                    raise HTTPException(409, "Turn cancelled")
                if not voice_test:
                    self.history = (self.history + [{"role": "user", "content": text}, {"role": "assistant", "content": result["text"]}])[-12:]
                if person_id and not voice_test:
                    self.memory.interacted(person_id)
                self.last_activity = time.monotonic()
                self.caption, self.emotion = result["text"], result["emotion"]
                self.status, self.turn_id = "speaking", str(uuid.uuid4())
                self.speaking_until = time.monotonic() + min(120, max(15, len(result["text"]) / 9))
                return {**result, "transcript": text, "turn_id": self.turn_id, "audio": base64.b64encode(wav).decode() if wav else None}
            except HTTPException:
                if epoch == self.epoch:
                    self.status = "paused" if self.paused else "idle"
                raise
            except Exception as exc:
                if epoch == self.epoch:
                    self.status, self.emotion = "idle", "sad"
                    if isinstance(exc, httpx.HTTPStatusError):
                        self.error = f"Cloud service returned {exc.response.status_code}. Check API access, credits, and model settings."
                    elif isinstance(exc, httpx.RequestError):
                        self.error = "Cloud connection failed. Check the network and try again."
                    elif isinstance(exc, ValueError):
                        self.error = str(exc)[:160]
                    else:
                        self.error = "This turn failed. Check the device configuration and try again."
                    self.caption = "A TEMPORARY BUREAUCRATIC DIFFICULTY."
                raise HTTPException(503, self.error or "Turn cancelled") from None


def create_app(config=None):
    config = config or Config.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.controller = Controller(config)
        app.state.controller.camera.start()
        yield
        app.state.controller.camera.close()
        await app.state.controller.brain.close()
        app.state.controller.memory.close()

    app = FastAPI(title="The Governor", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_guard(request, call_next):
        # Bind to loopback; reject cross-origin browser mutations and DNS rebinding.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin requests are disabled"}, status_code=403)
            if request.headers.get("x-governor-client") != "1":
                return JSONResponse({"detail": "Missing local client header"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    def ctl():
        return app.state.controller

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Profile not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/state")
    async def state():
        return ctl().state()

    @app.get("/api/health")
    async def health():
        return {"ok": True, "provider": config.provider, "camera": ctl().camera.snapshot()["status"]}

    @app.post("/api/turn")
    async def turn(body: TextInput):
        return await ctl().turn(text=body.text, session_id=body.session_id)

    @app.get("/api/setup")
    async def setup():
        return inspect_setup(config, ctl().camera.snapshot())

    @app.post("/api/display")
    async def display(body: DisplaySettings):
        ctl().memory.save_setting("display", body.model_dump())
        ctl().display = body
        ctl().last_activity = time.monotonic()
        return body.model_dump()

    @app.post("/api/preview")
    async def preview(body: FacePreview):
        if ctl().state()["status"] != "idle" or ctl().lock.locked():
            raise HTTPException(409, "Finish the conversation or resume before previewing a face")
        ctl().preview = body.emotion
        ctl().preview_until = time.monotonic() + 8
        ctl().last_activity = time.monotonic()
        return ctl().state()

    @app.post("/api/wake")
    async def wake():
        ctl().last_activity = time.monotonic()
        return {"ok": True}

    @app.post("/api/test-voice")
    async def test_voice(body: SessionInput):
        return await ctl().turn(text="Speaker test", session_id=body.session_id, voice_test=True)

    @app.post("/api/audio")
    async def audio(file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
        allowed = {"audio/webm": "webm", "audio/wav": "wav", "audio/x-wav": "wav", "audio/ogg": "ogg", "audio/mp4": "mp4"}
        content_type = (file.content_type or "").split(";")[0]
        if content_type not in allowed:
            raise HTTPException(415, "Use WAV, WebM, Ogg, or MP4 audio")
        data = await file.read(4 * 1024 * 1024 + 1)
        await file.close()
        if len(data) > 4 * 1024 * 1024:
            raise HTTPException(413, "Recording too large; keep it under 30 seconds")
        return await ctl().turn(audio=(data, "speech." + allowed[content_type], content_type), session_id=session_id)

    @app.post("/api/playback/done")
    async def playback(body: Playback):
        if body.turn_id == ctl().turn_id and ctl().status == "speaking":
            ctl().status = "idle"
            ctl().last_activity = time.monotonic()
        return {"ok": True}

    @app.post("/api/power")
    async def power(body: Power):
        ctl().paused = body.paused
        ctl().invalidate()
        return ctl().state()

    @app.get("/api/people")
    async def people():
        return ctl().memory.people()

    @app.post("/api/people")
    async def create_person(body: ProfileInput):
        if not body.consent:
            raise HTTPException(422, "Ask the person before saving a profile")
        return ctl().memory.create(body.name)

    @app.post("/api/select")
    async def select(body: Selection):
        if body.person_id:
            ctl().memory.person(body.person_id)
        ctl().selected = body.person_id
        ctl().invalidate()
        return ctl().state()

    @app.delete("/api/people/{ident}")
    async def delete_person(ident: str):
        ctl().memory.delete(ident)
        if ctl().selected == ident:
            ctl().selected = None
            ctl().invalidate()
        return {"ok": True}

    @app.get("/api/people/{ident}/memories")
    async def memories(ident: str):
        ctl().memory.person(ident)
        return ctl().memory.facts(ident)

    @app.post("/api/people/{ident}/memories")
    async def remember(ident: str, body: TextInput):
        return ctl().memory.remember(ident, body.text)

    @app.delete("/api/people/{ident}/memories/{fact_id}")
    async def forget(ident: str, fact_id: str):
        ctl().memory.forget(ident, fact_id)
        # Discard conversational context that may contain the removed fact.
        if ctl().selected == ident:
            ctl().invalidate()
        return {"ok": True}

    @app.post("/api/people/{ident}/face")
    async def enroll(ident: str, body: Consent):
        if not body.consent:
            raise HTTPException(422, "Face enrollment needs the person's consent")
        ctl().camera.enroll(ident)
        return {"ok": True}

    @app.delete("/api/people/{ident}/face")
    async def forget_face(ident: str):
        ctl().memory.forget_face(ident)
        return {"ok": True}

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    return app
