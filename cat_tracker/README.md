# Cat & Person Tracker

Track cats and/or people with a camera and pan/tilt servo. Uses YOLO to detect cats and people, then drives the servos so the camera keeps the selected target centered in the frame.

**Features:**

- **Single file** — Everything runs from `cat_tracker.py`. Servo logic is inlined; no separate `servo_driver` import required.
- **Baked-in dependencies** — Required (and optional) packages are listed in the script. Install with `--install-deps` or `--install-deps-all`.
- **Cat and person tracking** — Track cats only, people only, or both (default). The largest detection in frame is the servo target.
- **Bounding boxes** — All detections are drawn: green box + “(tracking)” for the active target, orange boxes + confidence % for others.
- **Raspberry Pi ready** — I2C/PCA9685 support, headless (`--no-window`), and optional systemd “run at boot” instructions.

## Quick start

```bash
cd cat_tracker
python3 cat_tracker.py --install-deps       # Install opencv + ultralytics (run once)
python3 cat_tracker.py --install-deps-all  # Optional: add Adafruit libs for servo
python3 cat_tracker.py                     # Run (or --no-servo / --no-window as needed)
```

You need a YOLO model (default `yolo11n.pt` for Pi; or `yolo11s.pt`) in the repo root; the script looks for it or downloads it on first run.

## Requirements

- Python 3.9+
- Webcam or camera (e.g. USB or on Arducam pan-tilt kit)
- **Optional:** PCA9685 + servos (e.g. [Arducam pan-tilt platform](https://www.arducam.com/product/arducam-pan-tilt-platform-for-raspberry-pi-camera-2-dof-bracket-kit-with-digital-servos-and-ptz-control-broad-b0283/))

---

## From the beginning: full setup walkthrough

Follow these steps in order. Use **Raspberry Pi** if you have the servo board; use **Mac/laptop** if you only want to try detection (no servo).

### 1. Get the code

```bash
cd ~
git clone https://github.com/jbeats13/cat.git
cd cat/cat_tracker
```

### 2. Create a virtual environment (same on Pi and Mac)

```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

From here on, use this venv: either run `source venv/bin/activate` in each new terminal, or call the venv Python explicitly: `./venv/bin/python3 ...`.

### 3. Install dependencies

**Required** (camera + YOLO):

```bash
./venv/bin/python3 cat_tracker.py --install-deps
```

**If you have a Raspberry Pi and a PCA9685 servo board**, also install the optional servo packages (includes `lgpio` for Pi). Either:

```bash
./venv/bin/python3 cat_tracker.py --install-deps-all
```

or install directly with pip (use the same Python you run the script with):

```bash
./venv/bin/python3 -m pip install lgpio adafruit-circuitpython-servokit adafruit-circuitpython-pca9685 adafruit-blinka
```

On Mac/laptop you can skip the servo packages and run with `--no-servo` later.

**If you use a Raspberry Pi camera (e.g. imx708) with `--camera-backend picamera2`**, install picamera2 in the same venv:

```bash
pip install picamera2
```

Install system deps if needed: `sudo apt install -y libcap-dev` (for building), then `sudo apt install -y python3-libcamera`. Because `libcamera` is a system package, the venv must see it. **Find the correct path** (run once on your Pi):

```bash
dpkg -L python3-libcamera | grep 'dist-packages' | head -1
```

Use that directory in `PYTHONPATH`. Common results: `/usr/lib/python3/dist-packages` or `/usr/lib/python3.12/dist-packages`. Example:

```bash
PYTHONPATH="/usr/lib/python3/dist-packages:$PYTHONPATH" python3 cat_tracker.py --no-window --conf 0.25 --camera-backend picamera2
```

**Easier long-term:** recreate the venv with system site-packages so it sees `libcamera` without `PYTHONPATH` (see [Troubleshooting](#troubleshooting)).

### 4. (Raspberry Pi + servo only) Enable I2C and wire the board

- **Enable I2C:** `sudo raspi-config` → Interface Options → I2C → Enable → Finish, then **reboot**.
- **Wire PCA9685:** SDA → Pi GPIO 2 (pin 3), SCL → Pi GPIO 3 (pin 5), VCC → 3.3 V (pin 1), GND → GND (pin 6). Servos plug into the PCA9685, not the Pi.
- **Check the Pi sees the board:**  
  `sudo apt install -y i2c-tools` then `sudo i2cdetect -y 1` — you should see **40** in the grid.

### 5. (Optional) Test the servos before the full tracker (Pi + servo)

```bash
./venv/bin/python3 test_servo.py --once
```

If the servos sweep once and return to center, wiring and I2C are good. If you get "No I2C device at 0x40" or "No module named 'lgpio'", see [Troubleshooting](#troubleshooting) below.

### 6. YOLO model

The script looks for a YOLO model (default `yolo11n.pt`) in the **repo root** (`~/cat/yolo11s.pt` when you cloned into `~/cat`). If the repo doesn’t include it, the first run may download it automatically (Ultralytics can do this), or you can download a small model and put it there. You can also pass a path: `--model /path/to/model.pt`.

### 7. Run the tracker

**With a display (and optional servo):**

```bash
cd ~/cat/cat_tracker
source venv/bin/activate
python3 cat_tracker.py
```

You should see a line like: `Servo: PCA9685 | Camera: 0 | Track: cat,person`. If it says `Servo: mock (...)`, the real servo driver didn’t load — run `--install-deps-all` and fix any import errors (see Troubleshooting).

**Over SSH or no monitor (headless):**

```bash
pip uninstall opencv-python -y
pip install opencv-python-headless
python3 cat_tracker.py --no-window
```

**Without the servo** (e.g. on a laptop, or to test detection only):

```bash
python3 cat_tracker.py --no-servo
```

Press **Q** in the window to quit, or **Ctrl+C** in the terminal.

### 8. Quick checks if something’s wrong

| What you see | What to do |
|--------------|------------|
| `Servo: mock (import failed)` | Run `./venv/bin/python3 cat_tracker.py --install-deps-all`. On Pi, ensure `lgpio` is installed (it’s in the optional list now). |
| `No I2C device at address: 0x40` | Enable I2C in `raspi-config`, reboot, run `i2cdetect -y 1` and check wiring (SDA/SCL/VCC/GND). |
| Camera doesn’t open / black window | Try `--camera 0`, `--camera 2`, or `--camera /dev/video0`. **Raspberry Pi camera (e.g. imx708):** if OpenCV fails on all `/dev/video*`, use the Pi camera backend: `pip install picamera2` then run with `--camera-backend picamera2`. On Pi, enable camera in raspi-config. |
| No detections / “Target: none” | Point camera at a cat or person; ensure the model supports those classes (default model does). You can lower `--min-width` and `--min-height` if the target is small. |
| **Servo works (test_servo) but tracking doesn’t move the camera** | Run `python3 cat_tracker.py --list-classes` and confirm you see `person` and `cat`. Then run with `--debug` to see `detections=N target=... pan=... tilt=...` every 20 frames. If `detections=0` or `target=none` while you’re in frame, lower the confidence: `--conf 0.25` or `--conf 0.2`. |

More detail: [Troubleshooting](#troubleshooting) and [Get it from GitHub and run on Raspberry Pi](#get-it-from-github-and-run-on-raspberry-pi).

---

## Test the servos first (optional)

If you have a Raspberry Pi and a PCA9685 pan/tilt board, you can test the servos **before** setting up the full cat tracker. That confirms wiring and I2C.

**1. Enable I2C:** `sudo raspi-config` → Interface Options → I2C → Enable, then reboot.

**2. Wire the PCA9685** to the Pi (see [GPIO pins table](#gpio-pins-for-pca9685-servo-board) in the section below). Use GPIO 2 (SDA), GPIO 3 (SCL), 3.3 V, and GND.

**3. Clone the repo** (if you haven’t already):

```bash
cd ~
git clone https://github.com/jbeats13/cat.git
cd cat/cat_tracker
```

**4. Create a venv and install the servo libraries:**

```bash
python3 -m venv venv
source venv/bin/activate
# Install lgpio + Adafruit libs (lgpio needed on Raspberry Pi for Blinka):
./venv/bin/python3 -m pip install lgpio adafruit-circuitpython-servokit adafruit-circuitpython-pca9685 adafruit-blinka
# Check they’re there:
./venv/bin/python3 -c "import adafruit_servokit; print('OK')"
```

**5. Run the servo test:**

```bash
python3 test_servo.py              # Sweep until Ctrl+C
python3 test_servo.py --once      # Sweep once and exit
python3 test_servo.py --mock      # No hardware; print angles only (no Adafruit libs needed)
```

If you see **"adafruit_servokit not found"**, the Adafruit libraries aren’t in your venv yet. These are the same packages the Arducam pan-tilt examples use (see `PCA9685/example/Jetson/ServoKit.py`). Install using the same Python you run the script with:

```bash
./venv/bin/python3 -m pip install lgpio adafruit-circuitpython-servokit adafruit-circuitpython-pca9685 adafruit-blinka
```

Then run `./venv/bin/python3 test_servo.py --once` again. (With the venv activated you can use `python3` instead.) On Raspberry Pi 5, **lgpio** is required by Adafruit Blinka; if you see **"No module named 'lgpio'"**, install it with that command. To confirm the install: `python3 -c "import adafruit_servokit; print('OK')"`. Or use `--mock` to test without hardware.

To check if the Pi sees the board: `sudo apt install -y i2c-tools` then `sudo i2cdetect -y 1`; you should see **40** in the grid.

---

## Get it from GitHub and run on Raspberry Pi

End-to-end steps to clone the repo on a Pi and run the tracker.

**1. Clone the repo**

```bash
cd ~
git clone https://github.com/jbeats13/cat.git
cd cat/cat_tracker
```

**2. (Optional) Enable I2C if you use the servo board**

```bash
sudo raspi-config
# Interface Options → I2C → Enable, then reboot
sudo reboot
```

**GPIO pins for PCA9685 (servo board)**  
The PCA9685 connects over **I2C**. On the Raspberry Pi 40-pin header, use:

| Pi pin | GPIO | PCA9685 | Notes |
|--------|------|---------|--------|
| 1      | —    | VCC     | 3.3 V |
| 3      | GPIO 2 | SDA   | I2C data |
| 5      | GPIO 3 | SCL   | I2C clock |
| 6      | —    | GND     | Ground |
| 9      | —    | GND     | Ground (optional second GND) |

So you only use **GPIO 2 (SDA)** and **GPIO 3 (SCL)** for data; the rest is 3.3 V and GND. The servos plug into the PCA9685 board, not into the Pi. (If your board uses 5 V for logic, connect VCC to Pi pin 2 or 4 (5 V) instead of 3.3 V — check your PCA9685 module.)

To **test the servos** before running the full tracker, see [Test the servos first (optional)](#test-the-servos-first-optional) above.

**3. Install Python and create a virtualenv**

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
```

**4. Install dependencies from the script**

```bash
python3 cat_tracker.py --install-deps        # opencv + ultralytics
python3 cat_tracker.py --install-deps-all   # add this if you use the PCA9685 servo
```

**5. (Optional) Headless: use OpenCV without a display**

If you run over SSH or without a monitor:

```bash
pip uninstall opencv-python -y
pip install opencv-python-headless
```

**6. YOLO model**

The script uses `yolo11n.pt` by default (downloads if missing). The repo may also include `yolo11s.pt`; use `--model yolo11s.pt` for better accuracy. Or pass any path: `--model /path/to/model.pt`.

**7. Run the tracker**

With a monitor (and optional servo):

```bash
cd ~/cat/cat_tracker
source venv/bin/activate
python3 cat_tracker.py
```

Over SSH or headless (no window):

```bash
cd ~/cat/cat_tracker
source venv/bin/activate
python3 cat_tracker.py --no-window
```

Without the servo (camera + detection only):

```bash
python3 cat_tracker.py --no-servo --no-window
```

Press **Ctrl+C** to stop. To start at boot, see **[Run at boot](#run-at-boot-start-when-the-pi-turns-on)** below.

---

## Raspberry Pi (extra detail)

**Camera:** You can pass an index or a device path: `--camera 0`, `--camera 2`, or `--camera /dev/video0`. On Pi there are often many `/dev/video*` nodes; OpenCV’s index 0 might not be the real capture device. If you get “Camera read failed” or “Not a video capture device”, run `v4l2-ctl --list-devices` and try the index or path for the capture device. **Raspberry Pi camera (e.g. imx708)** that doesn’t work with OpenCV: install `picamera2` and run with `--camera-backend picamera2` (e.g. `python3 cat_tracker.py --no-window --camera-backend picamera2`).

**IMX708 (Camera Module 3 / Arducam 12MP):** The IMX708 is supported by libcamera and Picamera2. If the camera isn't detected at all, see [Arducam's IMX708 setup](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/12MP-IMX708/) (config.txt: `camera_auto_detect=0`, `dtoverlay=imx708`, then reboot). Once `rpicam-still --list-cameras` shows the camera, use this tracker with `--camera-backend picamera2` and ensure the venv can see the system `libcamera` package (PYTHONPATH or venv with `--system-site-packages`; see §3 and Troubleshooting).

**I2C check:** After enabling I2C and rebooting, run `ls /dev/i2c*`; you should see `/dev/i2c-1`.

**Check if the Pi sees the PCA9685 (servo board):** With the board wired and powered, run:

```bash
sudo apt install -y i2c-tools
sudo i2cdetect -y 1
```

If the PCA9685 is connected correctly, you’ll see **40** in the grid (its default I2C address). If the row for `40` is empty or you get errors, check wiring (SDA, SCL, VCC, GND) and that I2C is enabled in `raspi-config`.

### Performance on Pi

- YOLO on Raspberry Pi (CPU only) is relatively slow (often a few FPS). That’s normal.
- To speed up: use a smaller model or lower camera resolution; or a Pi with NPU (e.g. Pi 5) if supported.

### Run at boot (start when the Pi turns on)

You can make the cat tracker start automatically when the Raspberry Pi boots. That way you don’t need to SSH in and run it by hand. This uses **systemd**, the service manager built into Raspberry Pi OS.

**What you need first**

- The tracker runs correctly when you start it yourself (e.g. `python3 cat_tracker.py --no-window`).
- Your repo path and username. The steps below use:
  - **User:** `pi` (change to your username if different, e.g. `raspberry` on newer Pi OS).
  - **Repo path:** `/home/pi/cat` (so the app is in `/home/pi/cat/cat_tracker` and the venv in `/home/pi/cat/cat_tracker/venv`).

**Step 1: Create the service file**

Open a new systemd service file:

```bash
sudo nano /etc/systemd/system/cat-tracker.service
```

Paste the following. **Change `pi` and `/home/pi/cat` if your username or path are different:**

```ini
[Unit]
Description=Cat/Person Tracker
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/cat/cat_tracker
ExecStart=/home/pi/cat/cat_tracker/venv/bin/python3 cat_tracker.py --no-window
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- **User=pi** — Run as user `pi` (so it sees your home directory and venv). Use your actual username if it’s not `pi`.
- **WorkingDirectory** — Must be the `cat_tracker` folder (where `cat_tracker.py` lives).
- **ExecStart** — Full path to the Python in your venv, then the script and `--no-window` (no display needed at boot).
- **Restart=on-failure** — If the script crashes, systemd will try to start it again after 5 seconds (**RestartSec=5**).

Save and exit: **Ctrl+O**, Enter, then **Ctrl+X**.

**Step 2: Reload systemd and enable the service**

```bash
sudo systemctl daemon-reload
sudo systemctl enable cat-tracker.service
```

- **daemon-reload** — Makes systemd read the new service file.
- **enable** — Turns on “start this service at boot.” The tracker will now start automatically every time the Pi boots.

**Step 3: Start it once (optional)**

You don’t have to reboot to test. Start the service now:

```bash
sudo systemctl start cat-tracker.service
```

Check that it’s running:

```bash
sudo systemctl status cat-tracker.service
```

You should see something like `Active: active (running)`. If you see `failed` or errors, check the logs (Step 4).

**Step 4: View logs**

To see what the tracker is doing (or why it failed):

```bash
journalctl -u cat-tracker.service -f
```

- **-f** — Follow the log (like `tail -f`). Press **Ctrl+C** to stop.

**Useful commands**

| What you want to do | Command |
|---------------------|--------|
| Stop the tracker    | `sudo systemctl stop cat-tracker.service` |
| Start it again      | `sudo systemctl start cat-tracker.service` |
| Disable at boot     | `sudo systemctl disable cat-tracker.service` |
| Re-enable at boot   | `sudo systemctl enable cat-tracker.service` |
| Restart after you change code | `sudo systemctl restart cat-tracker.service` |

After you **disable** the service, it will no longer start when the Pi turns on until you run **enable** again.

---

## Usage

**Install dependencies (run once):**  
`python3 cat_tracker.py --install-deps` (opencv + ultralytics). For servo: `python3 cat_tracker.py --install-deps-all`. Or use `pip install -r requirements.txt`.

**With servo (default):**  
Camera + YOLO + pan/tilt servos to follow the largest cat or person.

```bash
python3 cat_tracker.py
```

**Without servo (camera + detection only):**  
Use on a machine without PCA9685 or to test.

```bash
python3 cat_tracker.py --no-servo
```

**Track:** `--track cat`, `--track person`, or `--track cat,person` (default). **Headless:** `--no-window` (see [Troubleshooting](#troubleshooting) for Qt/wayland and headless OpenCV).

**All options:**

| Option | Description |
|--------|-------------|
| `--install-deps` | Install required packages (opencv-python, ultralytics). |
| `--install-deps-all` | Install required + optional (Adafruit servo) packages. |
| `--no-servo` | Disable servo; detection and bounding boxes only. (Use full flag, not `--no`.) |
| `--no-window` | Don't open the OpenCV window (for headless/SSH). (Use full flag, not `--no`.) |
| `--min-width`, `--min-height` | Min box size (px) to track; default 50×50. |
| `--camera 0` or `--camera /dev/video0` | Camera index or device path (default 0). |
| `--camera-backend auto \| opencv \| picamera2` | Use `picamera2` for Raspberry Pi camera (e.g. imx708) when OpenCV cannot open the device (default: auto). |
| `--model path/to/yolo11n.pt` | YOLO model path (default: `yolo11n.pt` for Pi; use `yolo11s.pt` for better accuracy). |
| `--gain 0.4` | Tracking gain; higher = servos react faster. |
| `--track cat,person` | Classes to track (default: cat,person). |

Press **q** in the window to quit (or **Ctrl+C** in the terminal if using `--no-window`).

## Troubleshooting

**"externally-managed-environment"** or **"No module named 'cv2'"**  
Use a virtual environment and install dependencies there. From `~/cat/cat_tracker`: `python3 -m venv venv`, `source venv/bin/activate`, then `python3 cat_tracker.py --install-deps`. Always activate the venv before running the script. If using an IDE, set it to use the venv Python (e.g. `venv/bin/python3`).

**"bash: .../venv/bin/python3: No such file or directory"**  
Your shell is still using an old (broken or incomplete) virtualenv. Deactivate it, remove the venv folder, then create a new one:

```bash
deactivate
rm -rf venv
sudo apt install -y python3-venv   # if on Debian/Ubuntu/Pi and venv fails
python3 -m venv venv
source venv/bin/activate
```

**"Ambiguous option: --no could match --no-servo, --no-window"**  
Use the **full** flag: `--no-window` or `--no-servo`, not `--no`.

**"No module named 'libcamera'" when using `--camera-backend picamera2`**  
The venv can’t see the system `libcamera` package. Either find the right path and set `PYTHONPATH` (see Pi camera step in §3), or **recreate the venv with system site-packages** so it sees system packages:

```bash
cd ~/cat/cat_tracker
deactivate
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install opencv-python ultralytics picamera2
python3 cat_tracker.py --no-window --conf 0.25 --camera-backend picamera2
```

Use the same `python3` that will run the script (e.g. system Python 3.11/3.12). Then the venv sees both pip packages and system `libcamera`.

**"No module named 'lgpio'"**  
On Raspberry Pi (especially Pi 5), Adafruit Blinka needs **lgpio**. With the venv active, run: `./venv/bin/python3 -m pip install lgpio`, then try the import or `test_servo.py` again.

**"Building wheel for lgpio" failed**  
The Python **lgpio** package needs the system **lgpio** library and build tools. On Raspberry Pi, install them, then install the Python package in the venv:

```bash
sudo apt install -y swig build-essential liblgpio-dev
./venv/bin/python3 -m pip install lgpio
```

If your system doesn’t have **liblgpio-dev**, try `sudo apt install -y lgpio` (or search: `apt search lgpio`), then retry the pip install.

**"adafruit_servokit not found" when running `test_servo.py`**  
Install into the **same** Python that runs the script: run `python3 test_servo.py --install` (installs into that Python, then run `test_servo.py` again). Or run `python3 -m pip install lgpio adafruit-circuitpython-servokit adafruit-circuitpython-pca9685 adafruit-blinka` with the venv active. If it still fails: run `which python3` and `python3 -m pip list | grep -i adafruit` to confirm you’re in the venv and packages are there; or run `./venv/bin/python3 test_servo.py --install` then `./venv/bin/python3 test_servo.py --once` so the same interpreter is used. Or use `--mock` to test without hardware.

**"No I2C device at address: 0x40" / "Remote I/O error" when running `test_servo.py`**  
The Pi can’t talk to the PCA9685. Check:

1. **Device on bus:** Run `sudo i2cdetect -y 1` again. You should see **40** in the grid. If not, the board isn’t seen (check wiring and power).
2. **I2C permission:** Your user must be in the **i2c** group so Python can use I2C without sudo:
   ```bash
   sudo usermod -aG i2c $USER
   ```
   Then **log out and log back in** (or reboot). After that, run `test_servo.py` again (no sudo).
3. **Wiring and power:** SDA→GPIO 2 (pin 3), SCL→GPIO 3 (pin 5), VCC→3.3 V, GND→GND. Ensure the PCA9685 is powered and cables are secure.

**Servo not tracking**  
If the servo doesn’t follow you (or the cat), check: (1) You’re not using `--no-servo`. (2) Minimum box size: the default is 50×50 px. If you previously raised `--min-width` / `--min-height` (e.g. to 1000×700), only very large, close-up detections are tracked; lower them or omit them to track normal-sized people. (3) I2C is enabled and the PCA9685 is wired correctly.

**"Could not find the Qt platform plugin wayland"**  
This happens when OpenCV (with Qt) tries to open a window but your environment doesn’t have the Wayland Qt plugin (common on Raspberry Pi or over SSH).

- **Option 1 — Run without a window (recommended):**  
  ```bash
  python3 cat_tracker.py --no-window
  ```  
  The script sets `QT_QPA_PLATFORM=offscreen` when you use `--no-window`, so Qt doesn’t try to load wayland and the error goes away. Tracking still runs; you just don’t see the video window.

- **Option 2 — Show a window on Pi:** The script sets `QT_QPA_PLATFORM=xcb` and `QT_QPA_FONTDIR` to system fonts so Qt doesn't look for the missing `cv2/qt/fonts` folder. Run `python3 cat_tracker.py`. If you still see "QFontDatabase: Cannot find font directory", install system fonts and retry: `sudo apt install -y fonts-dejavu-core`, then `QT_QPA_FONTDIR=/usr/share/fonts python3 cat_tracker.py`. If the window still doesn't appear, use Option 1.

- **Option 3 — Use headless OpenCV (no Qt at all):**  
  ```bash
  pip uninstall opencv-python -y
  pip install opencv-python-headless
  ```  
  Then run with `--no-window` (you can’t show a window with the headless build). This avoids Qt entirely.

## Configuration

All config lives in `cat_tracker.py`. Edit the constants near the top if needed:

- **GPIO / wiring:** The PCA9685 uses **I2C**: Pi **GPIO 2 (SDA)** and **GPIO 3 (SCL)** plus 3.3 V and GND. See the [GPIO pins table](#gpio-pins-for-pca9685-servo-board) in the Raspberry Pi section.
- **Servo ports:** `PAN_SERVO_PORT`, `TILT_SERVO_PORT` — Indices (0 = pan, 1 = tilt for typical Arducam).
- **Angle limits:** `PAN_RANGE`, `TILT_RANGE` — Min/max angles for your mount.
- **Tracking:** `GAIN` (how fast servos follow), `DEADZONE` (ignore small center errors).
- **Dependencies:** `REQUIRED_PACKAGES` and `OPTIONAL_PACKAGES` — Used by `--install-deps` / `--install-deps-all`.

## How it works

1. YOLO runs on each frame and detects the chosen classes (**cat**, **person**, or both).
2. The **largest** detection among those classes is chosen as the servo target.
3. **Bounding boxes** are drawn for every detection: green + “(tracking)” for the active target, orange + confidence % for the rest. A crosshair marks the target center.
4. The error between the target’s center and the frame center is converted to pan/tilt angle changes.
5. Servos are updated so the camera keeps the target centered (or the script runs without servo if `--no-servo` or no PCA9685).

The app is a single script; the model file path is resolved relative to the repo root when you run from `cat_tracker/`.
