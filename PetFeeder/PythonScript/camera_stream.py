import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading

cam = cv2.VideoCapture(0)

class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith('/cam'):
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            while True:
                ret, img = cam.read()
                if not ret:
                    break
                _, jpeg = cv2.imencode('.jpg', img)
                self.wfile.write(b"--frame\r\n")
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(jpeg.tobytes())))
                self.end_headers()
                self.wfile.write(jpeg.tobytes())
                self.wfile.write(b"\r\n")
        else:
            self.send_error(404)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

def main():
    try:
        server = ThreadedHTTPServer(('0.0.0.0', 8000), CamHandler)
        print("Camera streaming at http://<Pi-IP>:8000/cam")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        print("Camera stopped.")

if __name__ == '__main__':
    main()
