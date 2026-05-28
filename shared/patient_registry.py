"""
Registro de pacientes unificado.

Responsabilidades:
- ler perfis_clinicos.json (compartilhado entre chatbot e dashboard)
- criar novos pacientes a partir do chatbot (gera BENEF-NEW-NNN)
- expor a lista de pacientes para o dropdown do dashboard
- invalidar o cache LRU do tool `consultar_historico_paciente` quando
  um perfil é criado/editado, para que a próxima leitura veja o novo registro

Concorrência:
- escritas usam lock + write-then-rename atômico (anti-corrupção em caso de
  crash do processo entre o write e o close).
- leituras não bloqueiam — Python garante atomicidade de open()/read() de
  um arquivo do disco; só evitamos meio-escritas.
"""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

from .paths import PROFILES_JSON

# Lock por processo. Em deployments multi-processo (gunicorn workers),
# usar fcntl.flock no arquivo seria mais robusto — fica como roadmap.
_WRITE_LOCK = threading.RLock()


def _load_raw() -> dict[str, Any]:
    """Carrega o JSON. Levanta FileNotFoundError se o arquivo sumir."""
    with PROFILES_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def _atomic_write(data: dict[str, Any]) -> None:
    """
    Grava o JSON usando padrão write-then-rename para evitar arquivo
    parcialmente escrito caso o processo seja morto no meio.
    """
    tmp = PROFILES_JSON.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(PROFILES_JSON)  # rename atômico no mesmo filesystem


def list_patients() -> list[dict[str, Any]]:
    """Retorna a lista de beneficiários (cópia profunda — caller pode mutar)."""
    return deepcopy(_load_raw().get("beneficiarios", []))


def get_patient(paciente_id: str) -> Optional[dict[str, Any]]:
    """Retorna o perfil completo do paciente ou None se não encontrado."""
    return next(
        (deepcopy(p) for p in _load_raw().get("beneficiarios", [])
         if p.get("id") == paciente_id),
        None,
    )


def patient_exists(paciente_id: str) -> bool:
    return any(p.get("id") == paciente_id
               for p in _load_raw().get("beneficiarios", []))


def invalidate_caches() -> None:
    """
    Invalida o LRU cache do tool `consultar_historico_paciente`.

    Best-effort: se o tool ainda não foi importado neste processo, não faz
    nada. Não levanta exceção — pode ser chamado em testes onde o módulo
    do chatbot nem existe.
    """
    try:
        from src.tools.historico import _carregar_mock  # type: ignore
        _carregar_mock.cache_clear()
    except Exception:
        pass


def _next_new_id(existing_ids: set[str]) -> str:
    """Gera o próximo BENEF-NEW-NNN livre."""
    n = 1
    while f"BENEF-NEW-{n:03d}" in existing_ids:
        n += 1
    return f"BENEF-NEW-{n:03d}"


def create_patient(
    *,
    nome: str,
    idade: int,
    sexo: str,
    condicoes: Optional[list[dict[str, Any]]] = None,
    medicacoes: Optional[list[dict[str, Any]]] = None,
    alergias: Optional[list[str]] = None,
    plano: str = "Care Plus",
    score_risco: str = "a_avaliar",
    origem: str = "criado_via_chatbot",
) -> dict[str, Any]:
    """
    Cria um novo beneficiário no perfis_clinicos.json e devolve o registro.

    Args correspondem aos campos esperados pelo tool consultar_historico_paciente.
    O ID é gerado automaticamente como BENEF-NEW-NNN.

    Levanta ValueError se nome estiver vazio ou idade/sexo inválidos.
    """
    # Validação básica (a tool fará a sua própria — defesa em profundidade)
    if not nome or not nome.strip():
        raise ValueError("nome é obrigatório")
    if not (0 <= idade <= 120):
        raise ValueError(f"idade fora de [0,120]: {idade}")
    if sexo not in {"masculino", "feminino", "outro"}:
        raise ValueError(f"sexo inválido: {sexo!r}")

    with _WRITE_LOCK:
        data = _load_raw()
        existing_ids = {b["id"] for b in data.get("beneficiarios", [])}
        novo_id = _next_new_id(existing_ids)

        novo = {
            "id": novo_id,
            "nome": nome.strip(),
            "idade": int(idade),
            "sexo": sexo,
            "plano": plano,
            "condicoes_ativas": condicoes or [],
            "medicacoes_ativas": medicacoes or [],
            "alergias": alergias or [],
            "score_risco_cardiovascular": score_risco,
            "consultas": {
                "ultima": None,
                "proxima": None,
            },
            "exames_recentes": [],
            "sinais_vitais_ultimo_registro": {},
            "criado_em": datetime.now().isoformat(timespec="seconds"),
            "origem": origem,
        }

        data.setdefault("beneficiarios", []).append(novo)
        _atomic_write(data)

    # Fora do lock — invalidar caches downstream
    invalidate_caches()

    return deepcopy(novo)
