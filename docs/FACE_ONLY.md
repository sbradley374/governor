# Silent Governor face — first Pi milestone

This mode needs only the existing Pi 5, Raspberry Pi OS **Desktop**, HDMI converter, and CRT. No microphone, camera, speaker, Python environment, API key, AI model, or running backend is needed. Chromium opens four local files and animates the face without network requests.

It blinks, slowly shifts its gaze, changes expressions, winks, and occasionally rests. Idle captions appear briefly. It respects reduced-motion preferences. Keyboard controls: Space rests/wakes, C changes color, R picks a new expression, F requests full screen, H toggles help. Alt+F4 closes the kiosk. The face preserves 4:3 framing and leaves a seven-percent inset for CRT overscan.

## Get access to the Pi first

If the Pi is offline and you have neither a keyboard nor a microSD reader, you need a physical setup tool first. The simplest way to preserve the working installation is a **wired USB keyboard**. A mouse is optional for the terminal setup. Plug it into the Pi. From the desktop, open a terminal (usually Ctrl+Alt+T), then run:

```sh
sudo raspi-config
```

Configure Wireless LAN under System Options, enable SSH under Interface Options, and enable Desktop Autologin under the boot/login options. Menu wording can vary with Raspberry Pi OS. Type your Wi-Fi password on the Pi. Connecting the Pi to your router with Ethernet is an alternative to configuring Wi-Fi.

After connecting, find the address and account name:

```sh
hostname -I
whoami
```

On the Mac, connect using those values:

```sh
ssh YOUR_PI_USERNAME@YOUR_PI_IP
```

Use your existing Pi account password when prompted; do not send it in chat. SSH is disabled by default. [Official SSH instructions](https://www.raspberrypi.com/documentation/computers/remote-access.html#ssh)

An alternative, **if networking is already configured**, is a microSD reader: shut down the Pi, put its card in the Mac, and create an empty file named `ssh` on its boot partition (often mounted as `/Volumes/bootfs`). Eject the card and boot the Pi. That enables SSH; it does not configure Wi-Fi or create an account. Avoid reflashing a working card just to enable SSH.

## Transfer the small bundle from the Mac

Build locally with `python3 scripts/package-face.py`, or use the already prepared `dist/governor-face.tar.gz`.

```sh
scp /Users/sambradley/governor/dist/governor-face.tar.gz YOUR_PI_USERNAME@YOUR_PI_IP:~/
ssh YOUR_PI_USERNAME@YOUR_PI_IP
```

On the Pi:

```sh
tar -xzf ~/governor-face.tar.gz -C ~
cd ~/governor-face
bash scripts/install-face.sh
bash ~/.local/share/governor-face/launch.sh
```

The installer uses the installed Chromium, or installs it through apt if missing. This may require internet once. It copies the face into `~/.local/share/governor-face` and configures desktop autostart. No audio or vision packages are installed. Run as your normal Pi user, without putting `sudo` before the installer.

The launcher can find an existing desktop session when invoked over SSH. If no desktop is logged in, enable **Desktop Autologin** in `sudo raspi-config` and reboot. SSH access alone does not create a graphical desktop. Raspberry Pi OS Lite needs a desktop installation before this browser-based display can run.

If a Governor desktop launcher already exists, the installer backs it up before switching it to the silent face. The full robot source and data remain available for the later interactive setup. Stop the silent face before launching the full kiosk. Remove `~/.config/autostart/governor.desktop` to stop automatic startup.

## Try it on the Mac now

Open `governor/static/ambient.html` in a browser. It works directly as a local file. No server or API is required.

## Later hardware

First test whether your existing HDMI-to-composite converter carries audio to the CRT's white RCA input. The TV may already provide the speaker. Add a Linux-compatible USB microphone and USB UVC webcam when ready, then use the full installation guide for voice and face recognition. There is no need to buy these to display the silent face.

The lower brightness, blinking, and gaze motion do not eliminate CRT burn-in. Switch the TV off when unattended.

## Verification

The standalone behavior and existing renderer have automated checks; shell and JavaScript syntax are checked. Actual Pi startup, converter framing, and Chromium rendering on the CRT still require hardware access.
