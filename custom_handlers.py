import cv2
import base64
import threading
import time
from typing import Optional, Tuple
from gemini_engine.media import BaseMediaHandler

class LoopbackCameraHandler(BaseMediaHandler):
    def __init__(self, url: str, rate: float = 1.0):
        self.url = url
        self._rate = rate
        self.cap = cv2.VideoCapture(url)
        self.last_frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    @property
    def rate(self) -> float:
        return self._rate

    def _capture_worker(self):
        while self.running:
            if not self.cap or not self.cap.isOpened():
                if self.cap:
                    try:
                        self.cap.release()
                    except:
                        pass
                self.cap = cv2.VideoCapture(self.url)
                time.sleep(1)
                continue
                
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
                with self.lock:
                    self.last_frame = frame
            except Exception:
                if self.cap:
                    try:
                        self.cap.release()
                    except:
                        pass
                self.cap = None
                time.sleep(1)

    def get_chunk(self) -> Optional[Tuple[str, str]]:
        with self.lock:
            frame = self.last_frame
        
        if frame is None:
            return None
            
        try:
            frame = cv2.resize(frame, (640, 480))
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return "image/jpeg", base64.b64encode(buffer).decode('utf-8')
        except Exception:
            return None

    def close(self) -> None:
        self.running = False
        if self.cap:
            self.cap.release()