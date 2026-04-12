import asyncio
import threading
from colorama import Fore, Style
from typing import Any
import logging
import os
import shutil
import subprocess

from settings import *
from voice_link import VoiceLink
import external_tools.get_current_time
import external_tools.set_emotion


class GeminiCLI:
    def __init__(self, va_instance: Any, detector_instance: Any, link: VoiceLink = None):
        self.va = va_instance
        self.detector = detector_instance
        self.link = link
        self.is_calling = False

        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", force=True)
        self.logger = logging.getLogger(self.__class__.__name__)

        self._audio_command = "mpg123" if shutil.which("mpg123") is not None else "ffplay" if shutil.which("ffplay") is not None else None

        self.setup_callbacks()
        self.detector.callback = self.on_wake_word

        if self.link:
            self.link.on_trigger = self._on_remote_trigger
            self.link.on_stop = self._on_remote_stop

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
        if self.link:
            self.link.send_event("voice.error", {"message": str(error)})

    def _handle_message(self, role: str, text: str):
        self.logger.info(f"{Fore.GREEN}{Style.BRIGHT}GEMINI:{Style.RESET_ALL} {text}")
        if self.link:
            self.link.send_event("voice.message", {"role": role, "text": text})

    def _handle_tool_call(self, name: str, args: Any):
        self.logger.info(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} {name}({args})")
        if self.link:
            self.link.send_event("voice.tool_call", {"name": name, "args": str(args)})

    def _handle_tool_result(self, name: str, result: Any):
        self.logger.info(f"{Fore.MAGENTA}[RESULT]{Style.RESET_ALL} {name} -> {result}")
        if self.link:
            self.link.send_event("voice.tool_result", {"name": name, "result": str(result)})

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
            if self.link:
                self.link.send_event("voice.status_changed", {"status": "active"})
        else:
            self.is_calling = False
            self._play_sound("disconnect")
            self.logger.info(f"{Fore.YELLOW}[SYS]{Style.RESET_ALL} Звонок завершен. Ассистент OFFLINE.")
            self.logger.info(f"{Fore.CYAN}[SYS]{Style.RESET_ALL} Ожидание wake word...")
            if self.link:
                self.link.send_event("voice.status_changed", {"status": "idle"})
            self.detector.unpause()

    def on_wake_word(self, detected_word: str) -> None:
        self.logger.info(f"{Fore.GREEN}[WAKE WORD]{Style.RESET_ALL} Обнаружено '{detected_word}'. Запуск ассистента...")
        self.detector.pause()
        if self.link:
            self.link.send_event("voice.status_changed", {"status": "wake_word_detected", "word": detected_word})
        if not self.is_calling:
            threading.Thread(target=self.run_va, daemon=True).start()

    def _on_remote_trigger(self):
        self.logger.info(f"{Fore.GREEN}[REMOTE]{Style.RESET_ALL} Удалённый вызов ассистента")
        if not self.is_calling:
            self.on_wake_word("remote_trigger")

    def _on_remote_stop(self):
        self.logger.info(f"{Fore.YELLOW}[REMOTE]{Style.RESET_ALL} Удалённая остановка ассистента")
        if self.is_calling:
            try:
                self.va.stop()
            except Exception:
                pass

    def run_va(self) -> None:
        try:
            asyncio.run(self.va.run())
        except Exception as e:
            self.logger.error(f"Error in run_va: {e}", exc_info=True)

    def start(self):
        wake_word_model = settings.get("wake_word_settings", {}).get("model_name", "alexa")
        self.logger.info(f"{Fore.CYAN}[SYS]{Style.RESET_ALL} Запуск CLI. Ожидание wake word ({wake_word_model})...")
        self._play_sound("init")

        if self.link:
            self.link.start()

        try:
            self.detector.start()
        except KeyboardInterrupt:
            self.logger.info("Остановка пользователем...")
            if self.link:
                self.link.stop()
            try:
                self.va.stop()
            except Exception:
                pass
            os._exit(0)


if __name__ == "__main__":
    web_core = settings.get("web_core", {})
    ws_host = web_core.get("host", "127.0.0.1")
    ws_port = web_core.get("port", 80)
    master_token = settings.get("MASTER_TOKEN", "")

    link = VoiceLink(
        ws_url=f"ws://{ws_host}:{ws_port}/api/voice/link?token={master_token}",
        reconnect_interval=web_core.get("reconnect_interval", 5.0)
    )

    cli_app = GeminiCLI(va, detector, link)
    cli_app.start()