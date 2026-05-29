"""
Página /pacientes — lista geral de beneficiários cadastrados.

Lê em tempo real (refresh 10s) de data/mocks/perfis_clinicos.json
via shared.patient_registry. Útil pra:
- Demo: ver criar_perfil_paciente refletir aqui após criação
  via chat. Counter no topo permite validação visual instantânea.
- Debug: snapshot rápido do registry sem precisar do JSON cru.
"""
from __future__ import annotations

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

from shared.patient_registry import list_patients

dash.register_page(
    __name__,
    path="/pacientes",
    name="Pacientes",
    order=4,
)


def _patient_row(p: dict) -> dbc.ListGroupItem:
    """Renderiza uma linha do beneficiário.

    `condicoes_ativas` é lista de dicts ({cid, nome, status, desde})
    — extraímos apenas o nome para o display. Filtros defensivos
    cobrem perfis recém-criados pelo chatbot (BENEF-NEW-NNN) que
    podem ter campos opcionais ausentes.
    """
    condicoes_nomes = [
        c["nome"]
        for c in p.get("condicoes_ativas", [])
        if isinstance(c, dict) and "nome" in c
    ]
    condicoes_str = ", ".join(condicoes_nomes) or "sem condições ativas"

    return dbc.ListGroupItem([
        html.Strong(p.get("nome", "?")),
        html.Span(
            f" · {p.get('id', '?')} · {p.get('idade', '?')}a · {p.get('sexo', '?')}",
            className="text-muted",
        ),
        html.Div(condicoes_str, className="small"),
    ])


layout = html.Div(className="hud-page-content", children=[
    html.H2("Pacientes cadastrados"),
    html.P("Lista lida em tempo real de data/mocks/perfis_clinicos.json"),
    dcc.Interval(id="pacientes-refresh", interval=10_000),
    dbc.ListGroup(id="pacientes-list"),
])


@callback(
    Output("pacientes-list", "children"),
    Input("pacientes-refresh", "n_intervals"),
)
def atualizar_lista(_n):
    # (b) ordenação por id — lista previsível mesmo quando pacientes
    # são criados dinamicamente via chat (BENEF-NEW-NNN ficam no fim).
    pacientes = sorted(list_patients(), key=lambda p: p.get("id", ""))

    # (a) counter no topo da lista — útil pra demo do Cenário A
    # (validação visual instantânea: total sobe de N para N+1 após
    # criação de paciente novo via chatbot).
    header = html.P(
        f"Total: {len(pacientes)} pacientes",
        className="text-muted small",
    )

    rows = [_patient_row(p) for p in pacientes]
    return [header, *rows]
