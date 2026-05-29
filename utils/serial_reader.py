"""
ESP32 serial reader.

ESP32 firmware emits newline-delimited JSON: {"bpm": 75.3, "ibi": 820, "ts_ms": 12345}
pyserial is imported lazily so the app still runs without it.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import List, Optional


@dataclass
class SerialConfig:
    port: str = "COM3"
    baudrate: int = 115200
    timeout: float = 1.0


@dataclass
class SerialReader:
    config: SerialConfig = field(default_factory=SerialConfig)
    _thread: Optional[threading.Thread] = None
    _stop: threading.Event = field(default_factory=threading.Event)
    queue: "Queue[dict]" = field(default_factory=Queue)
    last_error: Optional[str] = None
    connected: bool = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.connected = False

    def drain(self) -> List[dict]:
        out: List[dict] = []
        while True:
            try:
                out.append(self.queue.get_nowait())
            except Empty:
                break
        return out

    def _run(self) -> None:
        try:
            import serial  # type: ignore
        except ImportError:
            self.last_error = "pyserial not installed (pip install pyserial)"
            return
        try:
            ser = serial.Serial(self.config.port, self.config.baudrate,
                                timeout=self.config.timeout)
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"Cannot open {self.config.port}: {exc}"
            return
        self.connected = True
        self.last_error = None
        try:
            while not self._stop.is_set():
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.queue.put(payload)
        finally:
            try:
                ser.close()
            except Exception:  # noqa: BLE001
                pass
            self.connected = False
