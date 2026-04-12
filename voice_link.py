import asyncio
import json
import logging
import threading
from typing import Optional, Callable

import websockets

logger = logging.getLogger("VoiceLink")

class VoiceLink:
    def __init__(self, ws_url: str, reconnect_interval: float = 5.0):
        self._ws_url = ws_url
        self._reconnect_interval = reconnect_interval
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        self.on_trigger: Optional[Callable] = None
        self.on_stop: Optional[Callable] = None

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._running

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"VoiceLink starting, target: {self._ws_url.split('?')[0]}")

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            logger.error(f"VoiceLink loop error: {e}")
        finally:
            self._loop.close()
            self._loop = None

    async def _connect_loop(self):
        while self._running:
            try:
                async with websockets.connect(self._ws_url) as ws:
                    self._ws = ws
                    logger.info("Connected to web-core")
                    await self._listen(ws)
            except (ConnectionRefusedError, OSError, websockets.exceptions.WebSocketException) as e:
                if self._running:
                    logger.warning(f"Connection failed: {e}, retrying in {self._reconnect_interval}s")
            finally:
                self._ws = None

            if self._running:
                await asyncio.sleep(self._reconnect_interval)

    async def _listen(self, ws: websockets.WebSocketClientProtocol):
        try:
            async for message in ws:
                try:
                    msg = json.loads(message)
                    event = msg.get("event", "")
                    self._dispatch(event)
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            logger.info("Disconnected from web-core")

    def _dispatch(self, event: str):
        if event == "voice.trigger" and self.on_trigger:
            try:
                self.on_trigger()
            except Exception as e:
                logger.error(f"Trigger callback error: {e}")
        elif event == "voice.stop" and self.on_stop:
            try:
                self.on_stop()
            except Exception as e:
                logger.error(f"Stop callback error: {e}")

    def send_event(self, event: str, data: dict = None):
        if not self._ws or not self._loop or not self._running:
            return
        asyncio.run_coroutine_threadsafe(
            self._send(event, data or {}),
            self._loop
        )

    async def _send(self, event: str, data: dict):
        if self._ws:
            try:
                await self._ws.send(json.dumps({"event": event, "data": data}))
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._ws and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            except Exception:
                pass