"""
Tool: agendar_teleconsulta
Agenda teleconsulta com cardiologista na plataforma Blua. Fictício.

Persistência (Feature 1 do README upstream do ArrhythmiaMonitor):
dual-write best-effort.
- Azure Blob (primário, quando AZURE_STORAGE_CONNECTION_STRING configurada):
  container 'dataset', blob 'consultas_<paciente_id>.json'. Read-modify-write
  com upload overwrite — comportamento "cria-se-não-existir, append".
- Disco local (backup sempre): data/consultas/consultas_<paciente_id>.json
  (atomic write-then-rename).
- Falhas em qualquer um logam warning sem bloquear resposta. API pública
  (`agendar_teleconsulta`) inalterada — agents que consomem não precisam mudar.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from shared.paths import DATA_DIR

log = logging.getLogger(__name__)

_MOCK_PATH = Path(__file__).resolve().parents[2] / "data" / "mocks" / "agendamentos.json"

# Adiciona raiz do projeto ao sys.path pra resolver `from dashboard.utils.storage`
# (Feature 1 — reusa blob_available do upstream em vez de duplicar lógica).
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _construir_consulta(
    *,
    motivo: str,
    medico: str,
    disponibilidade_slot: str,
    urgencia: str,
    paciente_id: str | None,
) -> dict:
    """Monta o dict da consulta (formato compatível com consultas_gabriel.json
    do repositório ArrhythmiaMonitor)."""
    agora = datetime.now()
    # TODO Passo 8 (INTEGRACAO_ARRHYTHMIAMONITOR.md §3.2): popular
    # data_referencia com data real do slot (parsing de "Hoje"/"Amanhã"/etc)
    # quando integrar com calendário real.
    return {
        "disponibilidade_slot": disponibilidade_slot,
        "agendado_em": agora.isoformat(timespec="seconds"),
        "data_referencia": agora.strftime("%d/%m/%Y"),
        "tipo": "Consulta agendada via agente",
        "medico": medico,
        "urgencia": urgencia,
        "resumo": motivo,
        "status": "agendada",
        "paciente_id": paciente_id,
        "criado_por": "agendar_teleconsulta_v1",
    }


def _registrar_consulta_localmente_disco(
    paciente_id: str | None, consulta: dict
) -> Path | None:
    """Persiste consulta em data/consultas/consultas_<paciente_id>.json.
    Atomic write-then-rename. Best-effort — falha loga warning e retorna None."""
    try:
        consultas_dir = DATA_DIR / "consultas"
        consultas_dir.mkdir(parents=True, exist_ok=True)

        pid = paciente_id or "sem_paciente"
        arquivo = consultas_dir / f"consultas_{pid}.json"

        if arquivo.exists():
            with arquivo.open(encoding="utf-8") as f:
                consultas = json.load(f)
        else:
            consultas = []

        consultas.append(consulta)

        tmp = arquivo.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(consultas, f, ensure_ascii=False, indent=2)
        tmp.replace(arquivo)

        log.info("Consulta registrada em %s", arquivo)
        return arquivo
    except Exception as exc:
        log.warning("Falha ao persistir consulta no disco: %s: %s",
                    type(exc).__name__, exc)
        return None


def _registrar_consulta_no_blob(
    paciente_id: str | None, consulta: dict
) -> str | None:
    """Persiste consulta em Azure Blob (container 'dataset', blob
    'consultas_<paciente_id>.json'). Read-modify-write: baixa JSON
    existente (lista vazia se 404), append, upload com overwrite=True.
    Best-effort — falha loga warning e retorna None."""
    try:
        from dashboard.utils.storage import blob_available
        if not blob_available():
            return None

        from azure.storage.blob import BlobServiceClient

        conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not conn:
            return None

        pid = paciente_id or "sem_paciente"
        blob_name = f"consultas_{pid}.json"
        container = "dataset"

        client = BlobServiceClient.from_connection_string(conn)
        blob_client = client.get_blob_client(container=container, blob=blob_name)

        # Read (cria-se-não-existir: 404 ou parse error → lista vazia)
        try:
            conteudo = blob_client.download_blob().readall().decode("utf-8")
            existente = json.loads(conteudo)
            if not isinstance(existente, list):
                existente = []
        except Exception:
            existente = []

        # Modify
        existente.append(consulta)

        # Write (overwrite cria se não existir)
        blob_client.upload_blob(
            json.dumps(existente, ensure_ascii=False, indent=2),
            overwrite=True,
        )

        log.info("Consulta registrada no Azure Blob: %s/%s", container, blob_name)
        return blob_name

    except Exception as exc:
        log.warning("Falha ao registrar consulta no Blob: %s: %s",
                    type(exc).__name__, exc)
        return None


def _persistir_consulta(paciente_id: str | None, consulta: dict) -> dict:
    """Dual-write: Blob primário (se disponível) + disco local sempre.
    Best-effort em ambos — qualquer falha loga warning mas não bloqueia.

    Returns:
        {"blob": <nome_blob_ou_None>, "local": <Path_ou_None>}
    """
    blob_ref = _registrar_consulta_no_blob(paciente_id, consulta)
    local_ref = _registrar_consulta_localmente_disco(paciente_id, consulta)
    return {"blob": blob_ref, "local": local_ref}


def agendar_teleconsulta(
    urgencia: str,
    motivo: str,
    especialidade: str = "cardiologia",
    paciente_id: str | None = None,
) -> dict:
    """
    Agenda teleconsulta com cardiologista na plataforma Blua.

    Args:
        urgencia: rotina | prioritario | urgente
        motivo: Resumo clínico gerado pelo agente para briefing do médico.
        especialidade: Especialidade médica. Default: cardiologia.
        paciente_id: ID do paciente vinculado (BENEF-XXX). Opcional.
            Quando fornecido, o agendamento é persistido em
            consultas_<paciente_id>.json (Blob primário + disco local).
            Quando ausente, vai pra consultas_sem_paciente.json.

    Returns:
        Dicionário com confirmação e dados do agendamento, incluindo:
            registro_blob: nome do blob (str) se uploaded, None caso contrário
            registro_local: path do arquivo local (str) se gravado, None caso contrário
    """
    urgencias_validas = {"rotina", "prioritario", "urgente"}

    if urgencia not in urgencias_validas:
        return {
            "erro": f"Urgência '{urgencia}' inválida.",
            "urgencias_validas": list(urgencias_validas)
        }

    with open(_MOCK_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)

    slots = dados["slots_disponiveis"].get(urgencia, [])

    if not slots:
        return {"erro": f"Nenhum slot disponível para urgência '{urgencia}'."}

    # Selecionar primeiro slot disponível
    slot = slots[0]

    # Gerar código de confirmação único
    codigo = f"BLU-{urgencia[:3].upper()}-{uuid.uuid4().hex[:4].upper()}"
    link = f"{slot['link_base']}-{codigo.lower()}"

    # Construir + persistir consulta (dual-write best-effort)
    consulta = _construir_consulta(
        motivo=motivo,
        medico=slot["medico"],
        disponibilidade_slot=slot["disponibilidade"],
        urgencia=urgencia,
        paciente_id=paciente_id,
    )
    referencias = _persistir_consulta(paciente_id, consulta)

    return {
        "agendado": True,
        "especialidade": especialidade,
        "urgencia": urgencia,
        "medico": slot["medico"],
        "disponibilidade": slot["disponibilidade"],
        "plataforma": slot["plataforma"],
        "link_acesso": link,
        "codigo_confirmacao": codigo,
        "instrucoes": slot["instrucoes"],
        "motivo_registrado": motivo,
        "registro_blob": referencias["blob"],
        "registro_local": str(referencias["local"]) if referencias["local"] else None,
    }
