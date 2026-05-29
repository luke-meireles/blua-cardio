"""CSV persistence helpers for cardiac data."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from .analysis import BeatRecord

CSV_COLUMNS = [
    "datetime",
    "patient",
    "timestamp_s",
    "ibi_ms",
    "bpm",
    "media_ibi",
    "desvio_medio",
    "bat_anormais",
    "status",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
# TODO Passo 8 (INTEGRACAO_ARRHYTHMIAMONITOR.md §3.2): usar shared.paths.TELEMETRY_CSV
DEFAULT_CSV = DATA_DIR / "cardiac_data.csv"
# TODO Passo 8 (INTEGRACAO_ARRHYTHMIAMONITOR.md §3.2): usar shared.paths.GABRIEL_CSV
GABRIEL_CSV = DATA_DIR / "gabriel_data.csv"


def ensure_csv(path: Path = DEFAULT_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
    return path


def append_beat(record: BeatRecord, patient: str = "live", path: Path = DEFAULT_CSV,
                dt: Optional[datetime] = None) -> None:
    ensure_csv(path)
    row = [
        (dt or datetime.now()).isoformat(timespec="seconds"),
        patient,
        record.timestamp_s,
        record.ibi_ms,
        record.bpm,
        record.media_ibi,
        record.desvio_medio,
        record.bat_anormais,
        record.status,
    ]
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def append_many(records: Iterable[BeatRecord], patient: str = "live",
                path: Path = DEFAULT_CSV) -> None:
    ensure_csv(path)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for r in records:
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                patient,
                r.timestamp_s,
                r.ibi_ms,
                r.bpm,
                r.media_ibi,
                r.desvio_medio,
                r.bat_anormais,
                r.status,
            ])


def load_csv(path: Path = DEFAULT_CSV) -> pd.DataFrame:
    ensure_csv(path)
    df = pd.read_csv(path)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    return df


def clear_csv(path: Path = DEFAULT_CSV) -> None:
    if path.exists():
        path.unlink()
    ensure_csv(path)
