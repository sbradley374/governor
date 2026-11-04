# Delivery status — November 2, 2026 / v0.3

## Implemented and exercised on the development Mac

- Demo console, expressive CRT face, display preferences, workbench, and arrival rehearsal.
- Persistent profile memory: manual facts, optional automatic notes and session summaries, lexical retrieval, corrections, deletion, opt-out, and additive migration of existing databases.
- Demo memory extraction for “I like …” and “I am working on …”; actual LLM extraction contracts tested with mocked HTTP.
- Local Vosk wake detector recognizes a synthetic “Governor” sample without microphone access or cloud calls.
- Arrival debounce/cooldown/departure logic, general/named greetings, visitor reset, timed reply windows, and spoken profile selection.
- Cancellation prevents delayed model notes from being filed after a speaker/session change.
- Safari UI verified: arrival rehearsal, profile creation, enabling automatic memory, saving a demo preference/summary, and correcting a memory.
- 39 Python tests plus 3 JavaScript renderer tests pass. JavaScript and shell syntax checks pass.
- Pi setup and optional audio-service installer, checksummed model downloader, source-only portable archive builder.

## Still needs hardware or provider setup

- API key and account model access for real cloud reasoning/transcription; no paid API requests made.
- Pi access (SSH or USB transfer), installation, service startup, HDMI converter audio, and CRT framing.
- USB microphone: test room-distance wake accuracy, false activations, speech transcription, noise thresholds, and half-duplex playback.
- USB UVC camera: download face models, enroll consenting people, calibrate recognition, and test arrivals under actual room lighting.
- Local Ollama/faster-whisper remain optional and unmeasured on this Pi.

No microphone or camera was activated during development. Wake-model testing used synthetic audio written to a temporary file. The local app remains in no-key demo mode.

## Boundaries

There is no speaker diarization, voice authentication, liveness detection, speech interruption/barge-in, automatic face enrollment, CSI-camera adapter, or physical motor control. Face presence may trigger a greeting but never selects a personal archive. The persona uses remembered context; it does not retrain itself or develop real feelings.

Native wake/camera interaction is implemented and portable, but must be calibrated on the real Pi. Automatic memory adds input/output tokens to normal AI replies; local wake detection, local face recognition, fixed arrival greetings, SQLite storage, and local eSpeak add no API call charges. No monthly spending cap is enforced.

## Silent display milestone — November 4, 2026

A standalone local HTML face now provides randomized gaze, expressions, winks, blinking, and short rests without the backend, API, camera, microphone, or speaker. A small face-only archive and desktop-autostart installer are available. Seven JavaScript checks pass, including offline ambient behavior and renderer regressions. Physical Pi transfer/startup remains blocked by lack of network access and setup peripherals; a wired USB keyboard is the simplest next setup tool. See FACE_ONLY.md.
