#!/usr/bin/env bash
#
# Run the cat tracker on a MacBook to test detection and tracking (no servo).
# Uses the built-in webcam and shows the live view with bounding boxes.
#
# First time: install deps with   ./test_tracking_mac.sh --install
# Then run:   ./test_tracking_mac.sh
#
# Press Q in the window to quit.
#

set -e
cd "$(dirname "$0")"
REPO_ROOT="$(cd .. && pwd)"

# Prefer venv in cat_tracker, then repo root
if [ -x "venv/bin/python3" ]; then
  PY="venv/bin/python3"
elif [ -x "$REPO_ROOT/venv/bin/python3" ]; then
  PY="$REPO_ROOT/venv/bin/python3"
else
  PY="python3"
fi

if [ "$1" = "--install" ]; then
  echo "Installing dependencies (opencv + ultralytics)..."
  "$PY" cat_tracker.py --install-deps
  echo "Done. Run ./test_tracking_mac.sh to start."
  exit 0
fi

echo "Starting tracker (camera only, no servo). Press Q to quit."
echo "Track: cat,person — green box = current target, orange = other detections."
echo ""

"$PY" cat_tracker.py \
  --no-servo \
  --track "cat,person" \
  --camera 0
