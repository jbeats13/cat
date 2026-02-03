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

You need a YOLO model (e.g. `yolo11s.pt`) in the repo root; the script looks for it automatically.

## Requirements

- Python 3.9+
- Webcam or camera (e.g. USB or on Arducam pan-tilt kit)
- **Optional:** PCA9685 + servos (e.g. [Arducam pan-tilt platform](https://www.arducam.com/product/arducam-pan-tilt-platform-for-raspberry-pi-camera-2-dof-bracket-kit-with-digital-servos-and-ptz-control-broad-b0283/))

---

## Running on Raspberry Pi

### 1. System setup

- Use **Raspberry Pi OS** (64-bit recommended for better performance).
- Update the system:
  ```bash
  sudo apt update && sudo apt upgrade -y
  ```

### 2. Enable I2C (for PCA9685 servo board)

1. Run `sudo raspi-config`.
2. Go to **Interface Options** → **I2C** → **Yes** to enable.
3. Reboot: `sudo reboot`.
4. After reboot, check that I2C is visible:
   ```bash
   ls /dev/i2c*
   ```
   You should see `/dev/i2c-1` (or similar).

### 3. Camera

- **USB webcam:** Plug it in; it will usually show up as `/dev/video0`. Use `--camera 0` (default).
- **Raspberry Pi Camera (CSI):** If you use `libcamera`/V4L2, it may appear as a video device (e.g. `/dev/video0`). Use `--camera 0`. If you use a different stack, you may need to point the script at a different source (e.g. a GStreamer or picamera2 pipeline); the script expects a OpenCV `VideoCapture` index by default.

### 4. Python and dependencies

```bash
# Install Python 3 and pip if needed
sudo apt install -y python3 python3-pip python3-venv

# Clone or copy your repo onto the Pi (e.g. ~/cat), then:
cd ~/cat/cat_tracker

# Use a virtualenv (recommended)
python3 -m venv venv
source venv/bin/activate

# Install packages using the script (dependencies are baked into cat_tracker.py)
python3 cat_tracker.py --install-deps        # opencv + ultralytics
python3 cat_tracker.py --install-deps-all   # + Adafruit libs for servo (PCA9685)
```

**Note:** If you run **without a display** (e.g. over SSH), use the headless OpenCV build so it doesn’t try to open a GUI:

```bash
pip uninstall opencv-python -y
pip install opencv-python-headless
```

Then run with `--no-window` (see below).

### 5. Model file

Ensure the YOLO model is on the Pi. From the repo root (e.g. `~/cat`):

```bash
# If yolo11s.pt is not already there, download or copy it to ~/cat/
ls ~/cat/yolo11s.pt
```

The script looks for `yolo11s.pt` in the repo root when you run from `cat_tracker/`.

### 6. Run the tracker

**With display (Pi connected to monitor + keyboard):**

```bash
cd ~/cat/cat_tracker
source venv/bin/activate   # if using venv
python3 cat_tracker.py
```

**Without display (SSH or headless):**

```bash
cd ~/cat/cat_tracker
source venv/bin/activate
python3 cat_tracker.py --no-window
```

**Without servo (test detection only):**

```bash
python3 cat_tracker.py --no-servo --no-window
```

**Track only people:**

```bash
python3 cat_tracker.py --track person --no-window
```

Press **Ctrl+C** in the terminal to stop.

### 7. Performance on Pi

- YOLO on Raspberry Pi (CPU only) is relatively slow (often a few FPS). That’s normal.
- To speed up a bit: use a smaller model if you have one (e.g. nano variant), or lower the camera resolution in your pipeline.
- For faster inference, use a Pi with **NPU** (e.g. Raspberry Pi 5 with compatible software) if you have support for it; the current script does not require it.

### 8. Run at boot (start when the Pi turns on)

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

## Setup (general)

All required packages are listed inside `cat_tracker.py`. Install them with:

```bash
cd cat_tracker
python3 cat_tracker.py --install-deps
```

That installs **opencv-python** and **ultralytics**. For servo hardware (PCA9685) on a Pi, also run:

```bash
python3 cat_tracker.py --install-deps-all
```

That adds **adafruit-circuitpython-servokit**, **adafruit-circuitpython-pca9685**, and **adafruit-blinka**. You only need `--install-deps-all` if you use the pan/tilt servo board.

You can still use `pip install -r requirements.txt` if you prefer; the script’s `--install-deps` / `--install-deps-all` are equivalent. For **Raspberry Pi** (I2C + servo, camera, headless, startup), see **[Running on Raspberry Pi](#running-on-raspberry-pi)** above.

## Usage

**Install dependencies (run once):**

```bash
python3 cat_tracker.py --install-deps       # opencv-python + ultralytics
python3 cat_tracker.py --install-deps-all  # + Adafruit libs for PCA9685 servo
```

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

**Track cats only, or people only:**

```bash
python3 cat_tracker.py --track cat
python3 cat_tracker.py --track person
python3 cat_tracker.py --track cat,person   # both (default)
```

**Headless (no display):**  
Use `--no-window` when running over SSH or without a monitor. On Raspberry Pi, use `opencv-python-headless` instead of `opencv-python` so no GUI stack is required.

```bash
python3 cat_tracker.py --no-window
```

**All options:**

| Option | Description |
|--------|-------------|
| `--install-deps` | Install required packages (opencv-python, ultralytics). |
| `--install-deps-all` | Install required + optional (Adafruit servo) packages. |
| `--no-servo` | Disable servo; detection and bounding boxes only. |
| `--no-window` | Don’t open the OpenCV window (for headless/SSH). |
| `--camera 0` | Camera index (default 0). |
| `--model path/to/yolo11s.pt` | YOLO model path (default: repo root `yolo11s.pt`). |
| `--gain 0.4` | Tracking gain; higher = servos react faster. |
| `--track cat,person` | Classes to track (default: cat,person). |

Press **q** in the window to quit (or **Ctrl+C** in the terminal if using `--no-window`).

## Configuration

All config lives in `cat_tracker.py`. Edit the constants near the top if needed:

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
