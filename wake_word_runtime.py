import threading

from wake_word.detector import WakeWordDetector


class RuntimeWakeWordDetector(WakeWordDetector):
    """WakeWordDetector that can be switched on and off while the process runs.

    Disabled means the microphone is released and detections are dropped; the
    pause()/unpause() calls made around an assistant session keep working and can
    never re-enable a detector that was switched off.
    """

    def __init__(self, *args, enabled: bool = True, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._enabled = enabled
        self._held = False
        self._state_lock = threading.RLock()
        if not enabled:
            self._is_paused = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def pause(self) -> None:
        with self._state_lock:
            self._held = True
            super().pause()

    def unpause(self) -> None:
        with self._state_lock:
            self._held = False
            if self._enabled:
                super().unpause()

    def set_enabled(self, enabled: bool) -> None:
        with self._state_lock:
            if enabled == self._enabled:
                return
            self._enabled = enabled
            if enabled:
                if not self._held:
                    super().unpause()
                self.logger.info("Wake word включён.")
            else:
                super().pause()
                self.logger.info("Wake word выключен. Микрофон освобождён.")

    def _open_stream(self, actual_blocksize: int) -> None:
        with self._state_lock:
            if self._is_paused:
                return
            super()._open_stream(actual_blocksize)
