"""Real-time cardiac monitor page."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html, dash_table

from utils.email_alert import enviar_alerta
from utils.analysis import status_color, status_label_pt, bpm_zone, STATUS_IRREGULAR
from utils.storage import load_blob
from utils.theme import (
    telemetry_tile, status_chip, hud_panel, plotly_layout, style_axes,
    PRIMARY_BLUE, ACCENT_CYAN, SUCCESS, DANGER, WARNING,
)

dash.register_page(__name__, path="/monitor", name="Monitor", order=1)

# ── Áudio ─────────────────────────────────────────────────────
_ALERT_PATH = Path(__file__).resolve().parent.parent / "assets" / "alert.wav"
_ALERT_B64 = base64.b64encode(_ALERT_PATH.read_bytes()).decode("ascii") \
    if _ALERT_PATH.exists() else ""


def _alert_audio_src(play: bool) -> str:
    if not play or not _ALERT_B64:
        return ""
    return f"data:audio/wav;base64,{_ALERT_B64}#{uuid.uuid4().hex}"


# ── Layout ─────────────────────────────────────────────────────

def _controls():
    return hud_panel(
        title="Controle",
        status="CFG",
        children=html.Div(className="hud-controls", children=[
            html.Div(className="field", children=[
                html.Label("JANELA VISUAL"),
                dcc.Slider(id="mon-window", min=20, max=300, step=10, value=80,
                           marks={20: "20", 80: "80", 150: "150", 300: "300"}),
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
        telemetry_tile("Status", "--", sub="classificacao atual", accent=PRIMARY_BLUE),
    ])


def layout():
    return html.Div([
        html.Section(className="hud-hero", children=[
            html.Span("MOD // 01  MONITOR", className="hud-hero__tag"),
            html.H1([
                "Monitor em tempo real ",
                html.Span("\u2764", className="hud-heart"),
            ]),
            html.P("Leitura em tempo real do Azure Blob Storage — "
                   "classificacao por modelo Random Forest"),
        ]),

        dcc.Store(id="mon-store", storage_type= "session", data={
            "running":    True,
            "records":    [],
            "blob_count": 0,
        }),
        dcc.Interval(id="mon-tick", interval= 1000, n_intervals= 0, disabled= False),
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


# ── Callbacks ──────────────────────────────────────────────────

@callback(
    Output("mon-store", "data"),
    Output("mon-tick", "disabled"),
    Input("mon-tick", "n_intervals"),
    State("mon-store", "data"),
)
def _drive(_ntick, store):
    store = store or {"running": True, "records": [], "blob_count": 0}

    try:
        df = load_blob()
        if df.empty:
            return store, False

        blob_count = store.get("blob_count", 0)
        records    = store.get("records", [])
        novos      = df.iloc[blob_count:]

        for _, row in novos.iterrows():
            records.append({
                "idx":          blob_count,
                "timestamp_s":  float(row["timestamp_s"]),
                "ibi_ms":       float(row["ibi_ms"]),
                "bpm":          float(row["bpm"]),
                "media_ibi":    float(row["media_ibi"]),
                "desvio_medio": float(row["desvio_medio"]),
                "bat_anormais": int(row["bat_anormais"]),
                "status":       str(row["status"]),
            })
            blob_count += 1

        store["records"]    = records
        store["blob_count"] = blob_count

    except Exception as e:
        print(f"[monitor] Erro ao ler Blob: {e}")

    return store, False


@callback(
    Output("mon-metrics",      "children"),
    Output("mon-alert-banner", "children"),
    Output("mon-alert-audio",  "src"),
    Output("mon-bpm-chart",    "figure"),
    Output("mon-ibi-chart",    "figure"),
    Output("mon-recent-table", "children"),
    Output("mon-status-bar",   "children"),
    Input("mon-store", "data"),
    State("mon-window", "value"),
)
def _render(store, max_points):
    store      = store or {}
    records    = store.get("records", [])
    running    = store.get("running", False)
    max_points = int(max_points or 80)

    # ── Métricas ───────────────────────────────────────────────
    if records:
        latest       = records[-1]
        color        = status_color(latest["status"])
        is_irreg     = latest["status"] == STATUS_IRREGULAR
        desvio       = latest["desvio_medio"]
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

    # ── Alerta — 4 ou 5 dos últimos 5 irregulares ─────────────
    alert_banner = None
    alert_src    = dash.no_update

    if len(records) >= 5:
        ultimos_5   = [r["status"] for r in records[-5:]]
        irregulares = ultimos_5.count(STATUS_IRREGULAR)

        if irregulares >= 4:

            # Defensive: enviar_alerta já tem opt-in (BLUA_EMAIL_ALERTS) +
            # try/except interno, mas envolve aqui também pra garantir que
            # qualquer regressão futura no email_alert nunca crashe o callback
            # principal do /monitor. Banner + áudio rodam mesmo se e-mail falhar.
            try:
                enviar_alerta(latest, irregulares)
            except Exception as e:
                print(f"[monitor] enviar_alerta levantou exceção (suprimida): "
                      f"{type(e).__name__}: {e}")

            if len(records) >= 6:
                anteriores = [r["status"] for r in records[-6:-1]]
                if anteriores.count(STATUS_IRREGULAR) < 4:
                    alert_src = _alert_audio_src(True)
            else:
                alert_src = _alert_audio_src(True)

            alert_banner = html.Div(className="hud-alert", children=[
                html.Strong("[ ALERTA ] Arritmia persistente detectada"),
                html.Span(f" // {irregulares}/5 ultimos registros irregulares"
                          " — avaliar paciente"),
            ])

    # ── Gráficos ───────────────────────────────────────────────
    subset = records[-max_points:] if records else []
    df     = pd.DataFrame(subset)

    bpm_fig = go.Figure(layout=plotly_layout(340, showlegend=False))
    style_axes(bpm_fig, "Registro", "BPM")
    if not df.empty:
        bpm_fig.add_hrect(y0=60, y1=100, fillcolor=SUCCESS, opacity=0.06,
                          line_width=0)
        bpm_fig.add_trace(go.Scatter(
            x=df["idx"], y=df["bpm"],
            mode="lines+markers",
            line=dict(color=PRIMARY_BLUE, width=2.4, shape="spline"),
            marker=dict(size=6,
                        color=df["status"].map(status_color),
                        line=dict(color="#FFFFFF", width=1)),
            hovertemplate="reg=%{x}<br>BPM=%{y:.1f}<extra></extra>",
            name="BPM",
        ))

    ibi_fig = go.Figure(layout=plotly_layout(280))
    style_axes(ibi_fig, "Registro", "ms")
    if not df.empty:
        ibi_fig.add_trace(go.Scatter(
            x=df["idx"], y=df["ibi_ms"], mode="lines",
            line=dict(color=ACCENT_CYAN, width=2), name="IBI"))
        ibi_fig.add_trace(go.Scatter(
            x=df["idx"], y=df["desvio_medio"], mode="lines",
            line=dict(color=DANGER, width=1.4, dash="dot"),
            name="Desvio medio"))
        ibi_fig.add_hline(y=100, line=dict(color=WARNING, width=1, dash="dash"))
        ibi_fig.add_hline(y=120, line=dict(color=DANGER, width=1, dash="dash"))

    # ── Tabela recente ─────────────────────────────────────────
    if records:
        recent = pd.DataFrame(records[-12:][::-1])
        recent["status"] = recent["status"].map(status_label_pt)
        recent = recent[["idx", "bpm", "ibi_ms", "media_ibi",
                         "desvio_medio", "bat_anormais", "status"]].rename(
            columns={
                "idx":          "#",
                "bpm":          "BPM",
                "ibi_ms":       "IBI (ms)",
                "media_ibi":    "Media IBI",
                "desvio_medio": "Desvio medio",
                "bat_anormais": "Bat. anormais",
                "status":       "Status",
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

    # ── Status bar ─────────────────────────────────────────────
    run_chip = status_chip("regular" if running else "irregular",
                           "Em execucao" if running else "Parado")
    status_bar = html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "14px"},
        children=[
            html.Span(
                [html.Span("FONTE: ", style={"color": "var(--hud-muted)"}),
                 html.Code("Azure Blob Storage // dataset_ppg.csv")],
                style={"fontFamily": "JetBrains Mono, Consolas, monospace",
                       "fontSize": "0.76rem"},
            ),
        ],
    )

    return metrics, alert_banner, alert_src, bpm_fig, ibi_fig, table, status_bar