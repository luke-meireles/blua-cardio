"""
Run with:  python app.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path  # FIX 8.5: pages_folder absoluto

# uuid agora é importado localmente em _inicializar_session_data — antes era
# usado no data literal do dcc.Store(session-data), o que causava o Bug 2
# (mesmo uuid pra todos os clientes). Ver comentário detalhado no callback.

import dash
from dash import Dash, Input, Output, State, dcc, html

from utils.storage import ensure_csv, DEFAULT_CSV

ensure_csv(DEFAULT_CSV)

# FIX 8.5: pages_folder relativo falha quando rodando de outro cwd
# (descoberto no Passo 8.5 — "python dashboard/app.py" do cwd da raiz
# resolvia "pages" como ./pages em vez de dashboard/pages).
_PAGES_DIR = Path(__file__).resolve().parent / "pages"

app = Dash(
    __name__,
    use_pages=True,
    pages_folder=str(_PAGES_DIR),  # FIX 8.5: caminho absoluto
    suppress_callback_exceptions=True,
    title="Cardio Monitor | HUD",
    update_title=None,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
    ],
)
server = app.server


# ---- static layout -------------------------------------------------------

def _nav_links():
    ordered = sorted(dash.page_registry.values(),
                     key=lambda p: p.get("order", 99))
    return [
        dcc.Link(
            p["name"].upper(),
            href=p["relative_path"],
            className="hud-nav-link",
            refresh=False,
        )
        for p in ordered
    ]


def _topbar():
    return html.Header(className="hud-topbar", children=[
        html.Div(className="hud-topbar__brand", children=[
            html.Span("C+", className="mark"),
            html.Div([
                html.Div("CardioMonitor"),
                html.Small("Clinical Telemetry // telemetria clínica"),
            ]),
        ]),
        html.Nav(className="hud-topbar__nav", id="hud-nav", children=_nav_links()),
        html.Div(className="hud-topbar__telemetry", children=[
            # C13: dropdown de perfil ativo (atalho de navegação contextual).
            # Posicionado dentro da seção telemetria pra preservar grid CSS
            # upstream (auto/1fr/auto — 3 colunas). 4º elemento direto no
            # Header quebraria o grid.
            html.Div(className="tel", children=[
                html.Span("PERFIL", className="lbl"),
                dcc.Dropdown(
                    id="topbar-perfil-dropdown",
                    options=[
                        {"label": "Gabriel", "value": "GABRIEL"},
                        {"label": "Meu Perfil", "value": "MEU_PERFIL"},
                    ],
                    value="GABRIEL",
                    clearable=False,
                    className="hud-topbar__dropdown",
                    style={"minWidth": "140px", "marginLeft": "8px"},
                ),
            ]),
            html.Div(className="tel", children=[
                html.Span(className="sig-dot"),
                html.Span("LINK", className="lbl"),
                html.Span("ACTIVE", className="val"),
            ]),
            html.Div(className="tel", children=[
                html.Span("UTC", className="lbl"),
                html.Span(id="hud-clock", className="val", children="--:--:--"),
            ]),
            html.Div(className="tel", children=[
                html.Span("DATE", className="lbl"),
                html.Span(id="hud-date", className="val", children="----"),
            ]),
        ]),
    ])


def _footer():
    return html.Footer(className="hud-footer", children=[
        html.Span("CARDIOMONITOR v1.0  //  PPG SLIDING WINDOW N=5  //  THRESHOLDS 100/120 ms"),
        html.Span("HARDWARE: ESP32 + MAX30100"),
    ])


app.layout = html.Div(className="app-shell", children=[
    dcc.Location(id="hud-url"),
    dcc.Interval(id="hud-clock-tick", interval=1000, n_intervals=0),
    # CHAT INTEGRATION + bug fix demo pública (3 bugs encadeados):
    #
    # Bug 1: storage_type default era "memory" — zerava UI ao F5/fechar aba.
    #        Fix: storage_type="local" sobrevive entre sessões do mesmo browser.
    #
    # Bug 2 (CRÍTICO): str(uuid.uuid4()) no data literal era avaliado UMA vez
    #        no import do módulo. TODOS os clientes conectados ao servidor
    #        recebiam o MESMO thread_id, causando cross-talk no MemorySaver
    #        do LangGraph (conversa de um usuário vazava pra outro).
    #        Fix: data=None inicial + callback _inicializar_session_data que
    #        gera uuid único por cliente na primeira navegação. Como
    #        storage_type="local" é per-browser, cada cliente tem seu thread.
    #
    # Bug 3: MemorySaver in-process compartilhado por todos (server-side).
    #        Não bloqueia demo (Bug 2 fixado isola por thread_id). Documentado
    #        em PENDENCIAS_POS_INTEGRACAO.md (Out.5) — produção real precisa
    #        de SqliteSaver ou Redis-backed checkpoint.
    dcc.Store(id="session-data", storage_type="local", data=None),
    # C13: perfil ativo (atalho de navegação contextual entre Gabriel e Meu Perfil)
    # storage_type="session" (não "local") — zera ao fechar aba pra evitar
    # dessincronização entre dropdown (value="GABRIEL" hardcoded) e Store
    # persistido com valor de sessão anterior. Telemetria (/monitor, /analise)
    # NÃO consome este Store — upstream usa dataset Azure Blob único.
    dcc.Store(id="perfil-ativo", data={"id": "GABRIEL"}, storage_type="session"),
    # J.1.b — trigger pra forçar reload de /meu-perfil após criar/editar perfil.
    # O dcc.Location não re-renderiza quando pathname retornado é igual ao atual
    # (ex: estamos em /meu-perfil e callback retorna /meu-perfil). Workaround:
    # callback escreve timestamp aqui, clientside callback em meu_perfil.py
    # detecta mudança e chama window.location.reload().
    dcc.Store(id="meu-perfil-refresh", data=None),
    html.Div(id="meu-perfil-reload-dummy", style={"display": "none"}),
    # CHAT INTEGRATION: audio element global pra alerts do chatbot
    html.Audio(id="audio-alert", src="/assets/alert.wav",
               className="blua-audio-alert", autoPlay=False),
    _topbar(),
    html.Main(dash.page_container, className="hud-page"),
    _footer(),
])


# ---- clock / nav active-state callbacks ---------------------------------

@app.callback(
    Output("hud-clock", "children"),
    Output("hud-date", "children"),
    Input("hud-clock-tick", "n_intervals"),
)
def _tick(_n):
    now = datetime.now(timezone.utc)
    return now.strftime("%H:%M:%S"), now.strftime("%Y-%m-%d")


@app.callback(
    Output("hud-nav", "children"),
    Input("hud-url", "pathname"),
)
def _nav_active(pathname):
    ordered = sorted(dash.page_registry.values(),
                     key=lambda p: p.get("order", 99))
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


# C13: dropdown de perfil ativo (atalho de navegação contextual).
# Atualiza dcc.Store(perfil-ativo) E navega pra rota do prontuário escolhido.
# Não filtra telemetria — upstream usa dataset Azure Blob único sem coluna
# patient (decisão tomada em H.A.3 após investigação).
@app.callback(
    Output("perfil-ativo", "data"),
    Output("hud-url", "pathname", allow_duplicate=True),
    Input("topbar-perfil-dropdown", "value"),
    prevent_initial_call=True,
)
def _trocar_perfil_ativo(perfil_id):
    if not perfil_id:
        return dash.no_update, dash.no_update
    rota = "/gabriel" if perfil_id == "GABRIEL" else "/meu-perfil"
    return {"id": perfil_id}, rota


# J.1.b fix-up (smoke final): label dinâmico do dropdown topbar REMOVIDO.
# Bug observado: callback que outputava topbar-perfil-dropdown.options a cada
# mudança de hud-url.pathname disparava re-render do react-select v5 do Dash 4,
# que resetava o value pro primeiro option (GABRIEL). Reset disparava
# _trocar_perfil_ativo que navegava pra /gabriel — clicar MONITOR ou ANALISE
# voltava pra /gabriel.
# Trade-off: label dropdown fica estático "Meu Perfil" (sem mostrar primeiro
# nome do usuário). Estética sacrificada em troca de navegação correta.
# Documentado em PENDENCIAS_POS_INTEGRACAO.md como pendência menor pós-J.


# Sync URL → dropdown value. Diferente da regressão J.1.4 (que mexia em options
# causando re-render react-select). Aqui só atualizamos value com dash.no_update
# guard pra evitar ping-pong com _trocar_perfil_ativo.
@app.callback(
    Output("topbar-perfil-dropdown", "value"),
    Input("hud-url", "pathname"),
    State("topbar-perfil-dropdown", "value"),
    prevent_initial_call=False,
)
def _sync_dropdown_to_url(pathname, current_value):
    """URL → dropdown. dash.no_update quando value já bate evita loop."""
    if pathname == "/meu-perfil" and current_value != "MEU_PERFIL":
        return "MEU_PERFIL"
    if pathname == "/gabriel" and current_value != "GABRIEL":
        return "GABRIEL"
    return dash.no_update


# Bug fix demo pública: gera thread_id único por cliente.
# Como session-data tem storage_type="local" (per-browser), cada cliente
# chama esse callback na primeira navegação e recebe um thread_id próprio.
# Evita cross-talk no MemorySaver server-side do LangGraph (todos os clientes
# compartilhavam o mesmo uuid fixo gerado no import time do módulo).
#
# allow_duplicate=True porque processar_mensagem em chat.py também escreve
# em session-data. prevent_initial_call="initial_duplicate" permite disparar
# na carga inicial sem conflitar com o validator de duplicates do Dash.
@app.callback(
    Output("session-data", "data", allow_duplicate=True),
    Input("hud-url", "pathname"),
    State("session-data", "data"),
    prevent_initial_call="initial_duplicate",
)
def _inicializar_session_data(pathname, current):
    """Inicializa session-data com thread_id único por cliente.

    Idempotente: se já existe thread_id no Store, retorna no_update.
    Dispara em qualquer mudança de pathname E na carga inicial
    (initial_duplicate). Garante que cada browser tem thread_id próprio.
    """
    import uuid as _uuid
    if (current is None
            or not isinstance(current, dict)
            or not current.get("thread_id")):
        return {
            "thread_id": str(_uuid.uuid4()),
            "mensagens": [],
            "flags_safety_anteriores": [],
            "ultimo_estado": None,
        }
    return dash.no_update


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
