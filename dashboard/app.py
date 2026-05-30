"""
Run with:  python app.py
"""

from __future__ import annotations

import uuid  # CHAT INTEGRATION: thread_id para dcc.Store global
from datetime import datetime, timezone
from pathlib import Path  # FIX 8.5: pages_folder absoluto

import dash
from dash import Dash, Input, Output, dcc, html

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
    # CHAT INTEGRATION: estado de sessão do chatbot preservado entre páginas.
    # storage_type default ("memory") — vai zerar ao recarregar a aba.
    # Para sobreviver a refresh, mudar para storage_type="session".
    dcc.Store(id="session-data", data={
        "thread_id": str(uuid.uuid4()),
        "mensagens": [],
        "flags_safety_anteriores": [],
        "ultimo_estado": None,
    }),
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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
