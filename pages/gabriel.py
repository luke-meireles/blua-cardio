"""Gabriel patient dashboard - renders the reference dataset."""

from __future__ import annotations

from urllib.parse import quote

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, dash_table

from utils.analysis import (
    status_color, status_label_pt, bpm_zone, bpm_zone_color,
)
from utils.storage import GABRIEL_CSV, load_csv
from utils.theme import (
    hud_panel, telemetry_tile, status_chip, plotly_layout, style_axes,
    PRIMARY_BLUE, ACCENT_CYAN, SUCCESS, DANGER, WARNING,
)

dash.register_page(__name__, path="/gabriel", name="Gabriel", order=3)


def layout():
    if not GABRIEL_CSV.exists():
        return html.Div([
            html.Section(className="hud-hero", children=[
                html.Span("MOD // 03  GABRIEL", className="hud-hero__tag"),
                html.H1("Prontuario - Gabriel"),
                html.P("Dataset de referencia PPG - 200 batimentos MAX30102"),
            ]),
            html.Div(className="hud-alert", children=[
                html.Strong("[ ERRO ]"),
                html.Span(" gabriel_data.csv nao encontrado em /data. "
                          "Regenere o dataset."),
            ]),
        ])

    df = load_csv(GABRIEL_CSV)

    reg = int((df["status"] == "regular").sum())
    irr = int((df["status"] == "irregular").sum())
    att = int((df["status"] == "atencao").sum())
    duration_s = float(df["timestamp_s"].max() - df["timestamp_s"].min())
    overall = ("irregular" if irr > reg * 0.25 else
               "atencao" if irr > 0 else "regular")

    patient_card = html.Div(className="hud-patient", children=[
        html.Div("G", className="hud-patient__avatar"),
        html.Div([
            html.Div("GABRIEL", className="hud-patient__name"),
            html.Div([
                "Paciente  //  sensor MAX30102  //  ",
                html.Code(f"{len(df)} batimentos em {duration_s:.0f} s",
                          style={"color": "var(--hud-blue-dark)"}),
            ], className="hud-patient__meta"),
        ]),
        status_chip(overall, "Ritmo " + status_label_pt(overall).lower()),
    ])

    bpm_mean = df["bpm"].mean()

    kpis = html.Div(className="grid grid-5", children=[
        telemetry_tile("BPM medio", f"{bpm_mean:.1f}", unit="bpm",
                       sub=bpm_zone(bpm_mean),
                       accent=bpm_zone_color(bpm_mean)),
        telemetry_tile("BPM min / max",
                       f"{df['bpm'].min():.0f} / {df['bpm'].max():.0f}",
                       sub="amplitude total", accent=PRIMARY_BLUE),
        telemetry_tile("IBI medio",
                       f"{df['ibi_ms'].mean():.0f}", unit="ms",
                       sub=f"sd {df['ibi_ms'].std():.0f} ms",
                       accent=ACCENT_CYAN),
        telemetry_tile("Episodios irregulares", str(irr),
                       sub=f"{irr/len(df)*100:.1f}% dos batimentos",
                       accent=DANGER if irr else SUCCESS),
        telemetry_tile("Batimentos anormais (total)",
                       str(int(df["bat_anormais"].sum())),
                       sub="somatorio da janela deslizante",
                       accent=WARNING),
    ])

    # BPM timeline
    bpm_fig = go.Figure(layout=plotly_layout(340))
    style_axes(bpm_fig, "Tempo (s)", "BPM")
    bpm_fig.add_hrect(y0=60, y1=100, fillcolor=SUCCESS, opacity=0.06, line_width=0)
    bpm_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["bpm"], mode="lines",
        line=dict(color=PRIMARY_BLUE, width=1.6), name="BPM",
        hovertemplate="t=%{x:.1f}s<br>BPM=%{y:.1f}<extra></extra>",
    ))
    for s, color in [("regular", SUCCESS), ("atencao", WARNING),
                     ("irregular", DANGER)]:
        sub = df[df["status"] == s]
        if not sub.empty:
            bpm_fig.add_trace(go.Scatter(
                x=sub["timestamp_s"], y=sub["bpm"], mode="markers",
                marker=dict(color=color, size=6,
                            line=dict(color="#FFFFFF", width=1)),
                name=status_label_pt(s),
            ))

    # IBI figure
    ibi_fig = go.Figure(layout=plotly_layout(320))
    style_axes(ibi_fig, "Tempo (s)", "ms")
    ibi_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["ibi_ms"], mode="lines",
        line=dict(color=ACCENT_CYAN, width=1.6), name="IBI"))
    ibi_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["media_ibi"], mode="lines",
        line=dict(color=PRIMARY_BLUE, width=1.4, dash="dot"),
        name="Media (janela 5)"))

    # desvio + abnormal bars
    stab_fig = go.Figure(layout=plotly_layout(320))
    style_axes(stab_fig, "Tempo (s)", "Desvio (ms)", y2_title="Anormais")
    stab_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["desvio_medio"], mode="lines",
        line=dict(color=DANGER, width=1.6), name="Desvio medio"))
    stab_fig.add_trace(go.Bar(
        x=df["timestamp_s"], y=df["bat_anormais"], name="Anormais",
        marker_color=ACCENT_CYAN, opacity=0.35, yaxis="y2"))
    stab_fig.add_hline(y=100, line_color=WARNING, line_dash="dash")
    stab_fig.add_hline(y=120, line_color=DANGER, line_dash="dash")

    # bpm histogram by status
    hist = px.histogram(df, x="bpm", nbins=30, color="status",
                        color_discrete_map={
                            "regular": SUCCESS, "atencao": WARNING,
                            "irregular": DANGER})
    hist.update_layout(**plotly_layout(300))
    style_axes(hist, "BPM", "Contagem")

    # box
    box = go.Figure(layout=plotly_layout(300))
    style_axes(box, "", "ms")
    box.add_trace(go.Box(y=df["ibi_ms"], name="IBI (ms)",
                         marker_color=PRIMARY_BLUE, line_color=PRIMARY_BLUE))
    box.add_trace(go.Box(y=df["desvio_medio"], name="Desvio medio",
                         marker_color=DANGER, line_color=DANGER))

    # table
    view = df.copy()
    view["status"] = view["status"].map(status_label_pt)
    if "datetime" in view.columns and pd.api.types.is_datetime64_any_dtype(view["datetime"]):
        view["datetime"] = view["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    view = view.rename(columns={
        "datetime": "Data/hora", "patient": "Paciente",
        "timestamp_s": "t (s)", "ibi_ms": "IBI (ms)", "bpm": "BPM",
        "media_ibi": "Media IBI", "desvio_medio": "Desvio medio",
        "bat_anormais": "Bat. anormais", "status": "Status",
    })
    table = dash_table.DataTable(
        data=view.to_dict("records"),
        columns=[{"name": c, "id": c} for c in view.columns],
        page_size=15,
        style_as_list_view=True,
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "JetBrains Mono, Consolas, monospace",
            "fontSize": "0.78rem", "padding": "6px 10px",
            "border": "1px solid #E3ECF5", "color": "#0B1E34",
        },
        style_header={
            "backgroundColor": "#F3F7FB", "fontWeight": "700",
            "textTransform": "uppercase", "letterSpacing": "0.08em",
            "fontSize": "0.7rem", "color": "#073E82",
            "borderBottom": "2px solid #073E82",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{Status} eq "Regular"'}, "color": SUCCESS},
            {"if": {"filter_query": '{Status} eq "Atencao"'}, "color": "#9A7300"},
            {"if": {"filter_query": '{Status} eq "Irregular"'},
             "color": DANGER, "fontWeight": "700"},
        ],
    )

    csv_href = "data:text/csv;charset=utf-8," + quote(df.to_csv(index=False))

    return html.Div([
        html.Section(className="hud-hero", children=[
            html.Span("MOD // 03  GABRIEL", className="hud-hero__tag"),
            html.H1([
                "Prontuario - Gabriel ",
                html.Span("\u2764", className="hud-heart"),
            ]),
            html.P("200 batimentos PPG registrados pelo sensor MAX30102 "
                   "- dataset de referencia"),
        ]),

        patient_card,
        kpis,

        hud_panel(title="Frequencia cardiaca ao longo da aquisicao",
                  status="TIMELINE", accent=ACCENT_CYAN,
                  children=dcc.Graph(figure=bpm_fig,
                                     config={"displayModeBar": False})),

        html.Div(className="grid grid-2", children=[
            hud_panel(title="Intervalo entre batimentos (IBI)",
                      status="ms",
                      children=dcc.Graph(figure=ibi_fig,
                                         config={"displayModeBar": False})),
            hud_panel(title="Desvio medio e batimentos anormais",
                      status="DESVIO", accent=DANGER,
                      children=dcc.Graph(figure=stab_fig,
                                         config={"displayModeBar": False})),
        ]),

        hud_panel(title="Distribuicoes",
                  status="HIST + BOX",
                  children=html.Div(className="grid grid-2", children=[
                      dcc.Graph(figure=hist,
                                config={"displayModeBar": False}),
                      dcc.Graph(figure=box,
                                config={"displayModeBar": False}),
                  ])),

        hud_panel(
            title="Registros",
            status=f"{len(df)} linhas",
            children=[
                table,
                html.Div(style={"marginTop": "14px"}, children=[
                    html.A("BAIXAR CSV DE GABRIEL", href=csv_href,
                           className="hud-btn hud-btn--ghost",
                           download="gabriel_data.csv"),
                ]),
            ],
        ),
    ])
