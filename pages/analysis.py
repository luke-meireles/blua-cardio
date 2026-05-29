"""Historical analysis page - reads the auto-saved CSV."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html
from dash import dash_table

from utils.analysis import status_label_pt, bpm_zone
from utils.storage import DEFAULT_CSV, GABRIEL_CSV, clear_csv, load_csv
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
            html.Div(className="field", children=[
                html.Label("ARQUIVO"),
                dcc.Dropdown(
                    id="an-source",
                    options=[
                        {"label": f"Ao vivo  //  {DEFAULT_CSV.name}", "value": "live"},
                        {"label": f"Gabriel  //  {GABRIEL_CSV.name}", "value": "gabriel"},
                    ],
                    value="live", clearable=False,
                    style={"width": "260px"},
                ),
            ]),
            html.Div(className="field", style={"minWidth": "260px"}, children=[
                html.Label("PACIENTES"),
                dcc.Dropdown(id="an-patients", multi=True, placeholder="todos"),
            ]),
            html.Div(className="field", style={"minWidth": "320px"}, children=[
                html.Label("PERIODO"),
                dcc.RangeSlider(id="an-range", min=0, max=1, step=1, value=[0, 1],
                                marks=None, tooltip={"placement": "bottom",
                                                     "always_visible": False}),
            ]),
            html.Div(className="field", style={"flexDirection": "row",
                                               "gap": "8px", "alignItems": "flex-end"},
                     children=[
                html.Button("LIMPAR CSV", id="an-clear", n_clicks=0,
                            className="hud-btn hud-btn--danger"),
                html.A("BAIXAR CSV", id="an-download", href="#", target="_blank",
                       className="hud-btn hud-btn--ghost", download="dados.csv"),
            ]),
            html.Div(id="an-clear-feedback", className="field",
                     style={"color": "var(--hud-success)", "fontSize": "0.8rem",
                            "fontFamily": "JetBrains Mono, monospace"}),
        ]),
    )


def layout():
    return html.Div([
        html.Section(className="hud-hero", children=[
            html.Span("MOD // 02  ANALISE", className="hud-hero__tag"),
            html.H1("Analise historica"),
            html.P("Exploracao dos batimentos gravados automaticamente em CSV "
                   "- tendencias, distribuicao e eventos irregulares"),
        ]),

        # tmin/tmax ISO strings for the period slider
        dcc.Store(id="an-ts-index"),

        _controls(),

        html.Div(id="an-content"),
    ])


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _load(source: str) -> pd.DataFrame:
    path = DEFAULT_CSV if source == "live" else GABRIEL_CSV
    return load_csv(path)


def _filter(df: pd.DataFrame, patients, rng, ts_index) -> pd.DataFrame:
    if df.empty:
        return df
    if patients:
        df = df[df["patient"].isin(patients)]
    if ts_index and rng and "datetime" in df.columns \
            and pd.api.types.is_datetime64_any_dtype(df["datetime"]):
        tmin = pd.to_datetime(ts_index["tmin"])
        tmax = pd.to_datetime(ts_index["tmax"])
        span = (tmax - tmin).total_seconds() or 1
        lo = tmin + pd.to_timedelta(rng[0] / 1000.0 * span, unit="s")
        hi = tmin + pd.to_timedelta(rng[1] / 1000.0 * span, unit="s")
        df = df[(df["datetime"] >= lo) & (df["datetime"] <= hi)]
    return df


# ----------------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------------

@callback(
    Output("an-patients", "options"),
    Output("an-patients", "value"),
    Output("an-range", "min"),
    Output("an-range", "max"),
    Output("an-range", "value"),
    Output("an-range", "marks"),
    Output("an-ts-index", "data"),
    Input("an-source", "value"),
    Input("an-clear", "n_clicks"),
)
def _bootstrap_filters(source, _nclear):
    if ctx.triggered_id == "an-clear" and source == "live":
        clear_csv(DEFAULT_CSV)

    df = _load(source)
    if df.empty:
        return [], [], 0, 1, [0, 1], None, None

    patients = sorted(df["patient"].dropna().unique().tolist())
    options = [{"label": p, "value": p} for p in patients]

    ts_index = None
    rmin, rmax, rvalue, marks = 0, 1000, [0, 1000], None
    if pd.api.types.is_datetime64_any_dtype(df["datetime"]):
        tmin = df["datetime"].min()
        tmax = df["datetime"].max()
        if pd.notna(tmin) and pd.notna(tmax) and tmin != tmax:
            ts_index = {"tmin": tmin.isoformat(), "tmax": tmax.isoformat()}
            rmin, rmax, rvalue = 0, 1000, [0, 1000]
            marks = {0: tmin.strftime("%H:%M"),
                     1000: tmax.strftime("%H:%M")}

    return options, patients, rmin, rmax, rvalue, marks, ts_index


@callback(
    Output("an-clear-feedback", "children"),
    Input("an-clear", "n_clicks"),
    prevent_initial_call=True,
)
def _clear_msg(_n):
    if not _n:
        return ""
    return f"CSV ao vivo limpo - {datetime.now().strftime('%H:%M:%S')}"


@callback(
    Output("an-download", "href"),
    Input("an-source", "value"),
    Input("an-patients", "value"),
    Input("an-range", "value"),
    State("an-ts-index", "data"),
)
def _download_href(source, patients, rng, ts_index):
    df = _filter(_load(source), patients, rng, ts_index)
    if df.empty:
        return "#"
    csv_text = df.to_csv(index=False)
    return "data:text/csv;charset=utf-8," + quote(csv_text)


@callback(
    Output("an-content", "children"),
    Input("an-source", "value"),
    Input("an-patients", "value"),
    Input("an-range", "value"),
    State("an-ts-index", "data"),
)
def _render(source, patients, rng, ts_index):
    df = _load(source)
    df = _filter(df, patients, rng, ts_index)

    if df.empty:
        return html.Div(className="hud-info", children=[
            "Nenhum dado carregado. Rode o ",
            html.Strong("Monitor em tempo real"),
            " para gerar o CSV ao vivo, ou selecione o dataset do paciente Gabriel.",
        ])

    total = len(df)
    reg = int((df["status"] == "regular").sum())
    att = int((df["status"] == "atencao").sum())
    irr = int((df["status"] == "irregular").sum())
    bpm_mean = df["bpm"].mean()
    bpm_min, bpm_max = df["bpm"].min(), df["bpm"].max()

    # KPI row
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

    # timeline
    x_col = "datetime" if pd.api.types.is_datetime64_any_dtype(df["datetime"]) \
        else "timestamp_s"

    bpm_fig = go.Figure(layout=plotly_layout(360))
    style_axes(bpm_fig, "", "BPM")
    bpm_fig.add_hrect(y0=60, y1=100, fillcolor=SUCCESS, opacity=0.05, line_width=0)
    bpm_fig.add_trace(go.Scatter(
        x=df[x_col], y=df["bpm"], mode="lines",
        line=dict(color=PRIMARY_BLUE, width=1.6), name="BPM",
        hovertemplate="%{x}<br>BPM=%{y:.1f}<extra></extra>",
    ))
    for s, col in [("regular", SUCCESS), ("atencao", WARNING),
                   ("irregular", DANGER)]:
        sub = df[df["status"] == s]
        if not sub.empty:
            bpm_fig.add_trace(go.Scatter(
                x=sub[x_col], y=sub["bpm"], mode="markers",
                marker=dict(size=6, color=col, line=dict(color="#FFFFFF", width=1)),
                name=status_label_pt(s),
                hovertemplate="%{x}<br>BPM=%{y:.1f}<extra>"
                              + status_label_pt(s) + "</extra>",
            ))

    # IBI histogram
    hist = px.histogram(df, x="ibi_ms", nbins=30,
                        color_discrete_sequence=[PRIMARY_BLUE])
    hist.update_layout(**plotly_layout(330, showlegend=False))
    style_axes(hist, "IBI (ms)", "Contagem")
    hist.add_vline(x=df["ibi_ms"].mean(), line_dash="dash", line_color=DANGER,
                   annotation_text=f"media {df['ibi_ms'].mean():.0f} ms",
                   annotation_position="top right")

    # pie
    pie_df = (df.assign(label=df["status"].map(status_label_pt))
                .groupby("label", as_index=False).size())
    color_map = {"Regular": SUCCESS, "Atencao": WARNING, "Irregular": DANGER}
    pie = go.Figure(go.Pie(
        labels=pie_df["label"], values=pie_df["size"], hole=0.58,
        marker=dict(colors=[color_map.get(l, PRIMARY_BLUE)
                            for l in pie_df["label"]],
                    line=dict(color="#FFFFFF", width=2)),
        textinfo="label+percent",
        textfont=dict(family="JetBrains Mono, monospace",
                      color="#FFFFFF", size=11),
    ))
    pie.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="#FFFFFF", showlegend=False)

    # stability (desvio + abnormal bar)
    stab = go.Figure(layout=plotly_layout(320))
    style_axes(stab, "", "Desvio medio (ms)", y2_title="Bat. anormais")
    stab.add_trace(go.Scatter(x=df[x_col], y=df["desvio_medio"], mode="lines",
                              line=dict(color=DANGER, width=1.6),
                              name="Desvio medio (ms)"))
    stab.add_trace(go.Bar(x=df[x_col], y=df["bat_anormais"],
                          name="Bat. anormais",
                          marker_color=ACCENT_CYAN, opacity=0.35, yaxis="y2"))
    stab.add_hline(y=100, line_color=WARNING, line_dash="dash")
    stab.add_hline(y=120, line_color=DANGER, line_dash="dash")

    # BPM zones
    zones = df["bpm"].map(bpm_zone).value_counts().reset_index()
    zones.columns = ["Zona", "Batimentos"]
    zone_colors = {
        "Bradicardia severa": DANGER, "Bradicardia": WARNING,
        "Normal": SUCCESS, "Taquicardia leve": WARNING,
        "Taquicardia moderada": "#EB8034", "Taquicardia severa": DANGER,
    }
    bar = px.bar(zones, x="Zona", y="Batimentos", color="Zona",
                 color_discrete_map=zone_colors)
    bar.update_layout(**plotly_layout(300, showlegend=False))
    style_axes(bar, "", "Batimentos")

    # table
    display = df.copy().tail(400)
    display["status"] = display["status"].map(status_label_pt)
    if "datetime" in display.columns and pd.api.types.is_datetime64_any_dtype(display["datetime"]):
        display["datetime"] = display["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
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

    return [
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
