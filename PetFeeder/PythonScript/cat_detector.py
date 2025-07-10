import cv2
import json
import os
import sys
from datetime import datetime
import signal

# === Configuration ===
LOG_FILE = "pet_feeder_logs.json"
CASCADE_PATH = "haarcascade_frontalcatface.xml"
HEADLESS = "--headless" in sys.argv

# === Initialize ===
print("[DETECTOR] Starting in headless mode" if HEADLESS else "[DETECTOR] Starting with display")

cat_cascade = cv2.CascadeClassifier(CASCADE_PATH)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

if not cap.isOpened():
    print("[ERROR] Cannot access the camera. Is it already in use?")
    sys.exit(1)

# === Graceful Shutdown ===
def shutdown(sig=None, frame=None):
    print("\n[INFO] Shutting down cat detector...")
    cap.release()
    if not HEADLESS:
        cv2.destroyAllWindows()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# === Main Loop ===
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to read frame from camera")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect cat faces (sensitive parameters)
        cats = cat_cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=2
        )

        if len(cats) > 0:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[DETECTED] Cat at {timestamp}")

            # Append detection to log
            entry = {"timestamp": timestamp, "item": "cat_detected"}
            logs = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r") as f:
                        logs = json.load(f)
                except json.JSONDecodeError:
                    print("[WARN] Log file corrupted, resetting.")

            logs.append(entry)
            with open(LOG_FILE, "w") as f:
                json.dump(logs, f, indent=2)

        # Show live preview if not headless
        if not HEADLESS:
            for (x, y, w, h) in cats:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.imshow("Cat Detector", frame)

            # Exit on ESC
            if cv2.waitKey(1) == 27:
                break

except Exception as e:
    print(f"[ERROR] {e}")
finally:
    shutdown()
