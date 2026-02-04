#!/usr/bin/env python3
"""
Cat & Person Tracker — Track cats and/or people with a camera and pan/tilt servo.

Uses YOLO to detect cats and/or people, then drives pan/tilt servos (e.g. PCA9685/Arducam)
to keep the selected target centered in the frame.

Usage:
  python cat_tracker.py --install-deps           # Install required packages (run once)
  python cat_tracker.py                           # Track cats and people (with servo)
  python cat_tracker.py --track cat               # Track cats only
  python cat_tracker.py --track person            # Track people only
  python cat_tracker.py --no-servo                # Camera + detection only
  python cat_tracker.py --camera 0                # Use camera index 0
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# --- Dependencies (baked in); install with: python cat_tracker.py --install-deps ---
REQUIRED_PACKAGES = [
    "opencv-python>=4.8.0",
    "ultralytics>=8.0.0",
]
OPTIONAL_PACKAGES = [
    "lgpio",  # Required by adafruit_blinka on Raspberry Pi (install first)
    "adafruit-circuitpython-servokit",
    "adafruit-circuitpython-pca9685",
    "adafruit-blinka",
    "picamera2",  # Raspberry Pi camera (e.g. imx708); use --camera-backend picamera2
]


def install_deps(include_optional: bool = False) -> None:
    """Install REQUIRED_PACKAGES and optionally OPTIONAL_PACKAGES via pip."""
    packages = list(REQUIRED_PACKAGES)
    if include_optional:
        packages.extend(OPTIONAL_PACKAGES)
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + packages
    print("Running: %s" % " ".join(cmd))
    subprocess.check_call(cmd)
    print("Done. You can run the tracker now.")


# Add parent for repo root when resolving model path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# --- Servo driver (inlined so this file is self-contained) ---
class _MockServo:
    def __init__(self, num_ports: int = 4) -> None:
        self._angles = [90] * num_ports

    def set_angle(self, port: int, angle: int | float) -> None:
        self._angles[port] = max(0, min(180, int(angle)))

    def get_angle(self, port: int) -> int | float:
        return self._angles[port]


def _create_servo_driver(use_servo: bool = True, num_ports: int = 4):
    if not use_servo:
        return _MockServo(num_ports=num_ports), "mock (--no-servo)"
    try:
        import adafruit_servokit
    except ImportError as e:
        print("Warning: Servo hardware disabled — could not import adafruit_servokit: %s" % e)
        print("  Install with: python3 cat_tracker.py --install-deps-all")
        print("  Or: pip install lgpio adafruit-circuitpython-servokit adafruit-circuitpython-pca9685 adafruit-blinka")
        return _MockServo(num_ports=num_ports), "mock (import failed)"

    class _PCA9685Servo:
        def __init__(self) -> None:
            self._kit = adafruit_servokit.ServoKit(channels=16)
            for i in range(num_ports):
                self._kit.servo[i].angle = 90

        def set_angle(self, port: int, angle: int | float) -> None:
            a = max(0, min(180, int(angle)))
            self._kit.servo[port].angle = a

        def get_angle(self, port: int) -> int | float:
            return self._kit.servo[port].angle or 90

    return _PCA9685Servo(), "PCA9685"


class _Picamera2Capture:
    """Thin wrapper so Picamera2 can be used like cv2.VideoCapture in the main loop."""

    def __init__(self, size=(640, 480)):
        from picamera2 import Picamera2
        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(main={"size": size})
        self._picam2.configure(config)
        self._picam2.start()

    def isOpened(self):
        return True

    def read(self):
        import cv2
        arr = self._picam2.capture_array()
        if arr.ndim == 3:
            if arr.shape[2] == 4:
                # XBGR8888 from libcamera: drop leading channel -> BGR for YOLO
                arr = arr[:, :, 1:4].copy()
            elif arr.shape[2] == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return (True, arr)

    def release(self):
        self._picam2.stop()


# --- Config (override with CLI) ---
MODEL_FILE = "yolo11s.pt"  # Path relative to repo root or cwd
CONF = 0.35
IOU = 0.3
TRACKER = "bytetrack.yaml"
PAN_SERVO_PORT = 0   # Arducam pan-tilt: 0=pan, 1=tilt
TILT_SERVO_PORT = 1
PAN_CENTER = 90
TILT_CENTER = 90
PAN_RANGE = (30, 150)   # Min/max pan angle
TILT_RANGE = (50, 130)  # Min/max tilt angle
GAIN = 0.55             # How aggressively to move (0.2 = slow, 0.8 = fast)
DEADZONE = 0.05         # Ignore small errors (fraction of frame)
SCAN_STEP = 2.0         # Pan degrees per frame when no target (left-right scan)
SCAN_START_FRAMES = 10  # Frames with no target before starting scan (avoids flicker)
MIN_TRACK_WIDTH = 0   # Min box width (px) to track; 0 = any size
MIN_TRACK_HEIGHT = 0  # Min box height (px) to track; 0 = any size
WINDOW_NAME = "Cat & Person Tracker"


def get_class_ids(model, class_names: list[str]) -> list[int]:
    """Resolve class names to model class IDs. Unknown names are skipped."""
    names = model.names
    ids = []
    for want in class_names:
        want = want.strip().lower()
        for idx, name in names.items():
            if name and name.lower() == want:
                ids.append(idx)
                break
    return ids


def main():
    parser = argparse.ArgumentParser(description="Track cats and/or people with camera and servo", allow_abbrev=False)
    parser.add_argument("--install-deps", action="store_true", help="Install required Python packages (run once)")
    parser.add_argument("--install-deps-all", action="store_true", help="Install required + optional (servo) packages")
    parser.add_argument("--no-servo", action="store_true", help="Run without servo (camera + detection only)")
    parser.add_argument("--camera", type=str, default="0", help="Camera index (0, 1, ...) or device path (e.g. /dev/video0); ignored if --camera-backend picamera2")
    parser.add_argument(
        "--camera-backend",
        type=str,
        choices=("auto", "opencv", "picamera2"),
        default="auto",
        help="Camera backend: auto (try OpenCV then Picamera2), opencv, or picamera2 for Raspberry Pi camera (e.g. imx708)",
    )
    parser.add_argument("--model", type=str, default=MODEL_FILE, help="YOLO model path")
    parser.add_argument("--gain", type=float, default=GAIN, help="Tracking gain (default %s)" % GAIN)
    parser.add_argument(
        "--track",
        type=str,
        default="cat,person",
        help="Comma-separated classes to track: cat, person (default: cat,person)",
    )
    parser.add_argument("--no-window", action="store_true", help="Do not show OpenCV window (use full flag, not --no)")
    parser.add_argument("--min-width", type=int, default=MIN_TRACK_WIDTH, help="Min box width (px) to track; 0 = any size (default %s)" % MIN_TRACK_WIDTH)
    parser.add_argument("--min-height", type=int, default=MIN_TRACK_HEIGHT, help="Min box height (px) to track; 0 = any size (default %s)" % MIN_TRACK_HEIGHT)
    parser.add_argument("--list-classes", action="store_true", help="Load model, print its class names, and exit (to check if person/cat exist)")
    parser.add_argument("--conf", type=float, default=CONF, help="Detection confidence threshold 0–1 (default %.2f); try 0.2–0.25 on Pi if no detections" % CONF)
    parser.add_argument("--debug", action="store_true", help="Print detection count and servo angles every 20 frames (for troubleshooting)")
    parser.add_argument("--invert-pan", action="store_true", help="Reverse pan direction (if camera moves wrong way)")
    parser.add_argument("--invert-tilt", action="store_true", help="Reverse tilt direction (if camera moves wrong way)")
    args = parser.parse_args()

    if args.install_deps:
        install_deps(include_optional=False)
        return
    if args.install_deps_all:
        install_deps(include_optional=True)
        return

    # Qt/OpenCV display: avoid Wayland plugin and font errors on Pi
    if args.no_window:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    else:
        # Use X11 backend so we don't need the Qt "wayland" plugin (often missing in venv)
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        # Qt looks for cv2/qt/fonts and fails if missing; create it and copy a system font
        try:
            import importlib.util
            _spec = importlib.util.find_spec("cv2")
            if _spec is not None and _spec.origin:
                _cv2_dir = Path(_spec.origin).resolve().parent
                _qt_fonts = _cv2_dir / "qt" / "fonts"
                if not _qt_fonts.is_dir() or not any(_qt_fonts.iterdir()):
                    _qt_fonts.mkdir(parents=True, exist_ok=True)
                    _copied = False
                    for _guess in (
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/usr/share/fonts/TTF/DejaVuSans.ttf",
                        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                    ):
                        if Path(_guess).is_file():
                            import shutil
                            shutil.copy2(_guess, _qt_fonts / Path(_guess).name)
                            _copied = True
                            break
                    if not _copied:
                        for _parent in ("/usr/share/fonts/truetype", "/usr/share/fonts"):
                            if Path(_parent).is_dir():
                                _first = next(Path(_parent).rglob("*.ttf"), None)
                                if _first is not None:
                                    import shutil
                                    shutil.copy2(str(_first), _qt_fonts / _first.name)
                                    break
                                break
        except Exception:
            pass  # continue; Qt may still warn about fonts

    import cv2
    from ultralytics import YOLO

    model_path = Path(args.model)
    if not model_path.is_absolute():
        for base in (Path.cwd(), _REPO_ROOT):
            p = base / model_path
            if p.exists():
                model_path = p
                break
    model_path_str = str(model_path)
    if not Path(model_path_str).exists():
        print("Note: model file not found at %s; YOLO may download it." % model_path_str, flush=True)
    model = YOLO(model_path_str, task="detect")
    track_classes = [s.strip() for s in args.track.split(",") if s.strip()]
    class_ids = get_class_ids(model, track_classes)

    if args.list_classes:
        print("Model: %s" % model_path_str, flush=True)
        print("Classes in this model:", flush=True)
        for idx in sorted(model.names.keys()):
            print("  %d: %s" % (idx, model.names[idx]), flush=True)
        print("", flush=True)
        print("Requested --track: %s" % ", ".join(track_classes), flush=True)
        if class_ids:
            resolved = [(i, model.names[i]) for i in class_ids]
            print("Resolved to class IDs: %s" % ", ".join("%s (id %d)" % (name, i) for i, name in resolved), flush=True)
        else:
            print("WARNING: None of those names match this model. Check spelling and model (COCO has 'person' and 'cat').", flush=True)
        return

    if not class_ids:
        raise SystemExit("No valid track classes. Use --track cat,person (or cat or person). Run with --list-classes to see this model's classes.")

    # Open camera: OpenCV and/or Picamera2 (Pi camera e.g. imx708)
    cap = None
    camera_label = args.camera
    if args.camera_backend == "picamera2":
        try:
            cap = _Picamera2Capture(size=(640, 480))
            camera_label = "picamera2 (Pi camera)"
        except Exception as e:
            raise SystemError("Failed to open Picamera2: %s. Install: pip install picamera2 (on Raspberry Pi OS)." % e)
    else:
        camera_arg = int(args.camera) if args.camera.isdigit() else args.camera
        cap = cv2.VideoCapture(camera_arg)
        if not cap.isOpened():
            if args.camera_backend == "opencv":
                raise SystemError("Failed to open camera %s. Try --camera 0 or /dev/video0 (see README)." % args.camera)
            # auto: try Picamera2 as fallback (e.g. Pi camera not exposed as /dev/video*)
            try:
                cap = _Picamera2Capture(size=(640, 480))
                camera_label = "picamera2 (OpenCV failed, using Pi camera)"
            except Exception as e:
                raise SystemError(
                    "Failed to open camera %s with OpenCV and Picamera2: %s. "
                    "On Raspberry Pi with Pi camera try: --camera-backend picamera2" % (args.camera, e)
                )
    assert cap is not None

    servo, servo_label = _create_servo_driver(use_servo=not args.no_servo, num_ports=4)
    print("Model: %s" % model_path_str, flush=True)
    print("Tracking class IDs: %s" % ", ".join("%s (id %d)" % (model.names[i], i) for i in class_ids), flush=True)
    print("Servo: %s | Camera: %s | Track: %s" % (servo_label, camera_label, ",".join(track_classes)), flush=True)
    if args.no_window:
        print("Headless: FPS and target print every 10 frames. Ctrl+C to stop.", flush=True)
    if servo:
        servo.set_angle(PAN_SERVO_PORT, PAN_CENTER)
        servo.set_angle(TILT_SERVO_PORT, TILT_CENTER)

    pan_angle = float(PAN_CENTER)
    tilt_angle = float(TILT_CENTER)
    scan_direction = 1  # 1 = pan right, -1 = pan left (when no target)
    frames_no_target = 0  # Consecutive frames with no person/cat
    fps_counter, fps_timer, fps_display = 0, time.time(), 0
    last_status_print = 0.0  # Time of last status line (so we print every 2s when headless)
    track_args = {"persist": True, "verbose": False}

    show_window = not args.no_window
    if show_window:
        try:
            cv2.namedWindow(WINDOW_NAME)
        except cv2.error as e:
            show_window = False
            print("Could not open display window: %s" % e, flush=True)
            print("Continuing without window (tracking and servo still work). Ctrl+C to stop.", flush=True)
            print("FPS and target will print every 10 frames.", flush=True)

    try:
        if not show_window:
            print("Headless: status every 2s below. Ctrl+C to stop.", flush=True)
        if not args.no_window and not show_window:
            print("(Window could not be opened; continuing without display.)", flush=True)
        frame_count = 0
        while cap.isOpened():
            if frame_count == 0 and not show_window:
                print("Reading first frame from camera...", flush=True)
            ok, frame = cap.read()
            if not ok:
                if not show_window:
                    print("Camera read failed (no frame). Check camera and --camera index.", flush=True)
                break
            frame_count += 1
            if frame_count == 1 and not show_window:
                print("First frame OK. Running YOLO (first run can take 30-60s on Pi)...", flush=True)
            if frame_count == 2 and not show_window:
                print("Second frame done. Status will print every 2s.", flush=True)

            h, w = frame.shape[:2]
            center_x, center_y = w / 2.0, h / 2.0

            results = model.track(
                frame,
                conf=args.conf,
                iou=IOU,
                max_det=10,
                tracker=TRACKER,
                classes=class_ids,
                **track_args,
            )
            boxes = results[0].boxes
            best_cx, best_cy = None, None
            best_area = 0
            best_label = None
            names = model.names

            detections_for_draw = []
            if boxes is not None and boxes.data is not None:
                data = boxes.data.cpu().tolist() if hasattr(boxes.data, "cpu") else list(boxes.data)
                for row in data:
                    if len(row) < 4:
                        continue
                    x1, y1, x2, y2 = map(int, row[:4])
                    w_px = x2 - x1
                    h_px = y2 - y1
                    area = w_px * h_px
                    # 6 cols: xyxy, conf, cls → 7 cols: xyxy, track_id, conf, cls (Ultralytics Boxes)
                    if len(row) >= 7:
                        cls_id, conf = int(row[6]), float(row[5])
                    elif len(row) >= 6:
                        cls_id, conf = int(row[5]), float(row[4])
                    else:
                        cls_id, conf = 0, 0.0
                    label = names.get(cls_id, "?")
                    # Only consider for tracking if class is one we want, and box is big enough
                    if (
                        cls_id in class_ids
                        and w_px >= args.min_width
                        and h_px >= args.min_height
                        and area > best_area
                    ):
                        best_area = area
                        best_cx = (x1 + x2) / 2.0
                        best_cy = (y1 + y2) / 2.0
                        best_label = label
                    detections_for_draw.append((x1, y1, x2, y2, label, conf, area))

            if frame_count == 1 and not show_window:
                print("First inference done. Target: %s" % (best_label if best_label else "none"), flush=True)

            # Draw bounding boxes (tracked target = green, others = orange); show dimensions
            for (x1, y1, x2, y2, label, conf, area) in detections_for_draw:
                w_px = x2 - x1
                h_px = y2 - y1
                dims = "%dx%d" % (w_px, h_px)
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                is_tracked = (
                    best_cx is not None
                    and abs(cx - best_cx) < 2
                    and abs(cy - best_cy) < 2
                )
                if is_tracked:
                    color = (0, 255, 0)
                    thickness = 3
                    box_label = "%s (tracking) %s" % (label, dims)
                else:
                    color = (0, 165, 255)
                    thickness = 2
                    box_label = "%s %.0f%% %s" % (label, conf * 100, dims)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                (tw, th), _ = cv2.getTextSize(box_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                cv2.putText(frame, box_label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                # Dimensions below the box (width x height in pixels)
                cv2.putText(frame, dims, (x1, y2 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            if servo:
                if best_cx is not None:
                    frames_no_target = 0
                    # Track target: center the largest person/cat
                    err_x = (best_cx - center_x) / max(center_x, 1)
                    err_y = (best_cy - center_y) / max(center_y, 1)
                    if args.invert_pan:
                        err_x = -err_x
                    if args.invert_tilt:
                        err_y = -err_y
                    if abs(err_x) < DEADZONE:
                        err_x = 0
                    if abs(err_y) < DEADZONE:
                        err_y = 0
                    pan_angle = pan_angle + args.gain * err_x * (PAN_RANGE[1] - PAN_RANGE[0]) * 0.5
                    tilt_angle = tilt_angle + args.gain * err_y * (TILT_RANGE[1] - TILT_RANGE[0]) * 0.5
                    pan_angle = max(PAN_RANGE[0], min(PAN_RANGE[1], pan_angle))
                    tilt_angle = max(TILT_RANGE[0], min(TILT_RANGE[1], tilt_angle))
                    servo.set_angle(PAN_SERVO_PORT, int(round(pan_angle)))
                    servo.set_angle(TILT_SERVO_PORT, int(round(tilt_angle)))
                else:
                    frames_no_target += 1
                    # Start scanning only after no target for several frames (avoids flicker)
                    if frames_no_target >= SCAN_START_FRAMES:
                        # No target: scan pan left and right
                        pan_angle = pan_angle + scan_direction * SCAN_STEP
                        if pan_angle >= PAN_RANGE[1]:
                            pan_angle = float(PAN_RANGE[1])
                            scan_direction = -1
                        elif pan_angle <= PAN_RANGE[0]:
                            pan_angle = float(PAN_RANGE[0])
                            scan_direction = 1
                        servo.set_angle(PAN_SERVO_PORT, int(round(pan_angle)))
                        servo.set_angle(TILT_SERVO_PORT, int(round(tilt_angle)))
                        if not show_window and fps_counter % 15 == 0:
                            print("Scan: pan=%d (get out of frame to see scan)" % int(round(pan_angle)), flush=True)

            num_detections = len(detections_for_draw)
            if args.debug and fps_counter % 20 == 0:
                msg = "detections=%d target=%s" % (num_detections, best_label if best_label else "none")
                if servo:
                    msg += " pan=%d tilt=%d" % (int(round(pan_angle)), int(round(tilt_angle)))
                print("DEBUG: %s" % msg, flush=True)

            # Draw
            if best_cx is not None:
                cx, cy = int(best_cx), int(best_cy)
                cv2.circle(frame, (cx, cy), 12, (0, 255, 0), 2)
                cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 2)
                cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 2)
            cv2.circle(frame, (int(center_x), int(center_y)), 6, (128, 128, 128), 1)

            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                fps_display = fps_counter
                fps_counter = 0
                fps_timer = time.time()
            # When headless: print status at least every 2 seconds (so slow Pi still shows output)
            now = time.time()
            if not show_window and (now - last_status_print >= 2.0 or frame_count <= 2):
                last_status_print = now
                msg = "FPS: %d | Target: %s" % (fps_display, best_label if best_label else "scanning")
                if servo:
                    msg += " | pan=%d tilt=%d" % (int(round(pan_angle)), int(round(tilt_angle)))
                print(msg, flush=True)
            status = "FPS: %d | Target: %s" % (fps_display, best_label if best_label else "scanning")
            cv2.putText(
                frame, status,
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )

            if show_window:
                cv2.imshow(WINDOW_NAME, frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
            else:
                time.sleep(0.03)
    finally:
        cap.release()
        if servo:
            servo.set_angle(PAN_SERVO_PORT, PAN_CENTER)
            servo.set_angle(TILT_SERVO_PORT, TILT_CENTER)
        if show_window:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
