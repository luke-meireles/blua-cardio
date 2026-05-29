"""
HUD theme tokens and reusable Dash UI primitives.

Aesthetic: clinical navy / cyan on near-white, squared corners, corner
brackets on panels, monospaced telemetry numbers. No rounded cards.
"""

from __future__ import annotations

from dash import html

# --- palette ---------------------------------------------------------------
PRIMARY_BLUE = "#0A4DA2"
PRIMARY_BLUE_DARK = "#073E82"
PRIMARY_BLUE_LIGHT = "#1C6DD0"
ACCENT_CYAN = "#00A9E0"
ACCENT_CYAN_DEEP = "#0086B3"
BG_WHITE = "#FFFFFF"
BG_SOFT = "#EEF3F9"
BG_GRID = "#F7FAFD"
TEXT_DARK = "#0B1E34"
TEXT_MUTED = "#54708C"
BORDER = "#C9D6E6"
BORDER_STRONG = "#0B2F5C"
SUCCESS = "#1FAE6F"
WARNING = "#F2B705"
DANGER = "#E53E3E"

PLOT_BG = BG_WHITE
PLOT_GRID = "#E3ECF5"


# --- UI primitives ---------------------------------------------------------

def hud_panel(children, title: str = "", status: str = "", accent: str = PRIMARY_BLUE,
              className: str = "", style: dict | None = None):
    """Squared panel with corner brackets and an optional HUD title bar."""
    header = None
    if title or status:
        header = html.Div(className="hud-panel__header", children=[
            html.Div(className="hud-panel__title", children=[
                html.Span(className="hud-panel__tick", style={"background": accent}),
                html.Span(title, className="hud-panel__title-text"),
            ]),
            html.Span(status, className="hud-panel__status") if status else None,
        ])
    brackets = [
        html.Span(className="hud-corner hud-corner--tl"),
        html.Span(className="hud-corner hud-corner--tr"),
        html.Span(className="hud-corner hud-corner--bl"),
        html.Span(className="hud-corner hud-corner--br"),
    ]
    return html.Div(
        className=f"hud-panel {className}".strip(),
        style=style or {},
        children=[*brackets, header, html.Div(children, className="hud-panel__body")],
    )


def telemetry_tile(label: str, value, unit: str = "", sub: str = "",
                   accent: str = PRIMARY_BLUE, highlight: bool = False):
    """Compact metric tile: label + big monospaced value + optional subtext."""
    return html.Div(
        className="hud-tile" + (" hud-tile--alert" if highlight else ""),
        style={"--tile-accent": accent},
        children=[
            html.Div(className="hud-tile__bar"),
            html.Div(label, className="hud-tile__label"),
            html.Div(className="hud-tile__value-row", children=[
                html.Span(str(value), className="hud-tile__value"),
                html.Span(unit, className="hud-tile__unit") if unit else None,
            ]),
            html.Div(sub, className="hud-tile__sub") if sub else None,
        ],
    )


def status_chip(status: str, label: str):
    cls = {"regular": "ok", "atencao": "warn", "irregular": "bad"}.get(status, "ok")
    return html.Span(className=f"hud-chip hud-chip--{cls}", children=[
        html.Span(className="hud-chip__led"),
        html.Span(label, className="hud-chip__label"),
    ])


_AXIS_STYLE = dict(
    gridcolor=PLOT_GRID, zerolinecolor=PLOT_GRID, linecolor=BORDER,
    showline=True, mirror=False, ticks="outside", tickcolor=BORDER,
    tickfont=dict(family="JetBrains Mono, Consolas, monospace", size=11),
    title_font=dict(size=12, color=TEXT_MUTED),
)


def plotly_layout(height: int = 320, **overrides) -> dict:
    """Shared Plotly layout: squared, monospaced ticks, subtle grid."""
    base = dict(
        height=height,
        margin=dict(l=52, r=20, t=24, b=44),
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="Inter, 'Segoe UI', sans-serif", color=TEXT_DARK, size=12),
        xaxis=dict(_AXIS_STYLE),
        yaxis=dict(_AXIS_STYLE),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=TEXT_MUTED),
        ),
        hoverlabel=dict(bgcolor=BG_WHITE, bordercolor=BORDER_STRONG,
                        font=dict(family="JetBrains Mono, Consolas, monospace",
                                  color=TEXT_DARK, size=11)),
    )
    base.update(overrides)
    return base


def style_axes(fig, x_title: str = "", y_title: str = "",
               y2_title: str = "") -> None:
    """Apply the shared axis chrome to a figure."""
    fig.update_xaxes(title_text=x_title, **_AXIS_STYLE)
    fig.update_yaxes(title_text=y_title, **_AXIS_STYLE)
    if y2_title:
        fig.update_layout(yaxis2=dict(
            title_text=y2_title, overlaying="y", side="right", showgrid=False,
            linecolor=BORDER, showline=True, ticks="outside", tickcolor=BORDER,
            tickfont=dict(family="JetBrains Mono, Consolas, monospace", size=11),
            title_font=dict(size=12, color=TEXT_MUTED),
        ))
