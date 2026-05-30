"""Historical analysis page - reads from Azure Blob Storage."""

from __future__ import annotations

from urllib.parse import quote

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html
from dash import dash_table

from utils.analysis import status_label_pt, bpm_zone
from utils.storage import load_blob
from utils.theme import (
    hud_panel, telemetry_tile, plotly_layout, style_axes,
    PRIMARY_BLUE, ACCENT_CYAN, SUCCESS, DANGER, WARNING,
)

dash.register_page(__name__, path="/analise", name="Analise", order=2)


def _controls():
    return hud_panel(
        title="Filtros",
        status="CFG",
        children=html.Div(className="hud-controls", children=[
            html.Div(className="field", style={"minWidth": "320px"}, children=[
                html.Label("PERIODO (registros)"),
                dcc.RangeSlider(
                    id="an-range", min=0, max=100, step=1, value=[0, 100],
                    marks=None,
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
            ]),
            html.Div(className="field", style={"flexDirection": "row",
                                               "gap": "8px", "alignItems": "flex-end"},
                     children=[
                html.A("BAIXAR CSV", id="an-download", href="#", target="_blank",
                       className="hud-btn hud-btn--ghost", download="historico.csv"),
            ]),
        ]),
    )


def layout():
    return html.Div([
        html.Section(className="hud-hero", children=[
            html.Span("MOD // 02  ANALISE", className="hud-hero__tag"),
            html.H1("Analise historica"),
            html.P("Historico completo do Azure Blob Storage — "
                   "tendencias, distribuicao e eventos irregulares"),
        ]),

        dcc.Store(id="an-store"),
        dcc.Interval(id="an-init", interval=500, n_intervals=0, max_intervals=1),
        _controls(),
        html.Div(id="an-content"),
    ])


# ── Callbacks ──────────────────────────────────────────────────

@callback(
    Output("an-store", "data"),
    Output("an-range", "max"),
    Output("an-range", "value"),
    Input("an-init", "n_intervals"),
)
def _bootstrap(_):
    df = load_blob()
    if df.empty:
        return None, 100, [0, 100]
    total = len(df)
    return df.to_json(orient="split"), total, [0, total]


@callback(
    Output("an-download", "href"),
    Output("an-content", "children"),
    Input("an-store", "data"),
    Input("an-range", "value"),
)
def _render(store, rng):
    if not store:
        return "#", html.Div(className="hud-info", children=[
            "Carregando dados do Blob Storage...",
        ])
    
    from io import StringIO
    df = pd.read_json(StringIO(store), orient= "split")

    if df.empty:
        return "#", html.Div(className="hud-info", children=["Dataset vazio."])

    df = df.iloc[rng[0]:rng[1]].reset_index(drop=True)
    df["idx"] = df.index

    if df.empty:
        return "#", html.Div(className="hud-info",
                             children=["Nenhum registro no periodo."])

    # download href
    href = "data:text/csv;charset=utf-8," + quote(df.to_csv(index=False))

    total    = len(df)
    reg      = int((df["status"] == "regular").sum())
    att      = int((df["status"] == "atencao").sum())
    irr      = int((df["status"] == "irregular").sum())
    bpm_mean = df["bpm"].mean()
    bpm_min  = df["bpm"].min()
    bpm_max  = df["bpm"].max()
    # ── KPIs ──────────────────────────────────────────────────
    kpis = html.Div(className="grid grid-5", children=[
        telemetry_tile("Batimentos",
                       f"{total:,}".replace(",", "."),
                       sub="registros no periodo", accent=PRIMARY_BLUE),
        telemetry_tile("BPM medio", f"{bpm_mean:.1f}", unit="bpm",
                       sub=f"min {bpm_min:.0f}  /  max {bpm_max:.0f}",
                       accent=ACCENT_CYAN),
        telemetry_tile("Regulares", str(reg),
                       sub=f"{reg/total*100:.1f}% do total", accent=SUCCESS),
        telemetry_tile("Atencao", str(att),
                       sub=f"{att/total*100:.1f}% do total", accent=WARNING),
        telemetry_tile("Irregulares", str(irr),
                       sub=f"{irr/total*100:.1f}% do total", accent=DANGER),
    ])

    # ── Série temporal BPM ────────────────────────────────────
    bpm_fig = go.Figure(layout=plotly_layout(360))
    style_axes(bpm_fig, "Registro", "BPM")
    bpm_fig.add_hrect(y0=60, y1=100, fillcolor=SUCCESS, opacity=0.05, line_width=0)
    bpm_fig.add_trace(go.Scatter(
        x=df["idx"], y=df["bpm"], mode="lines",
        line=dict(color=PRIMARY_BLUE, width=1.6), name="BPM",
        hovertemplate="reg=%{x}<br>BPM=%{y:.1f}<extra></extra>",
    ))
    for s, col in [("regular", SUCCESS), ("atencao", WARNING), ("irregular", DANGER)]:
        sub = df[df["status"] == s]
        if not sub.empty:
            bpm_fig.add_trace(go.Scatter(
                x=sub["idx"], y=sub["bpm"], mode="markers",
                marker=dict(size=6, color=col,
                            line=dict(color="#FFFFFF", width=1)),
                name=status_label_pt(s),
            ))

    # ── Histograma IBI ────────────────────────────────────────
    hist = px.histogram(df, x="ibi_ms", nbins=30,
                        color_discrete_sequence=[PRIMARY_BLUE])
    hist.update_layout(**plotly_layout(330, showlegend=False))
    style_axes(hist, "IBI (ms)", "Contagem")
    hist.add_vline(x=df["ibi_ms"].mean(), line_dash="dash", line_color=DANGER,
                   annotation_text=f"media {df['ibi_ms'].mean():.0f} ms",
                   annotation_position="top right")

    # ── Pizza ─────────────────────────────────────────────────
    pie_df = (df.assign(label=df["status"].map(status_label_pt))
                .groupby("label", as_index=False).size())
    color_map = {"Regular": SUCCESS, "Atencao": WARNING, "Irregular": DANGER}
    pie = go.Figure(go.Pie(
        labels=pie_df["label"], values=pie_df["size"], hole=0.58,
        marker=dict(
            colors=[color_map.get(l, PRIMARY_BLUE) for l in pie_df["label"]],
            line=dict(color="#FFFFFF", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(family="JetBrains Mono, monospace", color="#FFFFFF", size=11),
    ))
    pie.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="#FFFFFF", showlegend=False)
    
    # ── Estabilidade ──────────────────────────────────────────
    stab = go.Figure(layout=plotly_layout(320))
    style_axes(stab, "Registro", "Desvio medio (ms)", y2_title="Bat. anormais")
    stab.add_trace(go.Scatter(
        x=df["idx"], y=df["desvio_medio"], mode="lines",
        line=dict(color=DANGER, width=1.6), name="Desvio medio (ms)"))
    stab.add_trace(go.Bar(
        x=df["idx"], y=df["bat_anormais"], name="Bat. anormais",
        marker_color=ACCENT_CYAN, opacity=0.35, yaxis="y2"))
    stab.add_hline(y=100, line_color=WARNING, line_dash="dash")
    stab.add_hline(y=120, line_color=DANGER, line_dash="dash")

    # ── Zonas BPM ─────────────────────────────────────────────
    ORDEM_ZONAS = [
        "Normal",
        "Bradicardia severa",
        "Bradicardia",
        "Taquicardia severa",
        "Taquicardia moderada",
        "Taquicardia leve"
    ]
    zones = df["bpm"].map(bpm_zone).value_counts().reset_index()
    zones.columns = ["Zona", "Batimentos"]
    zones["Zona"] = pd.Categorical(zones["Zona"], categories= ORDEM_ZONAS, ordered= True)
    zones = zones.sort_values("Zona").reset_index(drop= True)
    zone_colors = {
        "Bradicardia severa": DANGER, "Bradicardia": WARNING,
        "Normal": SUCCESS, "Taquicardia leve": WARNING,
        "Taquicardia moderada": "#EB8034", "Taquicardia severa": DANGER,
    }
    bar = px.bar(zones, x="Zona", y="Batimentos", color="Zona",
                 color_discrete_map=zone_colors)
    bar.update_layout(**plotly_layout(300, showlegend=False))
    style_axes(bar, "", "Batimentos")

    # ── Tabela ────────────────────────────────────────────────
    display = df.tail(400).copy()
    display["status"] = display["status"].map(status_label_pt)
    table = dash_table.DataTable(
        data=display.to_dict("records"),
        columns=[{"name": c, "id": c} for c in display.columns],
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
            {"if": {"filter_query": '{status} eq "Regular"'}, "color": SUCCESS},
            {"if": {"filter_query": '{status} eq "Atencao"'}, "color": "#9A7300"},
            {"if": {"filter_query": '{status} eq "Irregular"'},
             "color": DANGER, "fontWeight": "700"},
        ],
    )

    content = [
        kpis,
        hud_panel(title="Serie temporal de BPM", status="TIMELINE",
                  accent=ACCENT_CYAN,
                  children=dcc.Graph(figure=bpm_fig,
                                     config={"displayModeBar": False})),
        html.Div(className="grid grid-2", children=[
            hud_panel(title="Distribuicao de IBI", status="HISTOGRAMA",
                      children=dcc.Graph(figure=hist,
                                         config={"displayModeBar": False})),
            hud_panel(title="Composicao dos batimentos", status="SHARE",
                      children=dcc.Graph(figure=pie,
                                         config={"displayModeBar": False})),
        ]),
        hud_panel(title="Estabilidade do ritmo", status="DESVIO + ANORMAIS",
                  accent=DANGER,
                  children=dcc.Graph(figure=stab,
                                     config={"displayModeBar": False})),
        hud_panel(title="Zonas clinicas de frequencia", status="BPM",
                  children=dcc.Graph(figure=bar,
                                     config={"displayModeBar": False})),
        hud_panel(title="Registros", status=f"{len(display)} linhas",
                  children=table),
    ]

    return href, content