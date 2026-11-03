# Pi 5 installation and hardware bring-up

## What you need

Already owned: Pi 5 with 8 GB, Raspberry Pi OS desktop, CRT, HDMI-to-composite converter. No change to the working video cable or boot firmware configuration is required.

Next: a USB microphone compatible with standard Linux USB audio. A simple wired microphone is enough for initial tests; room-distance conversation benefits from a microphone array or speakerphone. Optional: a USB UVC webcam. A Pi CSI camera requires a different capture adapter (Picamera2) and is not implemented in this version.

The TV can be the speaker if the converter outputs HDMI audio on its white RCA connection. Confirm that before buying speakers. Use the Pi's proper power supply and cooling. No need to open the CRT enclosure.

## Transfer and install

Without SSH, copy `dist/governor-pi.tar.gz` onto a USB drive, then on the Pi run:

```sh
cd ~
tar -xzf /path/on/usb/governor-pi.tar.gz
cd ~/governor
bash scripts/setup-pi.sh
.venv/bin/governor serve --demo
```

This archive contains a `governor/` project directory. For an existing installation, stop its services and back up the project/data before extracting an update. The archive never includes `.env` or `data`, so it cannot supply or overwrite those files. Alternatively, clone the private GitHub repository on the Pi using your GitHub authentication, or copy the source directory. Exclude `.venv`, `__pycache__`, `data`, and any `.env` containing a key; create the Pi's environment locally. Do not copy a macOS virtual environment onto Linux.

With SSH enabled in Raspberry Pi OS Control Centre or `sudo raspi-config`, transfer from the Mac:

```sh
rsync -av --exclude=.venv --exclude=.env --exclude=data --exclude=__pycache__ \
  /path/to/governor/ YOUR_USER@YOUR_PI_HOST:governor/
ssh YOUR_USER@YOUR_PI_HOST
cd ~/governor
bash scripts/setup-pi.sh
.venv/bin/governor serve
```

The installer uses apt to install Python venv support, Chromium, PortAudio, ALSA tools, and eSpeak NG. It installs optional audio/camera/wake Python packages, but does not open a microphone/camera or download face models. On an OS that names the browser `chromium-browser`, adjust the apt package name; the kiosk launcher supports both executable names.

On the Pi, open `http://localhost:8765`. Start in demo mode and type a greeting. The Workbench lets you preview expressions, save display settings, test speech, and check microphone levels without the API. No microphone is needed yet. To control it from the Mac:

```sh
ssh -N -L 8765:127.0.0.1:8765 YOUR_USER@YOUR_PI_HOST
```

Then use `http://localhost:8765` on the Mac. Stop the Mac demo server first if it occupies that port. Browser audio uses the microphone/speaker of the computer running that browser. For Pi audio while controlling from the Mac, use the native Pi microphone worker below.

## TV and sound

1. Keep the converter's NTSC/PAL setting that already works with your TV.
2. Select the Pi's connected HDMI output in desktop sound settings. Connect white RCA audio to the TV's audio input.
3. Test a normal sound or run `speaker-test -c 2 -t wav`. Stop with Ctrl-C.
4. Test speech with `espeak-ng -v en-gb 'The Governor is in residence.'`.
5. If silent, check TV input/volume, the converter's power, HDMI output selection, and `aplay -l`.
6. Use `bash scripts/kiosk.sh` on the Pi desktop for a fullscreen 4:3 face. Exit Chromium kiosk with Alt-F4. Text and facial features are inset for overscan; use a 4:3 display mode on the converter/TV if supported.

The face uses 640×480 drawing coordinates. This does not force the HDMI electrical output mode. The converter handles that. Low TV brightness and switching the display off when unattended remain sensible; blinking alone does not prevent CRT burn-in.

## Microphone

Set cloud or local mode first. For two-click recording, open the console **on the Pi**, click Talk, grant microphone access, speak, and click again. Recording is limited to 30 seconds. Headphones or low TV volume help initial calibration.

For hands-free room use, open a second Pi terminal:

```sh
cd ~/governor
.venv/bin/python scripts/download-wake-model.py
.venv/bin/governor doctor
.venv/bin/governor listen
```

This enables continuous **local** wake detection with the small Vosk English model (about 40 MB download). The model downloader verifies a pinned SHA-256 checksum. Say **Governor** or **Hey Governor**, pause until the face says it is listening, then speak your message. The wake utterance is discarded locally. Only clips recorded in the active reply window are submitted to the configured transcription backend. Cloud mode uploads those clips; local mode processes them locally.

The default follow-up window is 20 seconds after each reply; once speech starts, the worker allows up to 30 seconds to finish it (a 35-second server timeout includes trailing silence). **Room manners** lets you choose 5–60 seconds. Other speech or TV noise inside that window can be treated as a reply, so keep it short in a shared/noisy room. When the window expires, the worker clears the selected speaker and waits for the next wake phrase. Say **this is Sam** as a separate turn to select an existing uniquely named profile. This is a self-introduction, not voice authentication.

Detection uses constrained local speech recognition, not a separately trained custom keyword model. Its threshold and the TV/microphone arrangement need real-room testing. The bundled model is English-only. A synthetic sample passed on the Mac; that does not establish real microphone accuracy. Input closes while replies are generated/played to avoid hearing the TV's own response. This is half-duplex; natural interruption/barge-in is not implemented. Pause in the console stops processing, and Ctrl-C ends the worker.

Set `GOVERNOR_INPUT_DEVICE` and `GOVERNOR_OUTPUT_DEVICE` from the doctor's audio device list if defaults are wrong. The worker expects a device supporting 16 kHz mono capture. Adjust `GOVERNOR_VAD_THRESHOLD` (default 0.025) upward for noise or downward for quiet speech. Wake detection can mishear television/music, and the energy detector can trigger on noise during a reply window; use two-click recording in noisy rooms. Do not run two workers or record in the browser simultaneously.

## Camera and profiles

```sh
.venv/bin/python scripts/download-face-models.py
```

The download script resolves one OpenCV Zoo revision, verifies models against the repository's Git LFS SHA-256 hashes, and records a manifest. Preserve that manifest to repeat the same model version. Model licenses are in the corresponding [OpenCV Zoo directories](https://github.com/opencv/opencv_zoo/tree/main/models).

In `.env`, set `GOVERNOR_CAMERA=true`, then restart Governor. Create a profile with the person's agreement. With only that person visible, click Enroll face and confirm. The camera is enabled by configuration; Pause stops conversation, not the camera. To stop camera capture, set the camera setting false and restart.

Recognition remains local. Raw frames are not saved or sent to the LLM. The database stores a numeric face template, which is still biometric data; protect the Pi and its backups. “Remove face” deletes the template; “Forget person” deletes profile, template, and facts.

Tune and test under actual room lighting. Unknown and ambiguous faces should remain unknown. A photo can fool this recognizer; it is not authentication or liveness detection. Recognition shows possible presence but **never automatically selects the speaker**. Choose the speaker in the console during an active reply window, or introduce yourself by name. Only one speaker profile is active at a time; ask people to take turns.

Enable **Greet people arriving in the room** in Room manners, and keep `governor listen` running. Arrivals must remain visible for three seconds; departures take fifteen seconds to rearm, so a brief camera dropout does not repeat a hello. Greetings require an idle controller, no active reply window, and thirty seconds since the last interaction. The default global cooldown is ten minutes. Arrivals seen while paused or busy are not queued for later interruption. A named greeting uses only the recognized name, never personal memory; a reply window opens as a visitor. Start a new approach after the room has been quiet to test this behavior.

## Startup

After manual testing succeeds:

```sh
bash scripts/install-service.sh
journalctl --user -u governor -f
```

This installs a user service, starts it, and enables it for the user's session. Enable desktop autologin in Raspberry Pi OS if you want the kiosk to come up without typing a password. For a server that must start without a login, configure user lingering intentionally with `sudo loginctl enable-linger YOUR_USER`.

To start the fullscreen face with your desktop session, run:

```sh
bash scripts/install-kiosk.sh
```

The hands-free microphone worker is not auto-enabled by the main installer. After calibration and model download:

```sh
bash scripts/install-audio-service.sh
journalctl --user -u governor-audio -f
```

This explicitly enables the microphone worker for the user session. Stop it with `systemctl --user disable --now governor-audio`. It reconnects after server failures; a file lock prevents duplicate native workers. Do not use browser recording while this worker is running.

Stop/disable the server: `systemctl --user disable --now governor`. Remove kiosk autostart by deleting `~/.config/autostart/governor.desktop`.

## Hardware acceptance checklist

- Face remains readable and inside the CRT's edges; expressions and speech animation work.
- TV speaks a demo reply without buzzing, clipping, or missing an audio channel.
- Five spoken sentences transcribe correctly at your intended distance.
- Say Governor ten times at room distance and count misses; test ten unrelated phrases and TV background noise for false wakes.
- Silence/noise does not repeatedly create paid turns; follow-up windows expire and clear the profile.
- Enter/leave the camera view: one greeting, no repeats while present, and cooldown respected.
- Enable automatic memory for a test profile, correct a note, restart, and verify recall; erase it afterward.
- Switching the speaker clears the previous conversation; facts survive restart.
- Two enrolled people, an unknown visitor, bad lighting, and two simultaneous faces behave sensibly.
- Pausing during a slow response prevents its late playback.
- Unplugging network/camera/mic produces a recoverable failure instead of a stuck conversation.
- A 30-minute session has acceptable response times, CPU temperature, and cloud cost.

These checks require the real Pi and peripherals; development-machine tests cannot establish them.

Implementation references: [Vosk model catalog](https://alphacephei.com/vosk/models), [Vosk constrained recognition example](https://github.com/alphacep/vosk-api/blob/master/python/example/test_words.py).
