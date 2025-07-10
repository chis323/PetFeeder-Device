import socket
import threading
import time
from datetime import datetime
from gpiozero import AngularServo, DigitalInputDevice, DigitalOutputDevice
from time import sleep
import subprocess
import os
import json
import signal
import sys
from azure.storage.blob import BlobServiceClient, ContentSettings
import time
import requests

def wait_for_network():
    while True:
        try:
            response = requests.get("http://www.google.com", timeout=5)
            if response.status_code == 200:
                return True
        except:
            print("Waiting for network connection...")
            time.sleep(5)

# At start of your script:

# Hardware Constants
DT_PIN = 6
SCK_PIN = 5
CALIBRATION_FACTOR = 106.0
WEIGHT_THRESHOLD = 20
LOG_FILE = "pet_feeder_logs.json"
ALLOWED_TIMES = ["09:00", "14:00", "20:00"]
CAMERA_PID_FILE = "camera_stream.pid"

# Azure Configuration
AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=chis32;AccountKey=40IAMnYjZbmiDFmXaxllKmQcglNI3/bmMP/8YdeoQydxUC7ueQ4cNGusxZ8o/P0FRzFEHqlq0+Tl+ASt6117ag==;EndpointSuffix=core.windows.net"
AZURE_CONTAINER_NAME = "jsondata"
AZURE_BLOB_NAME = "dispense_logs.json"
wait_for_network()
class PiServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.clients = []
        self.running = False
        self.server_socket = None
        self.camera_process = None
        self.stream_process = None
        self.last_azure_sync_time = None

        # Initialize Azure Blob Service Client
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
            print("[AZURE] Connected to Blob Storage")
        except Exception as e:
            print(f"[AZURE ERROR] Connection failed: {e}")
            self.blob_service_client = None

        # Servo setup
        self.servo_food = AngularServo(18, min_pulse_width=0.0006, max_pulse_width=0.0023)
        self.servo_water = AngularServo(17, min_pulse_width=0.0006, max_pulse_width=0.0023)
        self.servo_food.angle = None
        self.servo_water.angle = None
        self.servo_busy = False

        # Load cell setup
        self.dt = DigitalInputDevice(DT_PIN)
        self.sck = DigitalOutputDevice(SCK_PIN, initial_value=False)

        print("Taring load cell...")
        time.sleep(1)
        self.tare_value = self.read_raw()
        print(f"Tare complete. Tare value: {self.tare_value}")

        self.last_dispense_time = None

        # Initialize log file if it doesn't exist
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as f:
                json.dump([], f)
                
    
    def delete_log(self):
        # 1. Delete local log
        try:
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
                print("[LOCAL] Log file deleted")
            else:
                print("[LOCAL] Log file not found")

            # Recreate empty log
            with open(LOG_FILE, 'w') as f:
                json.dump([], f)
            print("[LOCAL] Empty log file recreated")

        except Exception as e:
            print(f"[ERROR] Deleting local log: {e}")

        # 2. Delete Azure blob
        if self.blob_service_client:
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=AZURE_CONTAINER_NAME,
                    blob=AZURE_BLOB_NAME
                )
                blob_client.delete_blob()
                print("[AZURE] Log blob deleted")
            except Exception as e:
                print(f"[AZURE ERROR] Could not delete blob: {e}")
        else:
            print("[AZURE] Not connected, skipped Azure delete")
        

    def read_raw(self):
        count = 0
        while self.dt.value == 1:
            pass
        for _ in range(24):
            self.sck.on()
            count <<= 1
            self.sck.off()
            if self.dt.value:
                count |= 1
        self.sck.on()
        self.sck.off()
        if count & 0x800000:
            count -= 0x1000000
        return count

    def get_weight(self):
        raw = self.read_raw()
        return (raw - self.tare_value) / CALIBRATION_FACTOR

    def log_event(self, event_type, **kwargs):
        event = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type
        }
        
        # Add event-specific data
        if event_type == "dispense":
            event.update({
                "item": kwargs.get("item_type"),
                "weight": round(self.get_weight(), 2)
            })
        elif event_type == "cat_detected":
            event.update({
                "confidence": kwargs.get("confidence", 0),
                "position": kwargs.get("position", "unknown")
            })
        
        # Load existing logs and append new event
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
        
        logs.append(event)
        
        # Save updated logs
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
        
        print(f"[LOGGED] {event}")
        
        # Upload to Azure
        self.upload_to_azure()

    def upload_to_azure(self):
        if not self.blob_service_client:
            print("[AZURE] No connection to Azure, skipping upload")
            return

        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r") as f:
                    log_data = json.load(f)
                
                json_data = json.dumps(log_data, indent=2)
                
                blob_client = self.blob_service_client.get_blob_client(
                    container=AZURE_CONTAINER_NAME,
                    blob=AZURE_BLOB_NAME
                )
                
                blob_client.upload_blob(
                    json_data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type='application/json')
                )
                
                print("[AZURE] Logs uploaded successfully")
                self.last_azure_sync_time = datetime.now()
        except Exception as e:
            print(f"[AZURE ERROR] Upload failed: {e}")

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        print(f"Server listening on {self.host}:{self.port}")
        threading.Thread(target=self.accept_connections, daemon=True).start()
        threading.Thread(target=self.auto_scheduler, daemon=True).start()
        threading.Thread(target=self.servo_reset_loop, daemon=True).start()
        threading.Thread(target=self.azure_sync_loop, daemon=True).start()
        self.start_camera_detector()

    def azure_sync_loop(self):
        while self.running:
            try:
                if (not self.last_azure_sync_time or 
                    (datetime.now() - self.last_azure_sync_time).total_seconds() > 3600):
                    self.upload_to_azure()
            except Exception as e:
                print(f"[AZURE SYNC ERROR] {e}")
            time.sleep(2)

    def servo_reset_loop(self):
        while self.running:
            if not self.servo_busy:
                if self.servo_food.angle is not None:
                    self.servo_food.angle = None
                if self.servo_water.angle is not None:
                    self.servo_water.angle = None
            time.sleep(0.5)

    def auto_scheduler(self):
        while self.running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            if current_time in ALLOWED_TIMES and self.last_dispense_time != current_time:
                if self.get_weight() < WEIGHT_THRESHOLD:
                    print(f"[AUTO] Scheduled dispense at {current_time}")
                    self.dispense_food()
                    self.last_dispense_time = current_time
                else:
                    print(f"[AUTO] Time reached, but food is sufficient.")
            elif current_time not in ALLOWED_TIMES:
                self.last_dispense_time = None
            time.sleep(30)

    def accept_connections(self):
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"[CONNECTED] {client_address}")
                self.clients.append(client_socket)
                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    print(f"[ERROR] Accept failed: {e}")

    def handle_client(self, client_socket, client_address):
        try:
            # Start camera automatically on new client connection
            self.start_camera()
            print("[AUTO] Camera started on client connect")

            while self.running:
                data = client_socket.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                self.process_command(data)
        except Exception as e:
            print(f"[ERROR] Client {client_address}: {e}")
        finally:
            client_socket.close()
            self.clients.remove(client_socket)
            print(f"[DISCONNECTED] {client_address}")


    def process_command(self, command):
        print(f"[COMMAND] {command}")
        if command == "Up":
            self.dispense_food()
        elif command == "Down":
            self.dispense_water()
        elif command == "Auto":
            if self.get_weight() < WEIGHT_THRESHOLD:
                self.dispense_food()
            else:
                print("[AUTO] Skipped, food weight sufficient.")
        elif command == "Camera":
            self.start_camera()
        elif command == "StopCamera":
            self.stop_camera()
        elif command == "DeleteLog":
            self.delete_log()
        else:
            print(f"[UNKNOWN COMMAND] {command}")

    def dispense_food(self):
        print("[ACTION] Dispensing food...")
        self.servo_busy = True
        self.servo_food.angle = 0
        sleep(0.7)
        self.servo_food.angle = 90
        sleep(0.3)
        self.servo_food.angle = None
        self.servo_busy = False
        self.log_event("dispense", item_type="food")

    def dispense_water(self):
        print("[ACTION] Dispensing water...")
        self.servo_busy = True
        self.servo_water.angle = -70
        sleep(5)
        self.servo_water.angle = 20
        sleep(0.3)
        self.servo_water.angle = None
        self.servo_busy = False
        self.log_event("dispense", item_type="water")

    def log_cat_detection(self, confidence=0, position="unknown"):
        self.log_event("cat_detected", confidence=confidence, position=position)

    def start_camera_detector(self):
        if not self.is_camera_detector_running():
            try:
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cat_detector.py")
                self.camera_process = subprocess.Popen(
                    [sys.executable, script_path, "--headless"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                # Add thread to monitor detector output
                threading.Thread(target=self.monitor_detector_output, daemon=True).start()
                time.sleep(1)
                if self.camera_process.poll() is None:
                    print(f"[DETECTOR] Started (PID: {self.camera_process.pid})")
                else:
                    err = self.camera_process.stderr.read().decode()
                    print(f"[ERROR] Detector failed: {err}")
            except Exception as e:
                print(f"[ERROR] Failed to start detector: {str(e)}")

    def monitor_detector_output(self):
        while self.running and self.camera_process:
            output = self.camera_process.stdout.readline().decode().strip()
            if output and "DETECTED" in output:
                try:
                    # Parse detection details from output
                    parts = output.split("|")
                    confidence = float(parts[1].split(":")[1].strip())
                    position = parts[2].split(":")[1].strip()
                    self.log_cat_detection(confidence=confidence, position=position)
                except Exception as e:
                    print(f"[DETECTOR ERROR] Parsing output: {e}")
            elif output:
                print(f"[DETECTOR] {output}")

    def stop_camera_detector(self):
        if self.camera_process:
            try:
                os.killpg(os.getpgid(self.camera_process.pid), signal.SIGTERM)
                self.camera_process.wait(timeout=3)
                print("[DETECTOR] Stopped")
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self.camera_process.pid), signal.SIGKILL)
                except:
                    pass
            finally:
                self.camera_process = None

    def is_camera_detector_running(self):
        if self.camera_process:
            return self.camera_process.poll() is None
        return False

    def start_camera(self):
        if not self.is_camera_streaming():
            try:
                self.stream_process = subprocess.Popen(
                    ["python3", "camera_stream.py"],
                    preexec_fn=os.setsid,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                with open(CAMERA_PID_FILE, "w") as f:
                    f.write(str(self.stream_process.pid))
                print("[STREAM] Started")
            except Exception as e:
                print(f"[ERROR] Failed to start stream: {str(e)}")
        else:
            print("[STREAM] Already running")

    def stop_camera(self):
        if os.path.exists(CAMERA_PID_FILE):
            try:
                with open(CAMERA_PID_FILE, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                os.remove(CAMERA_PID_FILE)
                print("[STREAM] Stopped")
            except Exception as e:
                print(f"[ERROR] Could not stop stream: {e}")
        if self.stream_process:
            self.stream_process = None

    def is_camera_streaming(self):
        if os.path.exists(CAMERA_PID_FILE):
            with open(CAMERA_PID_FILE, "r") as f:
                pid = f.read().strip()
            try:
                os.kill(int(pid), 0)
                return True
            except ProcessLookupError:
                os.remove(CAMERA_PID_FILE)
        return False

    def stop(self):
        self.running = False
        self.stop_camera()
        self.stop_camera_detector()
        self.upload_to_azure()
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        if self.server_socket:
            self.server_socket.close()
        self.sck.close()
        self.dt.close()
        print("[SERVER] Shutdown complete")

if __name__ == "__main__":
    server = PiServer()
    try:
        server.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[EXIT] Shutting down...")
        server.stop()
