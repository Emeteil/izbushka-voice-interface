import asyncio
import threading
from colorama import Fore, Style
from typing import Any
import logging
import os
import shutil
import subprocess

from settings import *
import external_tools.get_current_time
import external_tools.set_emotion

class GeminiCLI:
    def __init__(self, va_instance: Any, detector_instance: Any):
        self.va = va_instance
        self.detector = detector_instance
        self.is_calling = False
        
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", force=True)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self._audio_command = "mpg123" if shutil.which("mpg123") is not None else "ffplay" if shutil.which("ffplay") is not None else None
        
        self.setup_callbacks()
        self.detector.callback = self.on_wake_word

    def setup_callbacks(self) -> None:
        self.va.on_log = lambda t: self._handle_log(t)
        self.va.on_error = lambda e: self._handle_error(e)
        self.va.on_message = lambda r, t: self._handle_message(r, t)
        self.va.on_tool_call = lambda n, a: self._handle_tool_call(n, a)
        self.va.on_tool_result = lambda n, r: self._handle_tool_result(n, r)
        self.va.on_status_change = self.handle_status_change

    def _handle_log(self, text: str):
        self.logger.info(f"{Fore.CYAN}[SYS]{Style.RESET_ALL} {text}")
        
    def _handle_error(self, error: Any):
        self.logger.error(f"{Fore.RED}[ERR]{Style.RESET_ALL} {error}")
        
    def _handle_message(self, role: str, text: str):
        self.logger.info(f"{Fore.GREEN}{Style.BRIGHT}GEMINI:{Style.RESET_ALL} {text}")

    def _handle_tool_call(self, name: str, args: Any):
        self.logger.info(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} {name}({args})")

    def _handle_tool_result(self, name: str, result: Any):
        self.logger.info(f"{Fore.MAGENTA}[RESULT]{Style.RESET_ALL} {name} -> {result}")

    def _play_sound(self, name: str, blocking: bool = False) -> None:
        if not self._audio_command:
            return
        path = os.path.join("sounds", f"{name}.mp3")
        if os.path.exists(path):
            cmd = [self._audio_command, "-q"] if self._audio_command == "mpg123" else [self._audio_command, "-autoexit", "-nodisp"]
            cmd.append(path)
            if blocking:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                threading.Thread(target=lambda: subprocess.run(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                ), daemon=True).start()

    def handle_status_change(self, status: str) -> None:
        if status == "online":
            self.is_calling = True
            self._play_sound("connect")
            self.logger.info(f"{Fore.GREEN}[SYS]{Style.RESET_ALL} Ассистент ONLINE. Можете говорить.")
        else:
            self.is_calling = False
            self._play_sound("disconnect")
            self.logger.info(f"{Fore.YELLOW}[SYS]{Style.RESET_ALL} Звонок завершен. Ассистент OFFLINE.")
            self.logger.info(f"{Fore.CYAN}[SYS]{Style.RESET_ALL} Ожидание wake word...")
            self.detector.unpause()

    def on_wake_word(self, detected_word: str) -> None:
        self.logger.info(f"{Fore.GREEN}[WAKE WORD]{Style.RESET_ALL} Обнаружено '{detected_word}'. Запуск ассистента...")
        self.detector.pause()
        if not self.is_calling:
            def _start_va():
                self.run_va()
            threading.Thread(target=_start_va, daemon=True).start()

    def run_va(self) -> None:
        try:
            asyncio.run(self.va.run())
        except Exception as e:
            self.logger.error(f"Error in run_va: {e}", exc_info=True)

    def start(self):
        wake_word_model = settings.get("wake_word_settings", {}).get("model_name", "alexa")
        self.logger.info(f"{Fore.CYAN}[SYS]{Style.RESET_ALL} Запуск CLI. Ожидание wake word ({wake_word_model})...")
        self._play_sound("init")
        try:
            self.detector.start()
        except KeyboardInterrupt:
            self.logger.info("Остановка пользователем...")
            try:
                self.va.stop()
            except Exception:
                pass
            os._exit(0)

if __name__ == "__main__":
    cli_app = GeminiCLI(va, detector)
    cli_app.start()