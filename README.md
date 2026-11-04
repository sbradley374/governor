# The Governor

A retro CRT companion for a Raspberry Pi: an expressive face, a conversational voice, and a lasting memory for people who choose to be remembered.

**Built for your setup:** Raspberry Pi 5 / 8 GB, Raspberry Pi OS desktop, HDMI-to-composite converter, yellow video + white mono audio into the TV. Keep your existing working video configuration.

## Start with just the face

No microphone, camera, speaker, or API yet? Open `governor/static/ambient.html` for the silent standalone face: blinking, wandering eyes, expressions, winks, and little rests. It works offline without the backend. Use `python3 scripts/package-face.py` to make a small Pi transfer bundle, then follow [the face-only setup guide](docs/FACE_ONLY.md). A keyboard or another physical setup method is needed to get an offline Pi onto the network first.

## Try it now

Clone the repository and install the demo:

```sh
git clone https://github.com/sbradley374/governor.git
cd governor
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/governor serve --demo
```

Open **http://localhost:8765** for the console, or **http://localhost:8765/?display=1** for the face. The demo is scripted and needs no API key. Type a message, introduce a test profile, and try `remember that I enjoy old films`.

For a fresh machine:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/governor
```

## Build and rehearse without the API

Cloud is the intended conversation backend, but API setup is deferred. The example configuration starts in demo mode. `governor serve --demo` also overrides the provider for that process without changing saved configuration.

The **Workbench** at the bottom of the console works without a key:

- Preview all six expressions for eight seconds.
- Save green, amber, or ice-blue phosphor, brightness, face inset, and idle dimming. Settings apply to the CRT view and survive restarts.
- Click the face or send a message to wake it after idle dimming. Dimming reduces brightness; it is not a guarantee against CRT burn-in.
- **Test voice** uses local speech or a browser voice; it makes no AI call and does not alter memory/history/familiarity. Sound plays on the computer running the console.
- **Check microphone** measures input in this browser for ten seconds, releases the microphone, and never records or uploads samples. No microphone is needed to use the rest of the demo.
- Readiness checks show what still needs installation or physical testing. They do not open the camera or microphone or test cloud access.

Try `hello`, `who are you?`, `tell me a joke`, `wow`, or `what do you remember about me?` in the text console. These are deliberately scripted demo responses. Explicit memories still persist normally.

## What's implemented

- Canvas CRT face: six emotional expressions, blinking, gaze motion, listening animation, and speech animation. Browser WAV playback drives mouth amplitude; native audio uses a speaking-state animation.
- Two-click microphone recording (up to 30 seconds), text input, pause/resume, and sound controls.
- Offline “Governor” / “Hey Governor” wake detection, brief follow-up windows, voice activity detection, and half-duplex playback.
- Camera-triggered arrival greetings, a configurable cooldown, and a no-hardware greeting rehearsal.
- Cloud: OpenAI Responses + file transcription. Local: Ollama + faster-whisper. Speech synthesis: local eSpeak NG, with browser speech fallback for browser-initiated turns.
- SQLite profiles, opt-in automatic facts/preferences/projects and conversation summaries, relevant retrieval, correction/deletion controls, and familiarity from exchange count. Raw conversation history stays in RAM.
- Confirm the speaker in the console or say “this is NAME” for an existing profile. Camera presence never silently selects a personal archive.
- Local OpenCV YuNet/SFace recognition with confidence threshold, ambiguity rejection, and three-frame stabilization.
- Pi installer, user service, kiosk launcher, diagnostics, and automated tests.

This is a functional first version, **not yet hardware-validated on your Pi**. Cloud and Ollama contracts are tested with mocked responses; actual inference, microphone capture, TV audio, camera accuracy, and latency need device testing. No API key is configured and no paid API calls were made during development.

## Memory and room interaction (v0.3)

Create/select a profile, then enable **Remember useful details and conversation summaries automatically**. In demo mode, type `I like jazz` or `I am working on a robot`: the deliberately narrow rehearsal saves a note and a sample summary. Cloud/local AI modes extract useful notes from ordinary conversation using the same request as the reply. No extra memory API call or embedding service is needed; the larger response and retrieved context do add tokens to paid conversations.

The archive supports **Edit**, **Forget**, and **Erase all memories**. Automatic notes may correct other automatic notes; manually entered/edited facts are protected. Editing or forgetting a fact also clears that person's summaries, which might repeat the old information. Correcting a summary pins it as a manual note. Erase-all disables automatic saving too. Turning saving off alone keeps existing memories available for recall.

Use **Room manners → Rehearse an arrival** now, without a camera or API key. On the Pi, enable real arrival greetings after camera/audio setup. A single recognized face may get a named greeting; groups and unknown people get a general hello. A greeting opens a short reply window, but personal memory stays in visitor mode until a speaker is selected or introduces themself. The native worker returns to visitor mode after silence. There is no voice identification or simultaneous-speaker separation.

A transferable source archive can be generated with `python3 scripts/package-pi.py`; see [Pi setup](docs/PI_SETUP.md). Models, keys, personal data, and the Mac virtual environment are excluded.

## Choose a brain

Edit `.env`, then restart the server. The default remains `demo`.

### Cloud (recommended first)

```dotenv
GOVERNOR_PROVIDER=openai
OPENAI_API_KEY=your-key-here
GOVERNOR_MODEL=gpt-5.4-mini
GOVERNOR_TRANSCRIBE_MODEL=gpt-transcribe
```

Keep the key in `.env`, not in the browser or chat. The model must support Responses structured output and `reasoning.effort=none`; if changing model families, adjust `brain.py` accordingly. Local speech synthesis costs no API usage.

**Example cost at rates checked November 2, 2026:** 20 exchanges/day, each averaging 2,000 input tokens and 200 output tokens, plus 10 recorded minutes/day costs about **$2.79 per 30 days**. At 100 exchanges and 50 recorded minutes/day, about **$13.95**. Rates used: GPT-5.4 mini $0.75/M input and $4.50/M output; transcription $0.0045/min. Actual costs vary with history, retrieved memories, automatic memory output, recording duration, output, and pricing. The examples above do not add a separate allowance for automatic memory output. These are estimates, not spending limits. API billing is separate from a ChatGPT subscription. The application bounds each recording and reply but does not enforce a monthly dollar cap.

Sources: [model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [API pricing](https://developers.openai.com/api/docs/pricing?latest-pricing-expanded=true), [file transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [structured output](https://developers.openai.com/api/docs/guides/structured-outputs).

### Fully local

1. Install Ollama using the [official ARM64 Linux instructions](https://docs.ollama.com/linux), start its service, and run `ollama pull qwen2.5:1.5b`.
2. Install the optional speech recognition dependencies and explicitly download the model:

```sh
.venv/bin/pip install -e '.[local]'
.venv/bin/python scripts/download-whisper.py
```

3. Set:

```dotenv
GOVERNOR_PROVIDER=local
GOVERNOR_LOCAL_MODEL=qwen2.5:1.5b
GOVERNOR_WHISPER_MODEL=tiny.en
```

4. Restart Governor. Test with text first, then voice. Install `espeak-ng` for speech output.

The [Qwen model](https://ollama.com/library/qwen2.5:1.5b) download is about 986 MB; runtime RAM use is higher. The 8 GB Pi is a sensible platform to try this size, but expect a quality and speed tradeoff versus cloud. Local inference has no per-call API charge. Initial package/model downloads need internet; runtime transcription uses cached files only, and the LLM connects only to loopback. `tiny.en` is English-only; set `tiny` and download again for multilingual Whisper. Python package wheel availability can vary by Pi OS/Python version; if local extras cannot install, cloud mode and the rest of the application still work.

Reference: [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Don't run a large model, a camera, and a browser at maximum load without measuring Pi temperature and response latency.

## Install on your Pi

See [the Pi setup guide](docs/PI_SETUP.md) for copying files, enabling SSH, TV sound, camera setup, boot startup, and the hardware acceptance checklist. See [architecture and behavior](docs/ARCHITECTURE.md) for memory boundaries and current limitations.

## Development

```sh
.venv/bin/pytest -q
.venv/bin/governor doctor
node --check governor/static/app.js
node --check governor/static/face.js
node --test tests/face.test.cjs
```

Run a single server process. The app binds to loopback and rejects cross-origin mutations. Access it remotely through an SSH tunnel; do not expose it to the internet. Anyone with local access to the console can inspect/change profiles; this is a single-owner appliance, not a multi-user authenticated service.
