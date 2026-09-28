import cv2
import base64
import threading
import time
import numpy as np
import requests
from typing import Optional, Tuple
from gemini_engine.media import BaseMediaHandler


class LoopbackCameraHandler(BaseMediaHandler):
    def __init__(self, url: str, rate: float = 1.0):
        # a plain single-shot JPEG GET is used instead of cv2.VideoCapture on the
        # MJPEG stream: a long-lived FFmpeg demux thread over HTTP proved to be an
        # unstable native dependency (observed a process-wide segfault in it), and
        # this handler only ever needs the latest frame, not continuous decoding.
        self.url = url
        self._rate = rate
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
            try:
                resp = requests.get(self.url, timeout=3.0)
                resp.raise_for_status()
                buffer = np.frombuffer(resp.content, dtype=np.uint8)
                frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
                if frame is not None:
                    with self.lock:
                        self.last_frame = frame
            except Exception:
                pass
            time.sleep(max(0.0, 1.0 / self._rate))

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
