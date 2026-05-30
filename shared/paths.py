"""
Caminhos canônicos para os dois sistemas.

Ponto único de verdade. Se você mover os arquivos de dados, atualize APENAS
aqui — todos os outros módulos importam destes constantes.

Layout esperado depois da integração ArrhythmiaMonitor (Fase I.fix):

    blua-cardio/
      dashboard/     # Dash multi-pages upstream (home, monitor, analise, chat, ...)
        data/                       # CSVs de telemetria (canônico do dashboard upstream)
          cardiac_data.csv          # gravado pelo /monitor em tempo real
          gabriel_data.csv          # dataset de referência do dashboard
      src/           # lógica do chatbot (LangGraph, tools, RAG)
      shared/        # esta pasta — ponte
      data/                         # dados não-telemetria do chatbot
        consultas/                  # registros de atendimentos (R3)
        mocks/
          perfis_clinicos.json      # registro de pacientes (extensível)
          wearable.json
          ...

Estrutura dual de `data/` é intencional:
- `dashboard/data/` segue convenção do upstream (`dashboard/utils/storage.py` com
  PROJECT_ROOT=parent.parent resolve pra `dashboard/`). Manter aqui evita patch
  no upstream e alinha com sua filosofia ("Cenário 3 — upstream canônico").
- `data/` (raiz) mantém artefatos do chatbot (mocks JSON, consultas). Não há
  conflito porque os dois sub-sistemas usam paths distintos.
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
# I.fix: CSVs de telemetria vivem em dashboard/data/ pra alinhar com
# dashboard/utils/storage.py upstream (PROJECT_ROOT=parent.parent).
# Mocks JSON e consultas continuam em DATA_DIR.
DASHBOARD_DATA_DIR: Path = PROJECT_ROOT / "dashboard" / "data"

# Registro de beneficiários — origem: chatbot (perfis_clinicos.json)
PROFILES_JSON: Path = DATA_DIR / "mocks" / "perfis_clinicos.json"

# Telemetria PPG ao vivo — origem: dashboard (cardiac_data.csv)
# Override via BLUA_TELEMETRY_CSV permite apontar pra outro arquivo
# (ex.: ambiente de teste, integração futura com Azure Blob mount).
TELEMETRY_CSV: Path = Path(
    os.environ.get(
        "BLUA_TELEMETRY_CSV",
        str(DASHBOARD_DATA_DIR / "cardiac_data.csv"),
    )
)

# Dataset de referência do dashboard (200 batimentos do paciente "Gabriel")
# Override via BLUA_GABRIEL_CSV — análogo a BLUA_TELEMETRY_CSV.
GABRIEL_CSV: Path = Path(
    os.environ.get(
        "BLUA_GABRIEL_CSV",
        str(DASHBOARD_DATA_DIR / "gabriel_data.csv"),
    )
)
