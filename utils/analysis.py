"""
Cardiac PPG analysis utilities.

Sliding-window logic documented in the reference dataset:
  - Window N = 5 beats
  - Regular   : desvio medio < 100 ms
  - Irregular : desvio medio > 120 ms
  - Between   : "atencao" (borderline)
  - Abnormal beats in the window: |IBI - media| > 120 ms
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import mean
from typing import Deque, List, Optional

WINDOW_N = 5
THRESHOLD_REGULAR_MS = 100.0
THRESHOLD_IRREGULAR_MS = 120.0
ABNORMAL_BEAT_MS = 120.0

STATUS_REGULAR = "regular"
STATUS_ATTENTION = "atencao"
STATUS_IRREGULAR = "irregular"


@dataclass
class BeatRecord:
    timestamp_s: float
    ibi_ms: float
    bpm: float
    media_ibi: float
    desvio_medio: float
    bat_anormais: int
    status: str


@dataclass
class PPGAnalyzer:
    window_n: int = WINDOW_N
    _ibis: Deque[float] = field(default_factory=deque)
    _timestamps: List[float] = field(default_factory=list)
    _t0: Optional[float] = None

    def reset(self) -> None:
        self._ibis.clear()
        self._timestamps.clear()
        self._t0 = None

    def add_beat(self, ibi_ms: float, timestamp_s: Optional[float] = None) -> BeatRecord:
        if ibi_ms <= 0:
            raise ValueError("IBI must be > 0 ms")

        if timestamp_s is None:
            if self._t0 is None:
                timestamp_s = 0.0
            else:
                timestamp_s = self._timestamps[-1] + (ibi_ms / 1000.0)
        if self._t0 is None:
            self._t0 = timestamp_s
        self._timestamps.append(timestamp_s)

        self._ibis.append(ibi_ms)
        if len(self._ibis) > self.window_n:
            self._ibis.popleft()

        media_ibi = mean(self._ibis)
        desvio_medio = mean(abs(v - media_ibi) for v in self._ibis)
        bat_anormais = sum(1 for v in self._ibis if abs(v - media_ibi) > ABNORMAL_BEAT_MS)
        status = classify_status(desvio_medio)
        bpm = 60000.0 / ibi_ms

        return BeatRecord(
            timestamp_s=round(timestamp_s - self._t0, 3),
            ibi_ms=round(ibi_ms, 2),
            bpm=round(bpm, 1),
            media_ibi=round(media_ibi, 2),
            desvio_medio=round(desvio_medio, 2),
            bat_anormais=bat_anormais,
            status=status,
        )


def classify_status(desvio_medio_ms: float) -> str:
    if desvio_medio_ms < THRESHOLD_REGULAR_MS:
        return STATUS_REGULAR
    if desvio_medio_ms > THRESHOLD_IRREGULAR_MS:
        return STATUS_IRREGULAR
    return STATUS_ATTENTION


def status_color(status: str) -> str:
    return {
        STATUS_REGULAR: "#1FAE6F",
        STATUS_ATTENTION: "#F2B705",
        STATUS_IRREGULAR: "#E53E3E",
    }.get(status, "#6B7A90")


def status_label_pt(status: str) -> str:
    return {
        STATUS_REGULAR: "Regular",
        STATUS_ATTENTION: "Atencao",
        STATUS_IRREGULAR: "Irregular",
    }.get(status, status.title())


def bpm_zone(bpm: float) -> str:
    if bpm < 50:
        return "Bradicardia severa"
    if bpm < 60:
        return "Bradicardia"
    if bpm <= 100:
        return "Normal"
    if bpm <= 120:
        return "Taquicardia leve"
    if bpm <= 150:
        return "Taquicardia moderada"
    return "Taquicardia severa"


def bpm_zone_color(bpm: float) -> str:
    z = bpm_zone(bpm)
    return {
        "Bradicardia severa": "#E53E3E",
        "Bradicardia": "#F2B705",
        "Normal": "#1FAE6F",
        "Taquicardia leve": "#F2B705",
        "Taquicardia moderada": "#EB8034",
        "Taquicardia severa": "#E53E3E",
    }[z]
