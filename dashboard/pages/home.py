"""Home page - overview + KPIs + navigation."""

from __future__ import annotations

import dash
from dash import html, dcc

from utils.storage import load_blob
from utils.theme import (
    telemetry_tile, hud_panel,
    PRIMARY_BLUE, ACCENT_CYAN, SUCCESS, DANGER,
)

dash.register_page(__name__, path="/", name="Home", order=0)


def _snapshot_tiles():
    df = load_blob()

    total = len(df)
    last_bpm = f"{df['bpm'].iloc[-1]:.1f}" if not df.empty else "--"
    irreg = int((df["status"] == "irregular").sum()) if not df.empty else 0
    pct_irreg = f"{(irreg / total * 100):.1f}%" if total > 0 else "--"

    return html.Div(className="grid grid-4", children=[
        telemetry_tile("Total de registros",
                       f"{total:,}".replace(",", "."),
                       sub="Azure Blob Storage", accent=PRIMARY_BLUE),
        telemetry_tile("Ultimo BPM",
                       last_bpm, unit="bpm",
                       sub="ultima amostra registrada", accent=ACCENT_CYAN),
        telemetry_tile("Eventos irregulares",
                       str(irreg),
                       sub=f"{pct_irreg} do historico total",
                       accent=DANGER if irreg else SUCCESS),
        telemetry_tile("Taxa de regularidade",
                       f"{((total - irreg) / total * 100):.1f}%" if total > 0 else "--",
                       sub="registros regulares",
                       accent=SUCCESS),
    ])


def _nav_card(idx: str, title: str, body: str, href: str):
    return dcc.Link(
        href=href,
        className="hud-navcard",
        children=[
            html.Div(idx, className="hud-navcard__idx"),
            html.Div(title, className="hud-navcard__title"),
            html.Div(body, className="hud-navcard__text"),
            html.Div("ABRIR >>", className="hud-navcard__arrow"),
        ],
    )


def layout():
    return html.Div([
        html.Section(className="hud-hero", children=[
            html.Span("SYS // OVERVIEW", className="hud-hero__tag"),
            html.H1([
                "CardioMonitor ",
                html.Span("\u2764", className="hud-heart"),
            ]),
            html.P("Plataforma clinica de monitoramento cardiaco em tempo real"),
        ]),

        hud_panel(
            title="Briefing",
            status="READY",
            children=html.P(
                [
                    "Esta plataforma recebe dados simulados via ",
                    html.Strong("gerador IBI"),
                    " processados pelo ",
                    html.Strong("simulador ESP32"),
                    ", classifica cada batimento como ",
                    html.Strong("Regular"), ", ",
                    html.Strong("Atencao"), " ou ",
                    html.Strong("Irregular"),
                    " atraves de um modelo ",
                    html.Strong("Random Forest"),
                    " hospedado na ",
                    html.Strong("Azure"),
                    ". Os dados sao persistidos no ",
                    html.Strong("Azure Blob Storage"),
                    " e visualizados em tempo real neste dashboard.",
                ],
                style={"margin": 0, "color": "var(--hud-muted)",
                       "lineHeight": "1.55"},
            ),
        ),

        hud_panel(
            title="Telemetria - snapshot",
            status="LIVE",
            accent=ACCENT_CYAN,
            children=_snapshot_tiles(),
        ),

        hud_panel(
            title="Navegacao",
            status="3 MODULOS",
            children=html.Div(className="grid grid-3", children=[
                _nav_card(
                    "MOD // 01",
                    "Monitor em tempo real",
                    "BPM ao vivo via Azure Blob Storage, classificacao por "
                    "modelo Random Forest e alerta em batimentos irregulares.",
                    "/monitor",
                ),
                _nav_card(
                    "MOD // 02",
                    "Analise historica",
                    "Leitura do historico completo do Blob Storage: tendencias "
                    "de BPM, distribuicao de IBI e eventos irregulares.",
                    "/analise",
                ),
                _nav_card(
                    "MOD // 03",
                    "Paciente Gabriel",
                    "Prontuario PPG do paciente Gabriel renderizado "
                    "no formato do dashboard.",
                    "/gabriel",
                ),
            ]),
        ),
    ])