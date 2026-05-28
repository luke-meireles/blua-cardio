"""
Ponte de telemetria: leitura do cardiac_data.csv do dashboard a partir
de qualquer consumidor (em particular, das tools do chatbot).

Cuidados de design:
- não cache o DataFrame inteiro: o CSV é apendado em tempo real pelo /monitor
  e qualquer cache stale entregaria dados antigos. Usamos pandas.read_csv
  direto — cache do filesystem do kernel já faz o trabalho pesado.
- a coluna `patient` do dashboard nem sempre bate com o `paciente_id` do
  chatbot. O dashboard atualmente grava "live", "live-sim" e nomes próprios
  como "Gabriel". O mapa `_ALIAS` resolve esses casos sem alterar dados
  legados.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .paths import TELEMETRY_CSV, GABRIEL_CSV

# Map opcional de paciente_id (chatbot) → strings aceitas na coluna `patient`
# do dashboard. Estendido em runtime via `register_alias`.
_ALIAS: dict[str, list[str]] = {
    # BENEF-MARIA é a paciente canônica do enunciado Sprint 2.
    # O dataset de referência do dashboard é o "Gabriel" — usamos como fallback.
    "BENEF-MARIA": ["BENEF-MARIA", "Gabriel", "live", "live-sim"],
}


def register_alias(paciente_id: str, *aliases: str) -> None:
    """Permite que outros módulos plugem aliases extras em runtime."""
    bag = _ALIAS.setdefault(paciente_id, [paciente_id])
    for a in aliases:
        if a not in bag:
            bag.append(a)


def _candidate_keys(paciente_id: str) -> list[str]:
    """Todos os valores aceitos para a coluna `patient` ao filtrar."""
    return list({paciente_id, *_ALIAS.get(paciente_id, [])})


def _read_csv_safe(path: Path) -> pd.DataFrame:
    """read_csv com fallback para DataFrame vazio se o arquivo não existir."""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_recent_beats(
    paciente_id: str,
    *,
    n: int = 60,
    csv_path: Path = TELEMETRY_CSV,
    fallback_to_gabriel: bool = True,
) -> pd.DataFrame:
    """
    Retorna os últimos `n` batimentos do paciente.

    Se não houver linhas para o paciente, e ele for BENEF-MARIA (canônico),
    cai para o gabriel_data.csv como referência. Para outros pacientes,
    devolve DataFrame vazio — caller decide o que fazer.
    """
    df = _read_csv_safe(csv_path)
    if not df.empty:
        keys = _candidate_keys(paciente_id)
        sub = df[df["patient"].isin(keys)]
        if not sub.empty:
            return sub.tail(n).reset_index(drop=True)

    # Fallback: dataset de referência para BENEF-MARIA
    if fallback_to_gabriel and paciente_id == "BENEF-MARIA":
        gab = _read_csv_safe(GABRIEL_CSV)
        if not gab.empty:
            return gab.tail(n).reset_index(drop=True)

    return pd.DataFrame()


def latest_beat(paciente_id: str) -> Optional[dict[str, Any]]:
    """
    Devolve o último batimento como dict no formato esperado pelo tool
    `analisar_ritmo_cardiaco` (chaves: IBI_ms, BPM, etc — note os
    nomes em CamelCase para casar com a assinatura legada).
    """
    df = load_recent_beats(paciente_id, n=1)
    if df.empty:
        return None
    row = df.iloc[-1]
    return {
        "timestamp_s": float(row["timestamp_s"]),
        "IBI_ms": float(row["ibi_ms"]),
        "BPM": float(row["bpm"]),
        "media_IBI": float(row["media_ibi"]),
        "desvio_medio": float(row["desvio_medio"]),
        "batimentos_anormais": int(row["bat_anormais"]),
        "status": str(row.get("status", "")),
        "datetime": str(row.get("datetime", "")),
    }


def window_summary(
    paciente_id: str,
    *,
    minutes: int = 5,
) -> dict[str, Any]:
    """
    Agrega estatísticas dos últimos N minutos do paciente.

    Returns:
        dict com BPM médio/mín/máx, distribuição de status (% regular,
        atenção, irregular) e timestamp da janela.
    """
    df = load_recent_beats(paciente_id, n=10_000)
    if df.empty:
        return {
            "paciente_id": paciente_id,
            "telemetria_disponivel": False,
            "mensagem": "Sem dados de PPG no dashboard para este paciente.",
        }

    # Filtrar pela janela temporal se houver coluna datetime
    if "datetime" in df.columns:
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        cutoff = df["datetime"].max() - timedelta(minutes=minutes)
        recent = df[df["datetime"] >= cutoff]
        if recent.empty:
            recent = df.tail(60)  # fallback: últimos 60 batimentos
    else:
        recent = df.tail(int(minutes * 60))

    total = max(len(recent), 1)
    status_counts = recent["status"].value_counts().to_dict()

    return {
        "paciente_id": paciente_id,
        "telemetria_disponivel": True,
        "janela_min": minutes,
        "n_beats": int(len(recent)),
        "bpm_medio": round(float(recent["bpm"].mean()), 1),
        "bpm_min": round(float(recent["bpm"].min()), 1),
        "bpm_max": round(float(recent["bpm"].max()), 1),
        "ibi_medio_ms": round(float(recent["ibi_ms"].mean()), 1),
        "desvio_medio_ms": round(float(recent["desvio_medio"].mean()), 1),
        "irregulares_pct": round(100 * status_counts.get("irregular", 0) / total, 1),
        "atencao_pct": round(100 * status_counts.get("atencao", 0) / total, 1),
        "regular_pct": round(100 * status_counts.get("regular", 0) / total, 1),
        "ultimo_status": str(recent.iloc[-1]["status"]),
        "ultimo_timestamp": str(recent.iloc[-1].get("datetime", "")),
    }
