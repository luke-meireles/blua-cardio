"""Página /meu-perfil — prontuário de paciente saudável demonstrativo.

J.1 da Fase J. Espelha gabriel.py em estilo (constantes Python hardcoded
+ layout 9-seções), mas com dados saudáveis pra criar contraste de demo:
- Gabriel: FA paroxística, 3 medicações cont., dataset com irregularidades
- MEU_PERFIL: assintomático, suplemento preventivo, dataset 100% regular

Lê meu_perfil_data.csv (200 batimentos, BPM 65-76, zero anômalos) via
MEU_PERFIL_CSV (integrado em J.2).
"""

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
from utils.storage import MEU_PERFIL_CSV, load_csv
from utils.theme import (
    hud_panel, telemetry_tile, status_chip, plotly_layout, style_axes,
    PRIMARY_BLUE, ACCENT_CYAN, SUCCESS, DANGER, WARNING,
)

dash.register_page(__name__, path="/meu-perfil", name="Meu Perfil", order=4)

# ── Dados mockados do prontuário (perfil saudável demonstrativo) ────────────

MEDICO = {
    "nome": "Dr. Robert Chase",
    "crm": "CRM-SP 178432",
    "especialidade": "Cardiologia Preventiva",
    "initials": "RC",
}

PACIENTE_INFO = {
    "nome": "Carlos Almeida",
    "nascimento": "22/07/1993",
    "idade": 32,
    "sexo": "Masculino",
    "convenio": "Care Plus — Plano Saúde Plena",
    "carteirinha": "CPS-2024-04217",
    "diagnostico_principal": "Avaliação cardiovascular preventiva — sem patologia ativa",
    "diagnosticos_secundarios": [
        "Sem comorbidades cardiometabólicas identificadas",
    ],
    "cha2ds2_va": 0,
    "alergias": "Sem alergias medicamentosas conhecidas",
    "observacoes": (
        "Paciente assintomático em programa de monitoramento cardiovascular "
        "preventivo via sensor PPG MAX30102 integrado ao CardioMonitor. "
        "Perfil de risco baixo — Framingham 10y < 5%. "
        "Sem indicação de farmacoterapia. Recomendação: manutenção de "
        "atividade física aeróbica regular (≥150 min/semana) e dieta "
        "mediterrânea."
    ),
}

PRESCRICAO = [
    {
        "medicamento": "Ômega-3 EPA/DHA 1g",
        "classe": "Suplemento — Ácidos graxos poli-insaturados",
        "posologia": "1 cápsula via oral, 1x ao dia, junto à refeição principal.",
        "duracao": "Uso preventivo contínuo — reavaliar anualmente.",
        "meta": "Manutenção de perfil lipídico favorável. Suporte cardiovascular preventivo.",
        "observacao": (
            "Não há indicação atual de medicação cardiovascular prescrita. "
            "Suplementação opcional baseada em evidências de benefício preventivo. "
            "Reavaliar necessidade anualmente conforme exames de rotina."
        ),
        "cor": SUCCESS,
    },
]

CONSULTAS = [
    {
        "data": "12/03/2025",
        "tipo": "Check-up cardiovascular anual",
        "medico": "Dr. Robert Chase",
        "resumo": (
            "Avaliação cardiovascular preventiva completa. ECG sem alterações. "
            "PA 118×76 mmHg. FC 70 bpm. IMC 23.5. Perfil lipídico dentro da meta "
            "(LDL 92, HDL 58, TG 88). Glicemia jejum 84 mg/dL. Sem indicação "
            "de farmacoterapia. Orientação: manter rotina de exercícios."
        ),
        "status": "realizada",
    },
    {
        "data": "08/05/2026",
        "tipo": "Monitoramento PPG — Aquisição CardioMonitor",
        "medico": "Dr. Robert Chase",
        "resumo": (
            "Sessão de 200 batimentos via MAX30102. Ritmo sinusal estável "
            "(BPM médio 70.2, range 65-75). Zero batimentos anômalos. "
            "Dataset incluído no programa de monitoramento contínuo."
        ),
        "status": "realizada",
    },
    {
        "data": "12/03/2027",
        "tipo": "Check-up cardiovascular anual",
        "medico": "Dr. Robert Chase",
        "resumo": (
            "Reavaliação anual: ECG, perfil lipídico, glicemia, função renal, "
            "atualização do escore de risco cardiovascular. Manter conduta "
            "preventiva se mantida estabilidade."
        ),
        "status": "agendada",
    },
]

# ── Helpers de UI (espelha gabriel.py) ──────────────────────────────────────


def _badge(text: str, color: str, bg: str = "transparent") -> html.Span:
    return html.Span(text, style={
        "display": "inline-block",
        "padding": "2px 10px",
        "borderRadius": "3px",
        "border": f"1px solid {color}",
        "color": color,
        "backgroundColor": bg,
        "fontSize": "0.7rem",
        "fontWeight": "700",
        "letterSpacing": "0.07em",
        "fontFamily": "JetBrains Mono, Consolas, monospace",
        "textTransform": "uppercase",
    })


def _consulta_card(c: dict) -> html.Div:
    is_agendada = c["status"] == "agendada"
    cor = ACCENT_CYAN if is_agendada else "var(--hud-blue-dark)"
    badge_text = "AGENDADA" if is_agendada else "REALIZADA"
    badge_color = ACCENT_CYAN if is_agendada else SUCCESS
    return html.Div(style={
        "borderLeft": f"3px solid {cor}",
        "padding": "12px 16px",
        "marginBottom": "10px",
        "backgroundColor": "rgba(7,62,130,0.04)",
        "borderRadius": "0 4px 4px 0",
    }, children=[
        html.Div(style={"display": "flex", "justifyContent": "space-between",
                        "alignItems": "center", "marginBottom": "4px"}, children=[
            html.Span(f"{c['data']}  //  {c['tipo']}", style={
                "fontFamily": "JetBrains Mono, Consolas, monospace",
                "fontSize": "0.8rem", "fontWeight": "700",
                "color": "var(--hud-blue-dark)",
            }),
            _badge(badge_text, badge_color),
        ]),
        html.P(c["resumo"], style={
            "fontSize": "0.82rem", "color": "#2C3E50",
            "margin": "0", "lineHeight": "1.5",
        }),
        html.Span(c["medico"], style={
            "fontSize": "0.72rem", "color": "#6B7D8F",
            "fontFamily": "JetBrains Mono, Consolas, monospace",
        }),
    ])


def _prescricao_card(p: dict) -> html.Div:
    return html.Div(style={
        "borderLeft": f"4px solid {p['cor']}",
        "padding": "14px 18px",
        "marginBottom": "12px",
        "backgroundColor": "rgba(7,62,130,0.03)",
        "borderRadius": "0 6px 6px 0",
    }, children=[
        html.Div(style={"display": "flex", "justifyContent": "space-between",
                        "alignItems": "flex-start", "marginBottom": "6px"}, children=[
            html.Div([
                html.Span(p["medicamento"], style={
                    "fontFamily": "JetBrains Mono, Consolas, monospace",
                    "fontSize": "0.9rem", "fontWeight": "700",
                    "color": "var(--hud-blue-dark)", "display": "block",
                }),
                html.Span(p["classe"], style={
                    "fontSize": "0.72rem", "color": "#6B7D8F",
                    "fontFamily": "JetBrains Mono, Consolas, monospace",
                }),
            ]),
            _badge("Uso contínuo", p["cor"]),
        ]),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                        "gap": "8px", "marginTop": "8px"}, children=[
            html.Div([
                html.Span("POSOLOGIA", style={"fontSize": "0.65rem",
                          "color": p["cor"], "fontWeight": "700",
                          "fontFamily": "JetBrains Mono, Consolas, monospace",
                          "letterSpacing": "0.08em", "display": "block"}),
                html.Span(p["posologia"], style={"fontSize": "0.8rem",
                          "color": "#2C3E50", "lineHeight": "1.4"}),
            ]),
            html.Div([
                html.Span("META TERAPÊUTICA", style={"fontSize": "0.65rem",
                          "color": p["cor"], "fontWeight": "700",
                          "fontFamily": "JetBrains Mono, Consolas, monospace",
                          "letterSpacing": "0.08em", "display": "block"}),
                html.Span(p["meta"], style={"fontSize": "0.8rem",
                          "color": "#2C3E50", "lineHeight": "1.4"}),
            ]),
        ]),
        html.Div(style={"marginTop": "8px", "padding": "6px 10px",
                        "backgroundColor": f"{p['cor']}11",
                        "borderRadius": "3px", "border": f"1px solid {p['cor']}33"},
                 children=[
            html.Span("ℹ ", style={"color": p["cor"]}),
            html.Span(p["observacao"], style={"fontSize": "0.76rem",
                      "color": "#4A5568", "lineHeight": "1.4"}),
        ]),
    ])


# ── Layout ───────────────────────────────────────────────────────────────────

def layout():
    if not MEU_PERFIL_CSV.exists():
        return html.Div([
            html.Section(className="hud-hero", children=[
                html.Span("MOD // 04  PRONTUÁRIO", className="hud-hero__tag"),
                html.H1("Prontuário — Meu Perfil"),
                html.P("Registro médico eletrônico — Care Plus / CardioMonitor"),
            ]),
            html.Div(className="hud-alert", children=[
                html.Strong("[ ERRO ]"),
                html.Span(" meu_perfil_data.csv não encontrado em "
                          "dashboard/data/. Regenere o dataset."),
            ]),
        ])

    df = load_csv(MEU_PERFIL_CSV)

    reg = int((df["status"] == "regular").sum())
    irr = int((df["status"] == "irregular").sum())
    att = int((df["status"] == "atencao").sum())
    duration_s = float(df["timestamp_s"].max() - df["timestamp_s"].min())
    overall = ("irregular" if irr > reg * 0.25 else
               "atencao" if irr > 0 else "regular")
    bpm_mean = df["bpm"].mean()

    # ── Cabeçalho hero ──────────────────────────────────────────────────────
    hero = html.Section(className="hud-hero", children=[
        html.Span("MOD // 04  PRONTUÁRIO MÉDICO", className="hud-hero__tag"),
        html.H1([
            f"Prontuário — {PACIENTE_INFO['nome']} ",
            html.Span("❤", className="hud-heart"),
        ]),
        html.P("Registro Médico Eletrônico — Care Plus / CardioMonitor  //  "
               "Perfil Cardiometabólico Saudável"),
    ])

    # ── Card do paciente + médico ────────────────────────────────────────────
    initials_paciente = "".join(p[0] for p in PACIENTE_INFO["nome"].split()[:2]).upper()
    patient_doctor_row = html.Div(style={
        "display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px",
        "marginBottom": "20px",
    }, children=[
        # Paciente
        hud_panel(
            title="Identificação do Paciente",
            status="DADOS CLÍNICOS",
            children=html.Div([
                html.Div(style={"display": "flex", "alignItems": "center",
                                "gap": "16px", "marginBottom": "14px"}, children=[
                    html.Div(initials_paciente, style={
                        "width": "54px", "height": "54px", "borderRadius": "50%",
                        "backgroundColor": "var(--hud-blue-dark)",
                        "color": "#FFFFFF", "display": "flex",
                        "alignItems": "center", "justifyContent": "center",
                        "fontSize": "1.4rem", "fontWeight": "700",
                        "fontFamily": "JetBrains Mono, Consolas, monospace",
                        "flexShrink": "0",
                    }),
                    html.Div([
                        html.Div(PACIENTE_INFO["nome"], style={
                            "fontSize": "1rem", "fontWeight": "700",
                            "color": "var(--hud-blue-dark)",
                            "fontFamily": "JetBrains Mono, Consolas, monospace",
                        }),
                        html.Div(
                            f"{PACIENTE_INFO['nascimento']}  //  "
                            f"{PACIENTE_INFO['idade']} anos  //  "
                            f"{PACIENTE_INFO['sexo']}",
                            style={"fontSize": "0.75rem", "color": "#6B7D8F",
                                   "fontFamily": "JetBrains Mono, Consolas, monospace"},
                        ),
                        html.Div(PACIENTE_INFO["convenio"], style={
                            "fontSize": "0.72rem", "color": "#6B7D8F",
                        }),
                    ]),
                    status_chip(overall, "Ritmo " + status_label_pt(overall).lower()),
                ]),
                # Info clínica
                *[html.Div(style={"marginBottom": "6px"}, children=[
                    html.Span(label + ": ", style={
                        "fontSize": "0.68rem", "fontWeight": "700",
                        "color": "var(--hud-blue-dark)", "textTransform": "uppercase",
                        "letterSpacing": "0.07em",
                        "fontFamily": "JetBrains Mono, Consolas, monospace",
                    }),
                    html.Span(value, style={"fontSize": "0.8rem", "color": "#2C3E50"}),
                ]) for label, value in [
                    ("Avaliação principal", PACIENTE_INFO["diagnostico_principal"]),
                    ("Comorbidades", " | ".join(PACIENTE_INFO["diagnosticos_secundarios"])),
                    ("Escore CHA₂DS₂-VA",
                     f"{PACIENTE_INFO['cha2ds2_va']} — sem indicação de anticoagulação"),
                    ("Alergias", PACIENTE_INFO["alergias"]),
                    ("Carteirinha", PACIENTE_INFO["carteirinha"]),
                ]],
                html.Div(style={
                    "marginTop": "10px", "padding": "8px 12px",
                    "backgroundColor": "rgba(7,62,130,0.05)",
                    "borderRadius": "4px", "borderLeft": f"3px solid {SUCCESS}",
                    "fontSize": "0.78rem", "color": "#2C3E50", "lineHeight": "1.5",
                }, children=PACIENTE_INFO["observacoes"]),
            ])
        ),

        # Médico responsável
        hud_panel(
            title="Médico Responsável",
            status="CARDIOLOGIA PREVENTIVA",
            accent=ACCENT_CYAN,
            children=html.Div([
                html.Div(style={"display": "flex", "alignItems": "center",
                                "gap": "16px", "marginBottom": "18px"}, children=[
                    html.Div(MEDICO["initials"], style={
                        "width": "54px", "height": "54px", "borderRadius": "50%",
                        "backgroundColor": ACCENT_CYAN,
                        "color": "#FFFFFF", "display": "flex",
                        "alignItems": "center", "justifyContent": "center",
                        "fontSize": "1.2rem", "fontWeight": "700",
                        "fontFamily": "JetBrains Mono, Consolas, monospace",
                        "flexShrink": "0",
                    }),
                    html.Div([
                        html.Div(MEDICO["nome"], style={
                            "fontSize": "1rem", "fontWeight": "700",
                            "color": "var(--hud-blue-dark)",
                            "fontFamily": "JetBrains Mono, Consolas, monospace",
                        }),
                        html.Div(MEDICO["especialidade"], style={
                            "fontSize": "0.78rem", "color": ACCENT_CYAN,
                            "fontWeight": "600",
                        }),
                        html.Div(MEDICO["crm"], style={
                            "fontSize": "0.72rem", "color": "#6B7D8F",
                            "fontFamily": "JetBrains Mono, Consolas, monospace",
                        }),
                    ]),
                ]),
                # Resumo clínico do médico
                html.Div(style={"borderTop": "1px solid #E3ECF5",
                                "paddingTop": "14px"}, children=[
                    html.Div("RESUMO CLÍNICO", style={
                        "fontSize": "0.65rem", "fontWeight": "700",
                        "color": ACCENT_CYAN, "letterSpacing": "0.1em",
                        "fontFamily": "JetBrains Mono, Consolas, monospace",
                        "marginBottom": "8px",
                    }),
                    html.P(
                        "Paciente em programa de monitoramento cardiovascular "
                        "preventivo desde mar/2025. Sem patologia cardiovascular "
                        "identificada. Perfil lipídico, glicêmico e pressórico "
                        "dentro das metas preventivas. CHA₂DS₂-VA = 0, sem indicação "
                        "de farmacoterapia cardiovascular. Conduta atual: "
                        "monitoramento PPG contínuo + check-up anual.",
                        style={"fontSize": "0.8rem", "color": "#2C3E50",
                               "lineHeight": "1.6", "margin": "0"},
                    ),
                    html.Div(style={"marginTop": "12px", "display": "flex",
                                    "gap": "8px", "flexWrap": "wrap"}, children=[
                        _badge("Assintomático", SUCCESS),
                        _badge("Sem comorbidades", SUCCESS),
                        _badge("Prevenção primária", PRIMARY_BLUE),
                        _badge("Monitoramento PPG", ACCENT_CYAN),
                    ]),
                ]),
            ])
        ),
    ])

    # ── KPIs de monitoramento ────────────────────────────────────────────────
    kpis = html.Div(className="grid grid-5", children=[
        telemetry_tile("BPM médio", f"{bpm_mean:.1f}", unit="bpm",
                       sub=bpm_zone(bpm_mean),
                       accent=bpm_zone_color(bpm_mean)),
        telemetry_tile("BPM mín / máx",
                       f"{df['bpm'].min():.0f} / {df['bpm'].max():.0f}",
                       sub="amplitude total", accent=PRIMARY_BLUE),
        telemetry_tile("IBI médio",
                       f"{df['ibi_ms'].mean():.0f}", unit="ms",
                       sub=f"sd {df['ibi_ms'].std():.0f} ms",
                       accent=ACCENT_CYAN),
        telemetry_tile("Episódios irregulares", str(irr),
                       sub=f"{irr/len(df)*100:.1f}% dos batimentos",
                       accent=DANGER if irr else SUCCESS),
        telemetry_tile("Batimentos anormais",
                       str(int(df["bat_anormais"].sum())),
                       sub="somatório da janela deslizante",
                       accent=WARNING),
    ])

    # ── Gráfico BPM timeline ─────────────────────────────────────────────────
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

    # ── Gráfico IBI ──────────────────────────────────────────────────────────
    ibi_fig = go.Figure(layout=plotly_layout(320))
    style_axes(ibi_fig, "Tempo (s)", "ms")
    ibi_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["ibi_ms"], mode="lines",
        line=dict(color=ACCENT_CYAN, width=1.6), name="IBI"))
    ibi_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["media_ibi"], mode="lines",
        line=dict(color=PRIMARY_BLUE, width=1.4, dash="dot"),
        name="Média (janela 5)"))

    # ── Gráfico desvio + anormais ────────────────────────────────────────────
    stab_fig = go.Figure(layout=plotly_layout(320))
    style_axes(stab_fig, "Tempo (s)", "Desvio (ms)", y2_title="Anormais")
    stab_fig.add_trace(go.Scatter(
        x=df["timestamp_s"], y=df["desvio_medio"], mode="lines",
        line=dict(color=DANGER, width=1.6), name="Desvio médio"))
    stab_fig.add_trace(go.Bar(
        x=df["timestamp_s"], y=df["bat_anormais"], name="Anormais",
        marker_color=ACCENT_CYAN, opacity=0.35, yaxis="y2"))
    stab_fig.add_hline(y=100, line_color=WARNING, line_dash="dash")
    stab_fig.add_hline(y=120, line_color=DANGER, line_dash="dash")

    # ── Histograma BPM por status ─────────────────────────────────────────────
    hist = px.histogram(df, x="bpm", nbins=30, color="status",
                        color_discrete_map={
                            "regular": SUCCESS, "atencao": WARNING,
                            "irregular": DANGER})
    hist.update_layout(**plotly_layout(300))
    style_axes(hist, "BPM", "Contagem")

    # ── Box plot IBI / desvio ─────────────────────────────────────────────────
    box = go.Figure(layout=plotly_layout(300))
    style_axes(box, "", "ms")
    box.add_trace(go.Box(y=df["ibi_ms"], name="IBI (ms)",
                         marker_color=PRIMARY_BLUE, line_color=PRIMARY_BLUE))
    box.add_trace(go.Box(y=df["desvio_medio"], name="Desvio médio",
                         marker_color=DANGER, line_color=DANGER))

    # ── Tabela de registros ──────────────────────────────────────────────────
    view = df.copy()
    view["status"] = view["status"].map(status_label_pt)
    if "datetime" in view.columns and pd.api.types.is_datetime64_any_dtype(view["datetime"]):
        view["datetime"] = view["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    view = view.rename(columns={
        "datetime": "Data/hora", "patient": "Paciente",
        "timestamp_s": "t (s)", "ibi_ms": "IBI (ms)", "bpm": "BPM",
        "media_ibi": "Média IBI", "desvio_medio": "Desvio médio",
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
            {"if": {"filter_query": '{Status} eq "Atenção"'}, "color": "#9A7300"},
            {"if": {"filter_query": '{Status} eq "Irregular"'},
             "color": DANGER, "fontWeight": "700"},
        ],
    )

    csv_href = "data:text/csv;charset=utf-8," + quote(df.to_csv(index=False))

    # ── Consultas ────────────────────────────────────────────────────────────
    consultas_realizadas = [c for c in CONSULTAS if c["status"] == "realizada"]
    consultas_agendadas = [c for c in CONSULTAS if c["status"] == "agendada"]

    # ── Montagem final ───────────────────────────────────────────────────────
    return html.Div([
        hero,
        patient_doctor_row,

        # Prescrição
        hud_panel(
            title="Prescrição / Suplementação Vigente",
            status=f"{len(PRESCRICAO)} ITEM" if len(PRESCRICAO) == 1
                   else f"{len(PRESCRICAO)} ITENS",
            accent=SUCCESS,
            children=html.Div([
                html.Div(style={
                    "padding": "8px 12px", "marginBottom": "14px",
                    "backgroundColor": "rgba(31,174,111,0.06)",
                    "border": f"1px solid {SUCCESS}33",
                    "borderRadius": "4px",
                    "fontSize": "0.75rem", "color": "#4A5568",
                    "fontFamily": "JetBrains Mono, Consolas, monospace",
                }, children=[
                    html.Span("✓  ", style={"color": SUCCESS}),
                    "Suplementação preventiva orientada por ",
                    html.Strong(MEDICO["nome"]),
                    f"  //  {MEDICO['crm']}  //  Sem medicação cardiovascular ativa.",
                ]),
                *[_prescricao_card(p) for p in PRESCRICAO],
            ])
        ),

        # Consultas
        html.Div(style={
            "display": "grid", "gridTemplateColumns": "1fr 1fr",
            "gap": "16px", "marginBottom": "20px",
        }, children=[
            hud_panel(
                title="Consultas Realizadas",
                status=f"{len(consultas_realizadas)} REGISTROS",
                children=html.Div(
                    [_consulta_card(c) for c in consultas_realizadas]
                ),
            ),
            hud_panel(
                title="Próximas Consultas",
                status="AGENDADO",
                accent=ACCENT_CYAN,
                children=html.Div(
                    [_consulta_card(c) for c in consultas_agendadas]
                ),
            ),
        ]),

        # KPIs PPG
        hud_panel(
            title="Monitoramento PPG — Sessão de Referência",
            status=f"{len(df)} BATIMENTOS  //  {duration_s:.0f}s",
            accent=ACCENT_CYAN,
            children=kpis,
        ),

        # BPM timeline
        hud_panel(title="Frequência cardíaca ao longo da aquisição",
                  status="TIMELINE", accent=ACCENT_CYAN,
                  children=dcc.Graph(figure=bpm_fig,
                                     config={"displayModeBar": False})),

        # IBI + desvio
        html.Div(className="grid grid-2", children=[
            hud_panel(title="Intervalo entre batimentos (IBI)",
                      status="ms",
                      children=dcc.Graph(figure=ibi_fig,
                                         config={"displayModeBar": False})),
            hud_panel(title="Desvio médio e batimentos anormais",
                      status="DESVIO", accent=DANGER,
                      children=dcc.Graph(figure=stab_fig,
                                         config={"displayModeBar": False})),
        ]),

        # Distribuições
        hud_panel(title="Distribuições",
                  status="HIST + BOX",
                  children=html.Div(className="grid grid-2", children=[
                      dcc.Graph(figure=hist, config={"displayModeBar": False}),
                      dcc.Graph(figure=box, config={"displayModeBar": False}),
                  ])),

        # Tabela de registros
        hud_panel(
            title="Registros PPG",
            status=f"{len(df)} linhas",
            children=[
                table,
                html.Div(style={"marginTop": "14px"}, children=[
                    html.A("BAIXAR CSV DE MEU PERFIL", href=csv_href,
                           className="hud-btn hud-btn--ghost",
                           download="meu_perfil_data.csv"),
                ]),
            ],
        ),
    ])
