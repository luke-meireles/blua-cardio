"""Real-time cardiac monitor page."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path
from statistics import mean
from typing import Optional

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html
from dash import dash_table

from utils.analysis import (
    ABNORMAL_BEAT_MS, WINDOW_N, BeatRecord, classify_status, status_color,
    status_label_pt, bpm_zone, STATUS_IRREGULAR,
)
from utils.serial_reader import SerialConfig, SerialReader
from utils.storage import (
    DEFAULT_CSV, GABRIEL_CSV, append_beat, ensure_csv, load_csv,
)
from utils.theme import (
    telemetry_tile, status_chip, hud_panel, plotly_layout, style_axes,
    PRIMARY_BLUE, ACCENT_CYAN, SUCCESS, DANGER, WARNING,
)

dash.register_page(__name__, path="/monitor", name="Monitor", order=1)


# ---- singleton for the background serial reader -------------------------

_SERIAL: Optional[SerialReader] = None


def _serial_start(port: str, baud: int) -> Optional[str]:
    global _SERIAL
    if _SERIAL is not None and _SERIAL.connected:
        return None
    _SERIAL = SerialReader(SerialConfig(port=port, baudrate=int(baud)))
    _SERIAL.start()
    return None


def _serial_stop() -> None:
    global _SERIAL
    if _SERIAL is not None:
        _SERIAL.stop()
    _SERIAL = None


def _serial_drain() -> list[dict]:
    if _SERIAL is None:
        return []
    return _SERIAL.drain()


def _serial_error() -> Optional[str]:
    return _SERIAL.last_error if _SERIAL is not None else None


# ---- audio alert (base64-encoded wav) -----------------------------------

_ALERT_PATH = Path(__file__).resolve().parent.parent / "assets" / "alert.wav"
_ALERT_B64 = base64.b64encode(_ALERT_PATH.read_bytes()).decode("ascii") \
    if _ALERT_PATH.exists() else ""


def _alert_audio_src(play: bool) -> str:
    if not play or not _ALERT_B64:
        return ""
    # cache-busting id forces the browser to replay
    return f"data:audio/wav;base64,{_ALERT_B64}#{uuid.uuid4().hex}"


# ---- pure beat math (stateless, used per tick) --------------------------

def _compute_record(prev_records: list[dict], new_ibi_ms: float,
                    prev_t_s: float) -> dict:
    """Compute a BeatRecord-like dict from prior records + a new IBI."""
    window = [r["ibi_ms"] for r in prev_records[-(WINDOW_N - 1):]] + [new_ibi_ms]
    media_ibi = mean(window)
    desvio = mean(abs(v - media_ibi) for v in window)
    bat_anormais = sum(1 for v in window if abs(v - media_ibi) > ABNORMAL_BEAT_MS)
    status = classify_status(desvio)
    bpm = 60000.0 / new_ibi_ms
    t_s = round(prev_t_s + new_ibi_ms / 1000.0, 3) if prev_records else 0.0
    return {
        "timestamp_s": t_s,
        "ibi_ms": round(new_ibi_ms, 2),
        "bpm": round(bpm, 1),
        "media_ibi": round(media_ibi, 2),
        "desvio_medio": round(desvio, 2),
        "bat_anormais": int(bat_anormais),
        "status": status,
    }


# ---- layout -------------------------------------------------------------

def _controls():
    return hud_panel(
        title="Controle",
        status="CFG",
        children=html.Div(className="hud-controls", children=[
            html.Div(className="field hud-radio", children=[
                html.Label("ORIGEM"),
                dcc.RadioItems(
                    id="mon-source",
                    options=[
                        {"label": "Simulacao", "value": "sim"},
                        {"label": "ESP32 (serial)", "value": "esp32"},
                    ],
                    value="sim",
                    inline=True,
                ),
            ]),
            html.Div(className="field", children=[
                html.Label("PORTA"),
                dcc.Input(id="mon-port", type="text", value="COM3",
                          disabled=True, style={"width": "120px"}),
            ]),
            html.Div(className="field", children=[
                html.Label("BAUDRATE"),
                dcc.Input(id="mon-baud", type="number", value=115200,
                          disabled=True, style={"width": "120px"}),
            ]),
            html.Div(className="field", children=[
                html.Label("VELOCIDADE"),
                dcc.Slider(id="mon-speed", min=0.5, max=5.0, step=0.5, value=2.0,
                           marks={1: "1x", 2: "2x", 3: "3x", 5: "5x"}),
            ]),
            html.Div(className="field", children=[
                html.Label("JANELA"),
                dcc.Slider(id="mon-window", min=20, max=300, step=10, value=80,
                           marks={20: "20", 80: "80", 150: "150", 300: "300"}),
            ]),
            html.Div(className="field hud-check", children=[
                html.Label("CSV"),
                dcc.Checklist(
                    id="mon-autosave",
                    options=[{"label": "Gravar", "value": "on"}],
                    value=["on"],
                ),
            ]),
            html.Div(className="field", style={"flexDirection": "row",
                                               "gap": "8px", "alignItems": "flex-end"},
                     children=[
                html.Button("INICIAR", id="mon-start", n_clicks=0,
                            className="hud-btn"),
                html.Button("PARAR", id="mon-stop", n_clicks=0,
                            className="hud-btn hud-btn--stop"),
                html.Button("ZERAR", id="mon-reset", n_clicks=0,
                            className="hud-btn hud-btn--ghost"),
            ]),
        ]),
    )


def _metric_placeholders():
    return html.Div(id="mon-metrics", className="grid grid-5", children=[
        telemetry_tile("Frequencia cardiaca", "--", unit="bpm",
                       sub="aguardando dados...", accent=PRIMARY_BLUE),
        telemetry_tile("IBI atual", "--", unit="ms",
                       sub="intervalo entre batimentos", accent=PRIMARY_BLUE),
        telemetry_tile("Media IBI (N=5)", "--", unit="ms",
                       sub="janela deslizante", accent=ACCENT_CYAN),
        telemetry_tile("Desvio medio", "--", unit="ms",
                       sub="limiares 100 / 120", accent=SUCCESS),
        telemetry_tile("Status", "--",
                       sub="classificacao atual", accent=PRIMARY_BLUE),
    ])


def layout():
    return html.Div([
        html.Section(className="hud-hero", children=[
            html.Span("MOD // 01  MONITOR", className="hud-hero__tag"),
            html.H1([
                "Monitor em tempo real ",
                html.Span("\u2764", className="hud-heart"),
            ]),
            html.P("Streaming do sensor MAX30100 via ESP32 - classificacao "
                   "instantanea por janela deslizante N=5"),
        ]),

        # persistent state
        dcc.Store(id="mon-store", data={
            "running": False,
            "records": [],
            "sim_idx": 0,
        }),
        dcc.Interval(id="mon-tick", interval=600, n_intervals=0, disabled=True),
        html.Audio(id="mon-alert-audio", src="", autoPlay=True,
                   style={"display": "none"}),

        _controls(),

        html.Div(id="mon-alert-banner"),

        _metric_placeholders(),

        hud_panel(
            title="BPM ao vivo",
            status="TELEMETRY // LIVE",
            accent=ACCENT_CYAN,
            children=dcc.Graph(id="mon-bpm-chart",
                               config={"displayModeBar": False},
                               figure=go.Figure(layout=plotly_layout(340))),
        ),

        hud_panel(
            title="IBI e desvio medio",
            status="ms",
            children=dcc.Graph(id="mon-ibi-chart",
                               config={"displayModeBar": False},
                               figure=go.Figure(layout=plotly_layout(280))),
        ),

        hud_panel(
            title="Ultimos batimentos",
            status="QUEUE",
            children=html.Div(id="mon-recent-table"),
        ),

        html.Div(id="mon-status-bar", style={"marginTop": "12px"}),
    ])


# ---- callbacks ----------------------------------------------------------

@callback(
    Output("mon-port", "disabled"),
    Output("mon-baud", "disabled"),
    Input("mon-source", "value"),
)
def _toggle_serial_fields(source):
    is_esp = source == "esp32"
    return (not is_esp), (not is_esp)


@callback(
    Output("mon-store", "data"),
    Output("mon-tick", "disabled"),
    Input("mon-start", "n_clicks"),
    Input("mon-stop", "n_clicks"),
    Input("mon-reset", "n_clicks"),
    Input("mon-tick", "n_intervals"),
    State("mon-source", "value"),
    State("mon-port", "value"),
    State("mon-baud", "value"),
    State("mon-speed", "value"),
    State("mon-autosave", "value"),
    State("mon-store", "data"),
    prevent_initial_call=True,
)
def _drive(_nstart, _nstop, _nreset, _ntick,
           source, port, baud, speed, autosave_v, store):
    trigger = ctx.triggered_id
    store = store or {"running": False, "records": [], "sim_idx": 0}
    autosave = "on" in (autosave_v or [])

    if trigger == "mon-start":
        store["running"] = True
        if source == "esp32":
            _serial_start(port or "COM3", int(baud or 115200))
        return store, False

    if trigger == "mon-stop":
        store["running"] = False
        _serial_stop()
        return store, True

    if trigger == "mon-reset":
        _serial_stop()
        return {"running": False, "records": [], "sim_idx": 0}, True

    # tick: ingest one or more beats
    if not store.get("running"):
        return store, True

    records = store.get("records", [])
    prev_t = records[-1]["timestamp_s"] if records else 0.0

    if source == "sim":
        if not GABRIEL_CSV.exists():
            store["running"] = False
            return store, True
        df = load_csv(GABRIEL_CSV)
        beats_per_tick = max(1, int(round(speed or 1.0)))
        for _ in range(beats_per_tick):
            if store["sim_idx"] >= len(df):
                store["running"] = False
                break
            row = df.iloc[store["sim_idx"]]
            rec = _compute_record(records, float(row["ibi_ms"]), prev_t)
            records.append(rec)
            prev_t = rec["timestamp_s"]
            store["sim_idx"] += 1
            if autosave:
                ensure_csv(DEFAULT_CSV)
                br = BeatRecord(**rec)
                append_beat(br, patient="live-sim", path=DEFAULT_CSV)
    else:
        err = _serial_error()
        if err:
            store["running"] = False
            _serial_stop()
            return store, True
        for payload in _serial_drain():
            ibi = payload.get("ibi")
            bpm_val = payload.get("bpm")
            if ibi is None and bpm_val:
                ibi = 60000.0 / float(bpm_val)
            if not ibi:
                continue
            rec = _compute_record(records, float(ibi), prev_t)
            records.append(rec)
            prev_t = rec["timestamp_s"]
            if autosave:
                ensure_csv(DEFAULT_CSV)
                append_beat(BeatRecord(**rec), patient="live-esp32",
                            path=DEFAULT_CSV)

    store["records"] = records
    return store, not store["running"]


@callback(
    Output("mon-metrics", "children"),
    Output("mon-alert-banner", "children"),
    Output("mon-alert-audio", "src"),
    Output("mon-bpm-chart", "figure"),
    Output("mon-ibi-chart", "figure"),
    Output("mon-recent-table", "children"),
    Output("mon-status-bar", "children"),
    Input("mon-store", "data"),
    State("mon-window", "value"),
)
def _render(store, max_points):
    store = store or {}
    records = store.get("records", [])
    running = store.get("running", False)
    max_points = int(max_points or 80)

    # ---- metrics row ----
    if records:
        latest = records[-1]
        color = status_color(latest["status"])
        is_irreg = latest["status"] == STATUS_IRREGULAR
        desvio = latest["desvio_medio"]
        desvio_accent = (SUCCESS if desvio < 100 else
                         WARNING if desvio <= 120 else DANGER)
        metrics = [
            telemetry_tile("Frequencia cardiaca",
                           f"{latest['bpm']:.0f}", unit="bpm",
                           sub=bpm_zone(latest["bpm"]),
                           accent=color, highlight=is_irreg),
            telemetry_tile("IBI atual",
                           f"{latest['ibi_ms']:.0f}", unit="ms",
                           sub="intervalo entre batimentos",
                           accent=PRIMARY_BLUE),
            telemetry_tile("Media IBI (N=5)",
                           f"{latest['media_ibi']:.0f}", unit="ms",
                           sub="janela deslizante",
                           accent=ACCENT_CYAN),
            telemetry_tile("Desvio medio",
                           f"{latest['desvio_medio']:.0f}", unit="ms",
                           sub="limiares 100 / 120 ms",
                           accent=desvio_accent),
            html.Div(
                className="hud-tile",
                style={"--tile-accent": color},
                children=[
                    html.Div(className="hud-tile__bar"),
                    html.Div("STATUS", className="hud-tile__label"),
                    html.Div(style={"marginTop": "6px"}, children=[
                        status_chip(latest["status"],
                                    status_label_pt(latest["status"])),
                    ]),
                    html.Div(
                        f"Batimentos anormais na janela: {latest['bat_anormais']}",
                        className="hud-tile__sub"),
                ],
            ),
        ]
    else:
        metrics = [
            telemetry_tile("Frequencia cardiaca", "--", unit="bpm",
                           sub="aguardando dados...", accent=PRIMARY_BLUE),
            telemetry_tile("IBI atual", "--", unit="ms",
                           sub="intervalo entre batimentos", accent=PRIMARY_BLUE),
            telemetry_tile("Media IBI (N=5)", "--", unit="ms",
                           sub="janela deslizante", accent=ACCENT_CYAN),
            telemetry_tile("Desvio medio", "--", unit="ms",
                           sub="limiares 100 / 120 ms", accent=SUCCESS),
            telemetry_tile("Status", "IDLE",
                           sub="Pressione INICIAR no painel de controle.",
                           accent=PRIMARY_BLUE),
        ]

    # ---- alert banner + audio (fires once on transition into irregular) ----
    alert_banner = None
    alert_src = dash.no_update
    if records and records[-1]["status"] == STATUS_IRREGULAR:
        prev_status = records[-2]["status"] if len(records) >= 2 else ""
        if prev_status != STATUS_IRREGULAR:
            alert_src = _alert_audio_src(True)
        alert_banner = html.Div(className="hud-alert", children=[
            html.Strong("[ ALERTA ] Arritmia detectada"),
            html.Span(" // desvio medio acima de 120 ms - avaliar paciente"),
        ])

    # ---- charts ----
    subset = records[-max_points:] if records else []
    df = pd.DataFrame(subset)

    bpm_fig = go.Figure(layout=plotly_layout(340, showlegend=False))
    style_axes(bpm_fig, "Tempo (s)", "BPM")
    if not df.empty:
        bpm_fig.add_hrect(y0=60, y1=100, fillcolor=SUCCESS, opacity=0.06,
                          line_width=0)
        bpm_fig.add_trace(go.Scatter(
            x=df["timestamp_s"], y=df["bpm"],
            mode="lines+markers",
            line=dict(color=PRIMARY_BLUE, width=2.4, shape="spline"),
            marker=dict(size=6,
                        color=df["status"].map(status_color),
                        line=dict(color="#FFFFFF", width=1)),
            hovertemplate="t=%{x:.1f}s<br>BPM=%{y:.1f}<extra></extra>",
            name="BPM",
        ))

    ibi_fig = go.Figure(layout=plotly_layout(280))
    style_axes(ibi_fig, "Tempo (s)", "ms")
    if not df.empty:
        ibi_fig.add_trace(go.Scatter(
            x=df["timestamp_s"], y=df["ibi_ms"], mode="lines",
            line=dict(color=ACCENT_CYAN, width=2), name="IBI"))
        ibi_fig.add_trace(go.Scatter(
            x=df["timestamp_s"], y=df["desvio_medio"], mode="lines",
            line=dict(color=DANGER, width=1.4, dash="dot"),
            name="Desvio medio"))
        ibi_fig.add_hline(y=100, line=dict(color=WARNING, width=1, dash="dash"))
        ibi_fig.add_hline(y=120, line=dict(color=DANGER, width=1, dash="dash"))

    # ---- recent table ----
    if records:
        recent = pd.DataFrame(records[-12:][::-1])
        recent["status"] = recent["status"].map(status_label_pt)
        recent = recent[["timestamp_s", "bpm", "ibi_ms", "media_ibi",
                         "desvio_medio", "bat_anormais", "status"]].rename(
            columns={
                "timestamp_s": "t (s)", "bpm": "BPM", "ibi_ms": "IBI (ms)",
                "media_ibi": "Media IBI", "desvio_medio": "Desvio medio",
                "bat_anormais": "Bat. anormais", "status": "Status",
            })
        table = dash_table.DataTable(
            data=recent.to_dict("records"),
            columns=[{"name": c, "id": c} for c in recent.columns],
            page_size=12,
            style_as_list_view=True,
            style_cell={
                "fontFamily": "JetBrains Mono, Consolas, monospace",
                "fontSize": "0.8rem",
                "padding": "6px 10px",
                "border": "1px solid #E3ECF5",
                "color": "#0B1E34",
            },
            style_header={
                "backgroundColor": "#F3F7FB",
                "fontWeight": "700",
                "textTransform": "uppercase",
                "letterSpacing": "0.08em",
                "fontSize": "0.7rem",
                "color": "#073E82",
                "borderBottom": "2px solid #073E82",
            },
            style_data_conditional=[
                {"if": {"filter_query": '{Status} eq "Regular"'},
                 "color": SUCCESS},
                {"if": {"filter_query": '{Status} eq "Atencao"'},
                 "color": "#9A7300"},
                {"if": {"filter_query": '{Status} eq "Irregular"'},
                 "color": DANGER, "fontWeight": "700"},
            ],
        )
    else:
        table = html.Div("Nenhum batimento registrado.", className="hud-info")

    # ---- status bar ----
    run_chip = status_chip("regular" if running else "irregular",
                           "Em execucao" if running else "Parado")
    status_bar = html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "14px"},
        children=[
            run_chip,
            html.Span(
                [html.Span("CSV: ", style={"color": "var(--hud-muted)"}),
                 html.Code(str(Path(DEFAULT_CSV)))],
                style={"fontFamily": "JetBrains Mono, Consolas, monospace",
                       "fontSize": "0.76rem"},
            ),
        ],
    )

    return metrics, alert_banner, alert_src, bpm_fig, ibi_fig, table, status_bar
