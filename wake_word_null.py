import threading


class NullWakeWordDetector:
    def __init__(self):
        self.callback = None

    def pause(self) -> None:
        pass

    def unpause(self) -> None:
        pass

    def start(self) -> None:
        threading.Event().wait()
