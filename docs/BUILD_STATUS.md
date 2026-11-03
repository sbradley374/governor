# Delivery status — November 2, 2026

## Implemented and exercised on the development Mac

- Demo backend, HTTP service, console, and animated CRT face.
- Profile CRUD, persistence, explicit memory commands, deletion, and conversation counts.
- Conversation serialization, cancellation, cross-profile history clearing, failure recovery.
- Cloud and local provider request contracts (mocked HTTP).
- Audio segmentation logic and conservative face matching logic.
- Browser visual preview in Safari; a scripted joke and expression preview exercised through the actual interface. JavaScript and shell syntax checks.
- Offline hardware workbench, persistent display preferences, idle dim/wake, and local voice-test endpoint.
- Session tokens reject old recordings/messages after speaker changes or server restart, before transcription.
- 21 passing Python tests and 3 passing JavaScript renderer regression tests.

## Implemented, still requiring external setup or hardware verification

- OpenAI transcription/reasoning: requires API key and account model access.
- Ollama + faster-whisper: requires optional dependencies and model downloads; Pi performance unmeasured.
- eSpeak synthesis and actual audio output: eSpeak is not installed on this Mac; Pi installer includes it.
- Browser microphone and native hands-free capture: need a microphone and device calibration.
- Camera recognition/enrollment: need USB UVC camera, camera extras, and downloaded OpenCV models.
- Raspberry Pi service, kiosk autostart, converter audio, and CRT overscan: require installation on the Pi.

No Pi connection or SSH host is available yet. No camera/microphone was activated. No paid API calls were made. Demo is not an LLM; choose cloud or local mode for real conversation.

## Deliberate first-version boundaries

No wake word, speech interruption, automatic speaker attribution, CSI camera adapter, automatic memory extraction, or physical motor control. The personality is a configured persona with explicit facts and familiarity, not an autonomous self-training system. The operator selects the current speaker; camera recognition offers presence suggestions.

Cloud remains the chosen backend for real conversation, but API setup is deferred. The development app runs in demo mode with no credentials or paid calls. The browser microphone meter is implemented but physical capture was not activated during development.
