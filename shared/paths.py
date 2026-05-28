"""
Caminhos canônicos para os dois sistemas.

Ponto único de verdade. Se você mover os arquivos de dados, atualize APENAS
aqui — todos os outros módulos importam destes constantes.

Layout esperado depois do merge:

    unified_blua/
      app/           # entradas Dash (chat, monitor, etc)
      src/           # lógica do chatbot (LangGraph, tools, RAG)
      shared/        # esta pasta — ponte
      data/
        cardiac_data.csv          # gravado pelo /monitor em tempo real
        gabriel_data.csv          # dataset de referência do dashboard
        mocks/
          perfis_clinicos.json    # registro de pacientes (extensível)
          wearable.json
          ...
"""
from __future__ import annotations

import os
from pathlib import Path


def _find_project_root() -> Path:
    """
    Resolve a raiz do projeto procurando pelo diretório `data/`.

    Permite que o módulo funcione independentemente de onde foi instalado:
    - subindo de `shared/paths.py` → `shared/` → raiz
    - mas também respeitando override via env var BLUA_ROOT (útil em testes
      e em deployments com volumes montados).
    """
    override = os.getenv("BLUA_ROOT")
    if override:
        root = Path(override).resolve()
        if not root.exists():
            raise RuntimeError(f"BLUA_ROOT={override} não existe.")
        return root
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT: Path = _find_project_root()
DATA_DIR: Path = PROJECT_ROOT / "data"

# Registro de beneficiários — origem: chatbot (perfis_clinicos.json)
PROFILES_JSON: Path = DATA_DIR / "mocks" / "perfis_clinicos.json"

# Telemetria PPG ao vivo — origem: dashboard (cardiac_data.csv)
TELEMETRY_CSV: Path = DATA_DIR / "cardiac_data.csv"

# Dataset de referência do dashboard (200 batimentos do paciente "Gabriel")
GABRIEL_CSV: Path = DATA_DIR / "gabriel_data.csv"
