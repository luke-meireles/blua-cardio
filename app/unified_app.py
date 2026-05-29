"""
unified_app.py — entrada Dash única para BluaDiagnostics + CardioMonitor.

Hospeda chatbot e dashboard sob UM servidor Flask, com navegação fluida
entre páginas. Usa Dash use_pages=True — cada página é um módulo separado
auto-registrado.

Layout final no navegador:

    http://localhost:8050/         → /chat (chatbot, página principal)
    http://localhost:8050/monitor  → live PPG monitor (do dashboard)
    http://localhost:8050/analise  → análise histórica (do dashboard)
    http://localhost:8050/pacientes → lista geral (nova, lê do registry)

Estratégia de merge:
1. As páginas do dashboard (pages/home.py, monitor.py, analysis.py)
   já usam dash.register_page — basta apontar pages_folder para ela.
2. O chatbot atual (app/dash_app.py) é convertido em um único arquivo
   pages/chat.py que registra a página /chat. Veja MERGE_GUIDE.md
   passo 4 para o template.

Como rodar:
    python app/unified_app.py
    # ou em produção:
    gunicorn -w 1 -b 0.0.0.0:8050 app.unified_app:server
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Garantir raiz do projeto no path (igual ao dash_app.py original)
_RAIZ = Path(__file__).resolve().parents[1]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# Bootstrap LangSmith etc — best-effort
try:
    from colab_setup import preparar_ambiente
    preparar_ambiente(exigir_chave=False)
except Exception as exc:
    print(f"[unified_app] bootstrap aviso: {exc}")

import dash
from dash import Dash, Input, Output, dcc, html
import dash_bootstrap_components as dbc

from shared.paths import DATA_DIR  # garante que data/ existe
from utils.storage import ensure_csv, DEFAULT_CSV  # do dashboard

# Pré-condições — cria CSV se não existir
ensure_csv(DEFAULT_CSV)

BACKEND_ATUAL = os.getenv("LLM_BACKEND", "dashscope")
MODELO_ATUAL = (
    os.getenv("QWEN_DASHSCOPE_MODEL", "qwen-plus")
    if BACKEND_ATUAL == "dashscope"
    else os.getenv("QWEN_OLLAMA_MODEL", "qwen2.5:14b")
)

# =============================================================================
# Dash app — uma instância, todas as páginas
# =============================================================================

app = Dash(
    __name__,
    use_pages=True,            # <-- chave do merge: páginas auto-registradas
    pages_folder=str(_RAIZ / "pages"),  # path absoluto via _RAIZ (linha 35)
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Blua · CardioMonitor + Diagnostics",
    update_title=None,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
    ],
)
server = app.server  # gunicorn / WSGI


# =============================================================================
# Layout compartilhado: topbar + nav + content slot + footer
# =============================================================================

def _nav_links() -> list:
    """Gera links na ordem definida em cada page module via `order=`."""
    ordered = sorted(
        dash.page_registry.values(),
        key=lambda p: p.get("order", 99),
    )
    return [
        dcc.Link(
            p["name"].upper(),
            href=p["relative_path"],
            className="hud-nav-link",
            refresh=False,
        )
        for p in ordered
    ]


def _topbar() -> html.Header:
    return html.Header(
        className="hud-topbar",
        children=[
            html.Div(
                className="hud-topbar__brand",
                children=[
                    html.Span("B+", className="mark"),
                    html.Div([
                        html.Div("Blua"),
                        html.Small("CardioMonitor + Diagnostics"),
                    ]),
                ],
            ),
            html.Nav(
                className="hud-topbar__nav",
                id="hud-nav",
                children=_nav_links(),
            ),
            html.Div(
                className="hud-topbar__telemetry",
                children=[
                    html.Div(className="tel", children=[
                        html.Span(className="sig-dot"),
                        html.Span("LINK", className="lbl"),
                        html.Span(BACKEND_ATUAL.upper(), className="val"),
                    ]),
                    html.Div(className="tel", children=[
                        html.Span("MODEL", className="lbl"),
                        html.Span(MODELO_ATUAL, className="val"),
                    ]),
                    html.Div(className="tel", children=[
                        html.Span("UTC", className="lbl"),
                        html.Span(id="hud-clock", className="val", children="--:--:--"),
                    ]),
                ],
            ),
        ],
    )


def _footer() -> html.Footer:
    return html.Footer(
        className="hud-footer",
        children=[
            html.Span(
                f"BLUA UNIFIED · backend {BACKEND_ATUAL.upper()} · modelo {MODELO_ATUAL}"
            ),
            html.Span(
                "⚕️ Este sistema não substitui avaliação médica · "
                "Em emergência: SAMU 192"
            ),
        ],
    )


app.layout = html.Div(
    className="app-shell",
    children=[
        dcc.Location(id="hud-url"),
        dcc.Interval(id="hud-clock-tick", interval=1000, n_intervals=0),
        # Session storage global — Passo 8.5 da unificação Dash.
        # storage_type="session" preserva conversa entre páginas e
        # reseta ao fechar a aba (alinha com ArrhythmiaMonitor README §6).
        # Callbacks de pages/chat.py referenciam "session-data" e Dash
        # resolve por ID independente da página ativa.
        dcc.Store(id="session-data", storage_type="session", data={}),
        _topbar(),
        # Page slot — Dash injeta a página ativa aqui
        html.Main(dash.page_container, className="hud-page"),
        _footer(),
    ],
)


# =============================================================================
# Callbacks globais (relógio e estado ativo do nav)
# =============================================================================

@app.callback(
    Output("hud-clock", "children"),
    Input("hud-clock-tick", "n_intervals"),
)
def _tick(_n: int) -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


@app.callback(
    Output("hud-nav", "children"),
    Input("hud-url", "pathname"),
)
def _nav_active(pathname: str) -> list:
    ordered = sorted(
        dash.page_registry.values(),
        key=lambda p: p.get("order", 99),
    )
    links = []
    for p in ordered:
        href = p["relative_path"]
        is_active = (pathname or "/") == href
        css_class = "hud-nav-link active" if is_active else "hud-nav-link"
        links.append(dcc.Link(
            p["name"].upper(),
            href=href,
            className=css_class,
            refresh=False,
        ))
    return links


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    print(f"[unified_app] Iniciando em http://localhost:8050")
    print(f"[unified_app] Backend: {BACKEND_ATUAL} | Modelo: {MODELO_ATUAL}")
    print(f"[unified_app] Paginas registradas:")
    for p in sorted(dash.page_registry.values(), key=lambda x: x.get("order", 99)):
        print(f"  {p['relative_path']:20s} -> {p['module']}")
    app.run(debug=False, host="0.0.0.0", port=8050)
