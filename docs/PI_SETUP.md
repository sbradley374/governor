# Pi 5 installation and hardware bring-up

## What you need

Already owned: Pi 5 with 8 GB, Raspberry Pi OS desktop, CRT, HDMI-to-composite converter. No change to the working video cable or boot firmware configuration is required.

Next: a USB microphone compatible with standard Linux USB audio. A simple wired microphone is enough for initial tests; room-distance conversation benefits from a microphone array or speakerphone. Optional: a USB UVC webcam. A Pi CSI camera requires a different capture adapter (Picamera2) and is not implemented in this version.

The TV can be the speaker if the converter outputs HDMI audio on its white RCA connection. Confirm that before buying speakers. Use the Pi's proper power supply and cooling. No need to open the CRT enclosure.

## Transfer and install

Without SSH, copy this project using a USB drive to `~/governor` on the Pi. Exclude `.venv`, `__pycache__`, `data`, and any `.env` containing a key; create the Pi's environment locally. Do not copy a macOS virtual environment onto Linux.

With SSH enabled in Raspberry Pi OS Control Centre or `sudo raspi-config`, transfer from the Mac:

```sh
rsync -av --exclude=.venv --exclude=.env --exclude=data --exclude=__pycache__ \
  /path/to/governor/ YOUR_USER@YOUR_PI_HOST:governor/
ssh YOUR_USER@YOUR_PI_HOST
cd ~/governor
bash scripts/setup-pi.sh
.venv/bin/governor serve
```

The installer uses apt to install Python venv support, Chromium, PortAudio, ALSA tools, and eSpeak NG. It installs optional audio/camera Python packages, but does not open a microphone/camera or download face models. On an OS that names the browser `chromium-browser`, adjust the apt package name; the kiosk launcher supports both executable names.

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
.venv/bin/governor doctor
.venv/bin/governor listen
```

This explicitly enables continuous local voice-activity monitoring. **There is no wake word:** every detected utterance is sent to the selected transcription backend. Cloud mode uploads each detected clip; local mode processes it locally. Input closes while replies are generated/played to avoid hearing the TV's own response. This is half-duplex; natural interruption/barge-in is not implemented. Pause in the console stops processing, and Ctrl-C ends the worker.

Set `GOVERNOR_INPUT_DEVICE` and `GOVERNOR_OUTPUT_DEVICE` from the doctor's audio device list if defaults are wrong. The worker expects a device supporting 16 kHz mono capture. Adjust `GOVERNOR_VAD_THRESHOLD` (default 0.025) upward for noise or downward for quiet speech. This simple energy detector can trigger on television/music; use two-click recording in noisy rooms. Do not run two workers or record in the browser simultaneously.

## Camera and profiles

```sh
.venv/bin/python scripts/download-face-models.py
```

The download script resolves one OpenCV Zoo revision, verifies models against the repository's Git LFS SHA-256 hashes, and records a manifest. Preserve that manifest to repeat the same model version. Model licenses are in the corresponding [OpenCV Zoo directories](https://github.com/opencv/opencv_zoo/tree/main/models).

In `.env`, set `GOVERNOR_CAMERA=true`, then restart Governor. Create a profile with the person's agreement. With only that person visible, click Enroll face and confirm. The camera is enabled by configuration; Pause stops conversation, not the camera. To stop camera capture, set the camera setting false and restart.

Recognition remains local. Raw frames are not saved or sent to the LLM. The database stores a numeric face template, which is still biometric data; protect the Pi and its backups. “Remove face” deletes the template; “Forget person” deletes profile, template, and facts.

Tune and test under actual room lighting. Unknown and ambiguous faces should remain unknown. A photo can fool this recognizer; it is not authentication or liveness detection. Recognition shows possible presence but **never automatically selects the speaker**. Choose the speaker in the console; this prevents assigning one person's words to somebody else merely because their face is visible.

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

The hands-free microphone worker is intentionally not auto-enabled. Add it to your own startup only after device calibration and deciding you want continuous listening.

Stop/disable the server: `systemctl --user disable --now governor`. Remove kiosk autostart by deleting `~/.config/autostart/governor.desktop`.

## Hardware acceptance checklist

- Face remains readable and inside the CRT's edges; expressions and speech animation work.
- TV speaks a demo reply without buzzing, clipping, or missing an audio channel.
- Five spoken sentences transcribe correctly at your intended distance.
- Silence/noise does not repeatedly create paid turns.
- Switching the speaker clears the previous conversation; facts survive restart.
- Two enrolled people, an unknown visitor, bad lighting, and two simultaneous faces behave sensibly.
- Pausing during a slow response prevents its late playback.
- Unplugging network/camera/mic produces a recoverable failure instead of a stuck conversation.
- A 30-minute session has acceptable response times, CPU temperature, and cloud cost.

These checks require the real Pi and peripherals; development-machine tests cannot establish them.
