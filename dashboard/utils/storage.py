"""CSV persistence helpers for cardiac data."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from utils.analysis import classify_status

import pandas as pd
from dotenv import load_dotenv

from .analysis import BeatRecord

load_dotenv()

# --- Colunas ---
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

BLOB_COLUMNS = [
    "Timestamp (s)",
    "IBI (ms)",
    "BPM",
    "Média IBI",
    "Desvio Médio",
    "Bat. Anormais (janela)",
    "Status",
]

# --- Caminhos Locais ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CSV = DATA_DIR / "cardiac_data.csv"
GABRIEL_CSV = DATA_DIR / "gabriel_data.csv"

# --- Azure Blob ---
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER = "dataset"
BLOB_NAME = "dataset_ppg.csv"

# --- Funções locais (mantidas intactas) ---
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


# --- Funções Azure Blob ---

def blob_available() -> bool:
    # Verifica se a connection string está configurada.
    return bool(AZURE_CONNECTION_STRING)

def load_blob(tail: Optional[int] = None) -> pd.DataFrame:
    """
    Lê o dataset_ppg.csv vindo do Azure Blob Storage.
    tail: se informado, retorna apenas os últimos N registros.
    Retorna Dataframe vazio caso haja falha
    """
    if not blob_available():
        return pd.DataFrame(columns= BLOB_COLUMNS)
    
    try:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob = client.get_blob_client(container= BLOB_CONTAINER, blob= BLOB_NAME)
        conteudo = blob.download_blob().readall().decode("utf-8")

        from io import StringIO
        df = pd.read_csv(StringIO(conteudo))

        if df.empty:
            return df
        
        # Normaliza nomes de colunas
        df.columns = [c.strip() for c in df.columns]

        # Renomeia para padrão interno do dashboard
        df = df.rename(columns={
            "Timestamp (s)":        "timestamp_s",
            "IBI (ms)":             "ibi_ms",
            "BPM":                  "bpm",
            "Média IBI":            "media_ibi",
            "Desvio Médio":         "desvio_medio",
            "Bat. Anormais (janela)": "bat_anormais",
            "Status":               "status",
        })

        df["status"] = df["desvio_medio"].apply(classify_status)

        if tail:
            df = df.tail(tail).reset_index(drop= True)
        return df
    
    except Exception as e:
        print(f"[Storage] Erro ao ler Blob: {e}")
        return pd.DataFrame()
