# Architecture and behavior

```mermaid
flowchart LR
  Mic[Browser recorder or native USB microphone] --> STT[Cloud transcription or local Whisper]
  STT --> Controller[Single conversation controller]
  Text[Text console] --> Controller
  Memory[(Local SQLite profiles and facts)] --> Controller
  Controller --> LLM[OpenAI Responses or local Ollama]
  LLM --> Voice[Local eSpeak NG]
  Voice --> Speaker[Browser or Pi audio output]
  Controller --> Face[CRT canvas: state and emotion]
  Camera[USB camera] --> Vision[Local YuNet and SFace]
  Vision --> Presence[Possible people present]
  Presence --> Console[Speaker selection console]
  Console --> Controller
```

## Division of work

`app.py` owns one robot state, one active speaker, and one asynchronous turn lock. Its API is loopback-only; host and origin guards prevent ordinary cross-site access. No cloud secrets appear in the browser. `brain.py` is the only module making inference requests. `memory.py` is a locked SQLite store. `camera.py` runs capture/inference on a background thread. `audio.py` is a separately started half-duplex worker. The browser polls state at 2 Hz; canvas animation runs independently.

State progresses idle → listening/transcribing → thinking → speaking → idle. Playback completion uses a turn ID, so an old completion cannot end a new utterance. A watchdog eventually releases speaking state if playback disappears. A unique session token also accompanies browser/native recordings and browser messages, rejecting stale submissions before transcription. Pause or speaker switch increments a generation, clears ephemeral history, and prevents an in-flight response from being played or assigned to the new speaker. An already-submitted cloud request may still incur charges when its response is discarded.

Server restarts lose the current selection and conversational context, but retain opted-in profiles/facts. Browser reloads retain the server's current session. Cloud requests set `store=false`; this does not assert that the provider has zero retention under all account policies.

## Personality and relationships

The Governor has a fixed persona: warm, curious, dryly funny, mildly bureaucratic. Its style receives a confirmed name, conversation count, and user-saved facts. The familiarity indicator grows after ten interactions. This provides continuity without inventing a psychological profile or claiming real feelings.

Memories are explicit: use the memory form or start an entire turn with `remember that ...`. Arbitrary model output never writes to the database. Each person can store 50 facts of up to 500 characters. The current speaker's most recent 12 conversation messages are kept in RAM; switching speakers or deleting an active memory clears them. Visitor conversation is also RAM-only, and no visitor facts are saved. Pause/resume resets the active conversation but retains the chosen profile.

The first version does not automatically summarize conversations, discover identity from voices, or infer personalities. Those can be evaluated later with correction controls. Long local prompts may exceed the small model's 4K context; keep facts concise and use a small set when running locally.

## Recognition

SFace templates are enrolled manually while exactly one face is visible. Matching requires a similarity above the configured threshold, a margin over the second-best match, and three consecutive recognition frames. Results expire if camera processing goes stale. Thresholds must be calibrated on the actual room, camera, and people.

Presence is not speaker identity. The console never changes the selected speaker just because somebody appears in the camera. There is no anti-spoofing, identity verification, surveillance archive, automatic enrollment, or face-image transmission. Camera errors do not take down conversation; reconnect and restart to recover a failed camera worker.

## Audio and physical deployment

Browser recording begins only after a click and permission, and stops after 30 seconds. The native worker is explicitly started with `governor listen`; it listens for speech energy, not a wake word. It opens the input only while the controller is idle, closes it before processing a turn, and waits for output playback before listening again. Pausing in the console stops capture at the next status check (about 300 ms). This avoids self-conversation but does not support barge-in.

In browser mode, audio comes from the browser that submitted the turn. A separate CRT display tab mirrors expressions but does not duplicate sound. In native mode, the Pi worker owns output. Native playback uses state-driven mouth motion; browser WAV output also uses an analyser for amplitude. If eSpeak is missing, browser turns can use speechSynthesis; the native worker instead leaves the reply visible and reports missing speech software.

## Storage and operation

Data is at `GOVERNOR_DATA_DIR/governor.sqlite3`. The directory is created with mode 0700, the DB with 0600, and the service uses umask 0077. SQLite secure deletion is enabled. Templates and facts are not encrypted at rest, and deletion does not erase independent backups or guarantee forensic erasure on flash media. Stop the service before backing up or restoring its directory. Treat backups like personal data.

Local users can access the console; there is no account/password layer. Do not expose the port on a LAN or public interface. Use SSH forwarding. The app has no device-execution tools, autonomous messaging, internet browsing, motors, or access control responsibilities.

## Next device milestones

1. Verify the face and HDMI-to-RCA audio on the Pi.
2. Connect a USB mic; measure cloud and local latency on ten fixed utterances.
3. Calibrate VAD in silence, normal conversation, and TV/music noise.
4. Add a UVC camera; measure known-person accuracy and unknown-person false matches.
5. Add a physical push-to-talk button or wake-word engine if hands-free use is desirable.
6. Consider streaming voice and echo cancellation for natural interruptions after the turn-based system is reliable.

## Validation completed here

Unit/integration tests exercise persistence, cascading deletion, profile isolation, consent flags, origin/host guards, pause behavior, cancellation of delayed replies, busy rejection, provider errors, cloud request schema, local loopback routing, ambiguous face rejection, and VAD onset/silence/maximum duration. A desktop Safari preview verifies the interface and face render.

Live cloud inference, local models, camera recognition, physical audio, boot behavior, and Pi performance are still unverified. The installation scripts are syntax-checked but were not executed on this macOS machine.

## Offline workbench and display settings

`/api/setup` reports passive readiness without probing devices or making external requests. `/api/test-voice` runs a constant local synthesis test through the normal playback lock and cancellation mechanism; it skips the LLM, history, and familiarity updates even in cloud mode. Microphone level measurement happens entirely in `workbench.js` and releases capture on stop, timeout, page hiding, or conversation activity.

Display settings live in the SQLite settings table, separate from people and facts. Expression previews expire after eight seconds and yield to conversation. Idle dimming is server-driven so all displays agree; wake, conversation, or a preview resets the timer. The canvas is capped at 30 frames per second, with occasional forced draws for state updates in background tabs. Routine HTTP access logging is disabled to avoid writing each state poll to the Pi's service journal.
