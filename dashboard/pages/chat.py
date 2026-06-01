"""
BluaDiagnostics — Interface Dash (Sprint 2).

Aplicação web Dash com:
- Chat conversacional cardiovascular
- Painel técnico em tempo real: pre_safety, supervisor, trajetória,
  RAG (chunks + scores), tools chamadas, safety flags, confidence
- Suporte HITL (botão aprovar/rejeitar rascunho de prescrição)
- Indicador de backend (DashScope / Ollama) com troca via env var
- Alerta sonoro para red flag (alert.wav)

Execução:
    python app/dash_app.py
    # Abre em http://localhost:8050

Variáveis ambiente respeitadas:
- DASHSCOPE_API_KEY (modo cloud)
- LLM_BACKEND=dashscope|ollama
- QWEN_OLLAMA_MODEL=qwen2.5:14b (default)
- LANGSMITH_API_KEY (observabilidade opcional)
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Garantir raiz do projeto no path.
# Arquivo está em dashboard/pages/chat.py:
#   parents[0] = dashboard/pages/
#   parents[1] = dashboard/
#   parents[2] = raiz do projeto  <-- queremos esta
# Necessário pra que "from src.graph import ..." e "from colab_setup import ..."
# resolvam corretamente.
_RAIZ = Path(__file__).resolve().parents[2]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# Bootstrap ambiente (LangSmith se configurado)
try:
    from colab_setup import preparar_ambiente
    preparar_ambiente(exigir_chave=False)
except Exception as exc:
    print(f"[dash_app] Bootstrap aviso: {exc}")

import dash
from dash import (
    html, dcc, callback, clientside_callback,
    Input, Output, State, no_update, ctx,
)
import dash_bootstrap_components as dbc

# Registro da página no app multi-pages.
# path='/chat' (C3 da integração ArrhythmiaMonitor): raiz '/' é home.py
# upstream agora; chat fica em /chat.
# order=5: vem depois de home(0), monitor(1), analise(2), gabriel(3),
# deixando order=4 livre pra /meu-perfil (C13/H futuro).
dash.register_page(
    __name__,
    path="/chat",
    name="Chat",
    order=5,
)

from src.graph import construir_grafo, executar_turno, aprovar_rascunho_prescricao
from shared.patient_registry import list_patients

# =============================================================================
# Configuração e bootstrap do grafo
# =============================================================================

BACKEND_ATUAL = os.getenv("LLM_BACKEND", "dashscope")
MODELO_ATUAL = (os.getenv("QWEN_DASHSCOPE_MODEL", "qwen-plus")
                if BACKEND_ATUAL == "dashscope"
                else os.getenv("QWEN_OLLAMA_MODEL", "qwen2.5:14b"))

# Construir grafo uma única vez na inicialização
print("[dash_app] Construindo grafo LangGraph...")
GRAFO = construir_grafo()
print("[dash_app] Grafo pronto.")

# Lista de beneficiários disponíveis (J.7 — Fase J).
#
# Filtro híbrido: Gabriel + MEU_PERFIL + qualquer perfil criado via
# chatbot (BENEF-NEW-XXX). Exclui BENEFs canônicos (BENEF-001 a
# BENEF-CV-003 — dados de teste do blua-cardio original) pra alinhar
# com o dropdown do topbar (que mostra só Gabriel + Meu Perfil).
#
# Carregado em module-import: mudanças no JSON refletem na próxima
# reinicialização do app. Refresh em runtime (criar perfil via chatbot
# ou UI/J.1) precisaria callback dinâmico — fora do escopo do J.7.
def _format_label(p: dict) -> str:
    nome = p.get("nome") or (
        "Meu Perfil" if p["id"] == "MEU_PERFIL" else f"Perfil {p['id']}"
    )
    idade = p.get("idade")
    return f"{nome} — {idade}a" if idade is not None else nome


def _eh_perfil_visivel(p: dict) -> bool:
    pid = p["id"]
    return (
        pid == "GABRIEL"
        or pid == "MEU_PERFIL"
        or pid.startswith("BENEF-NEW-")
    )


BENEFICIARIOS = [
    {"label": _format_label(p), "value": p["id"]}
    for p in list_patients()
    if _eh_perfil_visivel(p)
]

# =============================================================================
# App
# =============================================================================
# Removido pelo Passo 8.5 — a instância Dash() agora vive em app/unified_app.py
# (entrypoint único multi-pages). Esta página apenas exporta `layout` e
# decora callbacks com @callback (global, do módulo dash).

# =============================================================================
# Componentes auxiliares
# =============================================================================

def hud_panel(title: str, content, status: str = "ATIVO"):
    """HUD panel com cantos em bracket — base do design system."""
    return html.Div([
        html.Span(className="hud-corner hud-corner--tl"),
        html.Span(className="hud-corner hud-corner--tr"),
        html.Span(className="hud-corner hud-corner--bl"),
        html.Span(className="hud-corner hud-corner--br"),
        html.Div([
            html.Div([
                html.Span(className="hud-panel__tick"),
                html.Span(title, className="hud-panel__title"),
            ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
            html.Span(status, className="hud-panel__status"),
        ], className="hud-panel__header"),
        html.Div(content, className="hud-panel__body"),
    ], className="hud-panel")


def patient_card(perfil_id: str):
    """Card visual do paciente ativo no chat.

    Fix consolidado pós-merge: lê dinamicamente do JSON via get_patient()
    em vez de dict perfis_info hardcoded (que só tinha GABRIEL + BENEFs
    antigos e mostrava '??' pra MEU_PERFIL/BENEF-NEW-*).
    """
    from shared.patient_registry import get_patient

    perfil = get_patient(perfil_id) if perfil_id else None

    if not perfil or not perfil.get("nome"):
        # MEU_PERFIL não preenchido ou perfil inexistente
        iniciais = "??"
        nome = "Perfil não preenchido"
        meta = "Crie em /meu-perfil"
        condicoes = "—"
    else:
        nome = perfil["nome"]
        # Iniciais: primeiras letras das 2 primeiras palavras
        partes = nome.split()
        iniciais = (partes[0][0] + (partes[1][0] if len(partes) > 1 else "")).upper()

        idade = perfil.get("idade")
        sexo = perfil.get("sexo")
        if idade and sexo:
            meta = f"{idade}a · {sexo}"
        elif idade:
            meta = f"{idade}a"
        else:
            meta = "—"

        condicoes_lista = perfil.get("condicoes_ativas", [])
        if condicoes_lista:
            nomes_cond = [c.get("nome", str(c)) if isinstance(c, dict) else str(c)
                          for c in condicoes_lista]
            # primeiras 2 pra caber visualmente
            condicoes = " · ".join(nomes_cond[:2])
        else:
            condicoes = "Sem condições registradas"

    return html.Div([
        html.Div(iniciais, className="hud-patient__avatar"),
        html.Div([
            html.Div(nome, className="hud-patient__name"),
            html.Div(meta, className="hud-patient__meta"),
            html.Div(condicoes, className="hud-patient__meta",
                     style={"marginTop": "6px", "color": "var(--hud-blue-dark)"}),
        ]),
        html.Div([
            html.Span("ID", className="lbl",
                     style={"fontSize": "0.65rem", "letterSpacing": "0.16em",
                            "color": "var(--hud-muted)"}),
            html.Div(perfil_id, style={"fontFamily": "'JetBrains Mono', monospace",
                                         "color": "var(--hud-blue-dark)",
                                         "fontWeight": "700"}),
        ], style={"textAlign": "right"}),
    ], className="hud-patient blua-patient-card")


def chat_bubble(role: str, content: str, emergencia: bool = False):
    """Bubble de chat."""
    classes = "blua-bubble blua-bubble--" + ("user" if role == "user" else "assistant")
    if emergencia:
        classes += " blua-bubble--emergencia"
    return html.Div([
        html.Div(role.upper(), className="blua-bubble__role"),
        dcc.Markdown(content, dangerously_allow_html=False,
                     style={"margin": 0, "color": "inherit"}),
    ], className=classes)


def rag_chunk_card(doc: dict):
    """Card mostrando um chunk de RAG recuperado."""
    score_sim = doc.get("score_similaridade", 0)
    score_rerank = doc.get("score_rerank")
    score_display = f"sim={score_sim:.2f}"
    if score_rerank is not None:
        score_display += f" · rerank={score_rerank:.2f}"

    return html.Div([
        html.Div([
            html.Span(f"#{doc.get('rank', '?')}  {doc.get('fonte', '?')}"),
            html.Span(score_display, className="blua-rag-chunk__score"),
        ], className="blua-rag-chunk__meta"),
        html.Div(doc.get("chunk", "")[:220] + "…",
                 className="blua-rag-chunk__text"),
        html.Div(f"categoria: {doc.get('categoria', '—')}",
                 style={"fontSize": "0.7rem", "color": "var(--hud-muted)",
                        "marginTop": "4px", "fontFamily": "'JetBrains Mono', monospace"}),
    ], className="blua-rag-chunk")


def trajectory_display(trajetoria: list[str]):
    """Visualiza trajetória de nós percorridos."""
    if not trajetoria:
        return html.Div("—", className="hud-tile__sub")

    elementos = []
    for i, no in enumerate(trajetoria):
        is_current = (i == len(trajetoria) - 1)
        classes = "blua-trajectory__step"
        if is_current:
            classes += " blua-trajectory__step--current"
        elementos.append(html.Span(no, className=classes))
        if i < len(trajetoria) - 1:
            elementos.append(html.Span("→", className="blua-trajectory__arrow"))

    return html.Div(elementos, className="blua-trajectory")


def confidence_badge(nivel: str, score: float):
    """Badge de confiança colorido."""
    if not nivel:
        return html.Div("—")
    classes = f"blua-confidence blua-confidence--{nivel}"
    return html.Div([
        html.Span(nivel.upper()),
        html.Span(f"{score:.2f}", style={"fontWeight": "400", "opacity": "0.75"}),
    ], className=classes)


# =============================================================================
# Layout
# =============================================================================

layout = html.Div([
    # Audio element (alert.wav) — ativado por callback quando red flag
    html.Audio(id="audio-alert", src="/assets/alert.wav",
               className="blua-audio-alert", autoPlay=False),

    # J.4 — trigger de rehidratação agora usa Input("_pages_content", "children")
    # diretamente no callback _rehidratar_chat_area (ver abaixo). Não é mais
    # necessário componente no layout do /chat — o page_container do Dash
    # multi-pages é trigger nativo. Histórico:
    #   v1: dcc.Interval(max_intervals=1) em chat.py — só funcionava na 1ª visita
    #   v2: Store global + async clientside_callback com setTimeout(400ms) —
    #       Promise não esperava resolver no Dash 4.1, downstream não disparava
    #   v3 (atual): Input("_pages_content", "children") — trigger nativo do
    #       Dash multi-pages, sem delay artificial, sem Promise async.

    # Session storage — Passo 8.5: movido para o layout global do
    # app/unified_app.py com storage_type="session" (preserva conversa
    # entre páginas, reseta ao fechar a aba). Callbacks abaixo continuam
    # referenciando "session-data" — Dash resolve Stores globais por ID
    # independente da página ativa.

    # Page container
    html.Div([
        # 3-column main grid
        html.Div([
            # Coluna esquerda — Paciente
            html.Div([
                hud_panel("PACIENTE", [
                    dcc.Dropdown(
                        id="beneficiario-select",
                        options=BENEFICIARIOS,
                        value="GABRIEL",
                        clearable=False,
                        style={"marginBottom": "12px"},
                    ),
                    html.Div(id="patient-card-container"),
                    html.Button("NOVA SESSÃO", id="btn-nova-sessao",
                                className="hud-btn hud-btn--ghost",
                                style={"width": "100%", "marginTop": "16px"}),
                ]),
            ], style={"gridColumn": "span 3"}),

            # Coluna central — Chat
            html.Div([
                hud_panel("DIÁLOGO CLÍNICO", [
                    # dcc.Loading exibe um spinner sobre a chat-area enquanto
                    # o callback principal estiver em andamento — feedback
                    # visual instantaneo no clique de ENVIAR.
                    dcc.Loading(
                        id="chat-loading",
                        type="circle",
                        color="var(--hud-blue-dark, #007AB8)",
                        children=html.Div(id="chat-area", className="blua-chat-area",
                                 children=[
                                     html.Div("Olá! Sou o BluaDiagnostics. "
                                              "Pode me contar como está se sentindo "
                                              "ou pedir informações sobre seu acompanhamento cardiovascular.",
                                              className="hud-info",
                                              style={"alignSelf": "center"})
                                 ]),
                    ),
                    html.Div([
                        dcc.Input(id="user-input", type="text",
                                  placeholder="Digite sua mensagem…",
                                  debounce=False, n_submit=0,
                                  style={"width": "100%"}),
                        html.Button("ENVIAR", id="btn-enviar",
                                    className="hud-btn"),
                    ], className="blua-input-row"),
                    # hitl-container: placeholders ocultos garantem que
                    # btn-hitl-aprovar e btn-hitl-rejeitar SEMPRE existam no
                    # DOM (sao Input do callback principal). Sem eles, o
                    # frontend manda os Inputs incompletos e o backend lanca
                    # IndexError no _prepare_grouping.
                    html.Div(id="hitl-container", children=[
                        html.Button("", id="btn-hitl-aprovar",
                                    style={"display": "none"}),
                        html.Button("", id="btn-hitl-rejeitar",
                                    style={"display": "none"}),
                    ]),
                ], status="ONLINE"),
            ], style={"gridColumn": "span 6"}),

            # Coluna direita — Painel técnico
            html.Div([
                hud_panel("CONFIDENCE", html.Div("—",
                                                  id="confidence-display",
                                                  style={"color": "var(--hud-muted)"}),
                          status="REAL-TIME"),
                hud_panel("TRAJETÓRIA LANGGRAPH", html.Div("—",
                                                            id="trajectory-display",
                                                            style={"color": "var(--hud-muted)"}),
                          status="REAL-TIME"),
                hud_panel("INTENT", html.Div("—",
                                              id="intent-display",
                                              style={"fontFamily": "'JetBrains Mono', monospace",
                                                     "fontSize": "0.86rem",
                                                     "color": "var(--hud-muted)"}),
                          status="SUPERVISOR"),
                hud_panel("RAG · DOCUMENTOS", html.Div("—",
                                                        id="rag-display",
                                                        style={"color": "var(--hud-muted)"}),
                          status="CHROMADB"),
                hud_panel("TOOLS CHAMADAS", html.Div("—",
                                                      id="tools-display",
                                                      style={"color": "var(--hud-muted)"}),
                          status="FUNCTION"),
                hud_panel("SAFETY", html.Div("—",
                                              id="safety-display",
                                              style={"color": "var(--hud-muted)"}),
                          status="DUAL-LAYER"),
            ], style={"gridColumn": "span 3"}),

        ], className="grid grid-12col", style={"marginTop": "16px"}),

        # Footer REMOVIDO — o footer global em dashboard/app.py já mostra
        # o disclaimer em todas as rotas. Manter aqui criava barra duplicada.

    ], className="hud-page"),

], className="app-shell")


# =============================================================================
# Callbacks
# =============================================================================

def _hitl_placeholders():
    """Botoes HITL ocultos — usado quando nao ha rascunho pendente.

    Importante: btn-hitl-aprovar e btn-hitl-rejeitar sao Input do callback
    principal. Eles PRECISAM existir no DOM mesmo quando nao ha HITL ativo,
    senao o frontend manda os Inputs incompletos e Dash falha com
    IndexError no _prepare_grouping.
    """
    return [
        html.Button("", id="btn-hitl-aprovar", style={"display": "none"}),
        html.Button("", id="btn-hitl-rejeitar", style={"display": "none"}),
    ]


@callback(
    Output("patient-card-container", "children"),
    Input("beneficiario-select", "value"),
)
def atualizar_card_paciente(beneficiario_id):
    return patient_card(beneficiario_id or "GABRIEL")


# Fix consolidado pós-merge: sincronização bidirecional perfil-ativo Store
# ↔ dropdown chat 'beneficiario-select'. Antes o dropdown era estado órfão
# (hardcoded value="GABRIEL", ignorava o Store). Visível ao trocar perfil
# pelo topbar e abrir /chat — dropdown ficava em GABRIEL.
@callback(
    Output("beneficiario-select", "value"),
    Input("perfil-ativo", "data"),
    State("beneficiario-select", "value"),
    prevent_initial_call=False,
)
def _sync_chat_dropdown_from_store(perfil_data, current):
    """Store → dropdown chat. no_update quando já bate evita ping-pong."""
    if not perfil_data:
        return no_update
    target = perfil_data.get("id")
    if target and target != current:
        return target
    return no_update


@callback(
    Output("perfil-ativo", "data", allow_duplicate=True),
    Input("beneficiario-select", "value"),
    State("perfil-ativo", "data"),
    prevent_initial_call=True,
)
def _sync_store_from_chat_dropdown(chat_value, current):
    """Dropdown chat → Store. allow_duplicate porque app.py já tem Output."""
    if not chat_value:
        return no_update
    if current and current.get("id") == chat_value:
        return no_update
    return {"id": chat_value}


# Refresh dinâmico das options ao re-entrar em /chat. BENEFICIARIOS é
# carregado em module-import; sem este callback, mudar nome do MEU_PERFIL
# via formulário só refletiria após restart do app.
@callback(
    Output("beneficiario-select", "options"),
    Input("hud-url", "pathname"),
    prevent_initial_call=False,
)
def _refresh_chat_dropdown_options(pathname):
    """Re-lê list_patients() do JSON ao entrar em /chat."""
    if pathname != "/chat":
        return no_update
    return [
        {"label": _format_label(p), "value": p["id"]}
        for p in list_patients()
        if _eh_perfil_visivel(p)
    ]


@callback(
    Output("session-data", "data"),
    # chat-area e user-input.value tem allow_duplicate=True porque tambem
    # sao escritos pelo clientside_callback de Optimistic UI (logo abaixo).
    Output("chat-area", "children", allow_duplicate=True),
    Output("confidence-display", "children"),
    Output("trajectory-display", "children"),
    Output("intent-display", "children"),
    Output("rag-display", "children"),
    Output("tools-display", "children"),
    Output("safety-display", "children"),
    Output("hitl-container", "children"),
    Output("user-input", "value", allow_duplicate=True),
    Output("audio-alert", "autoPlay"),
    Input("btn-enviar", "n_clicks"),
    Input("user-input", "n_submit"),
    Input("btn-nova-sessao", "n_clicks"),
    Input("btn-hitl-aprovar", "n_clicks"),
    Input("btn-hitl-rejeitar", "n_clicks"),
    State("user-input", "value"),
    State("beneficiario-select", "value"),
    State("session-data", "data"),
    prevent_initial_call=True,
)
def processar_mensagem(n_enviar, n_submit, n_nova, n_aprovar, n_rejeitar,
                       mensagem, beneficiario, sessao):
    trig = ctx.triggered_id

    import sys as _sys
    print(f"[PROCESSAR_ENTRY] trig={trig!r} n_enviar={n_enviar!r} n_submit={n_submit!r} "
          f"n_nova={n_nova!r} n_aprovar={n_aprovar!r} n_rejeitar={n_rejeitar!r}",
          file=_sys.stderr, flush=True)

    # Lazy init de session-data: gera thread_id na primeira ação do user.
    # Antes era feito via clientside callback em pathname change, mas Dash 4.1
    # tinha race condition que wipava o Store em navegações subsequentes.
    # Aqui, sessao só é tocada quando o user dispara uma ação (botão/Enter),
    # garantindo zero interferência da navegação entre rotas.
    if not sessao or not isinstance(sessao, dict) or not sessao.get("thread_id"):
        sessao = {
            "thread_id": str(uuid.uuid4()),
            "mensagens": [],
            "flags_safety_anteriores": [],
            "ultimo_estado": None,
        }

    # GUARDA contra trigger falso por re-mount do botão em navegação multi-pages:
    # Quando user navega /chat → /monitor → /chat, os botões re-montam com
    # n_clicks=None, e Dash dispara processar_mensagem com trigger spurious.
    # Antigamente isso wipava as mensagens via branch btn-nova-sessao.
    # Fix: rejeitar trigger de botão com n_clicks falsy.
    button_clicks = {
        "btn-enviar": n_enviar,
        "btn-nova-sessao": n_nova,
        "btn-hitl-aprovar": n_aprovar,
        "btn-hitl-rejeitar": n_rejeitar,
    }
    if trig in button_clicks and not button_clicks[trig]:
        print(f"[PROCESSAR_GUARD] rejeitado trigger spurious: trig={trig} "
              f"n_clicks={button_clicks[trig]!r}", file=_sys.stderr, flush=True)
        return (no_update,) * 11

    # Reset de sessão — limpa só a UI, MANTÉM thread_id (contexto LangGraph
    # preservado). Útil pra demo: apresentador limpa a tela visualmente sem
    # perder o fio da conversa que o chatbot já tem internamente.
    if trig == "btn-nova-sessao":
        nova_sessao = {
            "thread_id": sessao["thread_id"],  # preserva contexto do grafo
            "mensagens": [],
            "flags_safety_anteriores": [],
            "ultimo_estado": None,
        }
        return (nova_sessao,
                [html.Div("Nova sessão iniciada.", className="hud-info",
                           style={"alignSelf": "center"})],
                "—", "—", "—", "—", "—", "—",
                _hitl_placeholders(), "", False)

    # B6 — HITL: aprovação/rejeição do rascunho de prescrição
    if trig in ("btn-hitl-aprovar", "btn-hitl-rejeitar"):
        aprovado = trig == "btn-hitl-aprovar"
        print(f"\n[dash_app] HITL: rascunho {'aprovado' if aprovado else 'rejeitado'}")
        try:
            estado = aprovar_rascunho_prescricao(
                grafo=GRAFO,
                thread_id=sessao["thread_id"],
                aprovado=aprovado,
            )
        except Exception as exc:
            print(f"[dash_app] Erro HITL: {exc}")
            return (no_update, no_update, no_update, no_update, no_update,
                    no_update, no_update,
                    html.Div(f"Erro HITL: {exc}", className="hud-alert"),
                    no_update, no_update, no_update)
        # Substitui a "mensagem" do usuário pelo log de auditoria HITL
        mensagem = f"[Médico {'aprovou' if aprovado else 'rejeitou'} o rascunho]"

    elif not mensagem or not mensagem.strip():
        return (no_update,) * 11

    else:
        # Executar turno normal no grafo
        print(f"\n[dash_app] Turno: {mensagem!r}")
        try:
            estado = executar_turno(
                grafo=GRAFO,
                mensagem_usuario=mensagem,
                thread_id=sessao["thread_id"],
                beneficiario_id=beneficiario,
                flags_safety_anteriores=sessao.get("flags_safety_anteriores", []),
            )
        except Exception as exc:
            print(f"[dash_app] Erro: {exc}")
            return (no_update, no_update, no_update, no_update, no_update,
                    no_update, no_update,
                    html.Div(f"Erro: {exc}", className="hud-alert"),
                    no_update, no_update, no_update)

    # Atualizar sessão
    resposta_final = estado.get("resposta_final", "")
    flags = estado.get("flags_safety", [])
    eh_emergencia = ("RED_FLAG" in str(flags)
                     or estado.get("agente_ativo") == "escalada_humana"
                     or "192" in resposta_final)

    sessao["mensagens"].append({"role": "user", "content": mensagem})
    sessao["mensagens"].append({"role": "assistant", "content": resposta_final,
                                  "emergencia": eh_emergencia})
    sessao["flags_safety_anteriores"] = flags
    sessao["ultimo_estado"] = {
        "intent": estado.get("intent_classificada"),
        "confianca_intent": estado.get("confianca_intent"),
        "agente_ativo": estado.get("agente_ativo"),
        "trajetoria_nos": estado.get("trajetoria_nos", []),
        "tools_chamadas": [t["tool"] for t in estado.get("tools_chamadas", [])],
        "documentos_rag": estado.get("documentos_rag", []),
        "flags_safety": flags,
        "confidence_score": estado.get("confidence_score", 0),
        "confidence_nivel": estado.get("confidence_nivel", "—"),
        "requer_aprovacao_humana": estado.get("requer_aprovacao_humana", False),
    }

    # Renderizar chat
    chat_children = [
        chat_bubble(m["role"], m["content"],
                    emergencia=m.get("emergencia", False))
        for m in sessao["mensagens"]
    ]

    # Painel técnico
    ult = sessao["ultimo_estado"]

    confidence_view = confidence_badge(ult["confidence_nivel"],
                                        ult["confidence_score"] or 0)
    trajectory_view = trajectory_display(ult["trajetoria_nos"])
    intent_view = html.Div([
        html.Div(f"intent: {ult['intent'] or '—'}",
                 style={"color": "var(--hud-blue-dark)", "fontWeight": "600"}),
        html.Div(f"confiança: {ult['confianca_intent']:.2f}"
                 if ult["confianca_intent"] else "confiança: —",
                 style={"color": "var(--hud-muted)"}),
        html.Div(f"agente_final: {ult['agente_ativo'] or '—'}",
                 style={"color": "var(--hud-cyan-deep)", "marginTop": "4px"}),
    ])
    rag_view = ([rag_chunk_card(d) for d in ult["documentos_rag"]]
                if ult["documentos_rag"]
                else html.Div("Sem chunks recuperados",
                              style={"color": "var(--hud-muted)",
                                     "fontStyle": "italic"}))
    tools_view = (html.Div([html.Code(t, style={"display": "block",
                                                  "padding": "4px 0",
                                                  "fontSize": "0.82rem"})
                            for t in ult["tools_chamadas"]])
                  if ult["tools_chamadas"]
                  else html.Div("Nenhuma tool chamada",
                                style={"color": "var(--hud-muted)",
                                       "fontStyle": "italic"}))

    if flags:
        safety_chips = [
            html.Span(f, className=f"hud-chip hud-chip--{'bad' if 'RED' in f or 'REPROV' in f else 'warn'}",
                      style={"display": "block", "margin": "4px 0"})
            for f in flags
        ]
        safety_view = html.Div(safety_chips)
    else:
        safety_view = html.Span("APROVADO", className="hud-chip hud-chip--ok")

    # HITL — botoes sempre presentes no DOM (Input do callback), apenas
    # mudam de visiveis (com label) para ocultos conforme requer_aprovacao_humana.
    if ult["requer_aprovacao_humana"]:
        hitl_view = html.Div([
            html.Span("🩺 Rascunho aguardando aprovação médica",
                      className="blua-hitl__label"),
            html.Button("APROVAR", className="hud-btn", id="btn-hitl-aprovar"),
            html.Button("REJEITAR", className="hud-btn hud-btn--ghost",
                        id="btn-hitl-rejeitar"),
        ], className="blua-hitl")
    else:
        hitl_view = _hitl_placeholders()

    import sys as _sys
    print(f"[PROCESSAR] gravando em session-data: {len(sessao.get('mensagens', []))} mensagens",
          file=_sys.stderr, flush=True)
    return (sessao, chat_children, confidence_view, trajectory_view,
            intent_view, rag_view, tools_view, safety_view, hitl_view,
            "", eh_emergencia)


# =============================================================================
# Optimistic UI — pinta a mensagem do usuario INSTANTANEAMENTE no chat,
# sem esperar o servidor Python responder. Executa direto no navegador
# em JavaScript.
#
# Fluxo:
#   1. User clica ENVIAR ou aperta Enter no input
#   2. Este clientside callback pinta o balao "USER" no chat-area JA
#   3. Em paralelo, o callback Python principal dispara, processa o
#      turno (~5-10s), e quando volta substitui o chat-area inteiro com
#      a versao completa (user msg + assistant msg)
#
# A substituicao no passo 3 funciona porque a versao do servidor inclui
# o mesmo balao do user + o novo balao do assistant — visualmente nao
# pisca, so adiciona a resposta.
# =============================================================================
clientside_callback(
    """
    function(n_enviar, n_submit, msg, currentChildren) {
        if (!msg || !msg.trim()) {
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }
        // Construir o balao de usuario no mesmo formato do chat_bubble Python
        const bolhaUser = {
            namespace: 'dash_html_components',
            type: 'Div',
            props: {
                className: 'blua-bubble blua-bubble--user',
                children: [
                    {namespace: 'dash_html_components', type: 'Div',
                     props: {className: 'blua-bubble__role', children: 'USER'}},
                    {namespace: 'dash_html_components', type: 'Div',
                     props: {style: {margin: 0, color: 'inherit'}, children: msg}}
                ]
            }
        };
        // Bolha placeholder "Pensando..." enquanto o servidor processa
        const bolhaPensando = {
            namespace: 'dash_html_components',
            type: 'Div',
            props: {
                className: 'blua-bubble blua-bubble--assistant',
                style: {opacity: 0.6, fontStyle: 'italic'},
                children: [
                    {namespace: 'dash_html_components', type: 'Div',
                     props: {className: 'blua-bubble__role', children: 'BLUA'}},
                    {namespace: 'dash_html_components', type: 'Div',
                     props: {style: {margin: 0, color: 'inherit'},
                             children: 'Analisando seu caso…'}}
                ]
            }
        };
        const novoChildren = Array.isArray(currentChildren)
            ? currentChildren.concat([bolhaUser, bolhaPensando])
            : [bolhaUser, bolhaPensando];
        return [novoChildren, ''];  // limpa o input
    }
    """,
    Output("chat-area", "children", allow_duplicate=True),
    Output("user-input", "value", allow_duplicate=True),
    Input("btn-enviar", "n_clicks"),
    Input("user-input", "n_submit"),
    State("user-input", "value"),
    State("chat-area", "children"),
    prevent_initial_call=True,
)


# =============================================================================
# J.4 — Rehidratação de chat-area ao re-entrar em /chat
# =============================================================================
# Bug: o layout do /chat é estático (children de chat-area hardcoded com
# "Olá! Sou o BluaDiagnostics..."). Cada navegação pra /chat re-renderiza
# o layout inicial, sobrescrevendo o histórico de bolhas. Session-data
# (Store global) preserva as mensagens mas a UI não as exibe.
#
# Fix: callback dispara em mudança de pathname; quando pathname == "/chat",
# lê session-data.mensagens e re-renderiza bolhas via chat_bubble().
#
# Escopo: rehidrata apenas chat-area (mensagens). Painéis técnicos
# (confidence/trajetória/RAG/tools/safety) voltam pra "—" ao re-entrar —
# o histórico das mensagens é o que importa pro usuário; painéis populam
# de novo no próximo turno do chatbot. Trade-off de simplicidade.


@callback(
    Output("chat-area", "children", allow_duplicate=True),
    Input("_pages_content", "children"),
    State("session-data", "data"),
    State("hud-url", "pathname"),
    prevent_initial_call=True,
)
def _rehidratar_chat_area(_content, sessao, pathname):
    """Rehidrata área de mensagens ao re-entrar em /chat."""
    import sys as _sys
    n_msg = len(sessao.get("mensagens", [])) if isinstance(sessao, dict) else "N/A"
    print(f"[REHIDRATE] disparado! pathname={pathname!r} sessao_type={type(sessao).__name__} mensagens={n_msg}",
          file=_sys.stderr, flush=True)

    if pathname != "/chat":
        print(f"[REHIDRATE] skip — pathname={pathname!r} != /chat", file=_sys.stderr, flush=True)
        return no_update
    if not sessao or not isinstance(sessao, dict):
        print(f"[REHIDRATE] skip — sessao vazia/inválida ({type(sessao).__name__})", file=_sys.stderr, flush=True)
        return no_update
    mensagens = sessao.get("mensagens", [])
    if not mensagens:
        print(f"[REHIDRATE] skip — zero mensagens no Store", file=_sys.stderr, flush=True)
        return no_update

    print(f"[REHIDRATE] RENDERIZANDO {len(mensagens)} mensagens em chat-area", file=_sys.stderr, flush=True)
    return [
        chat_bubble(m["role"], m["content"],
                    emergencia=m.get("emergencia", False))
        for m in mensagens
    ]


# =============================================================================
# Run
# =============================================================================
# Nota: o callback `init_painel_tecnico` foi removido em 2026-05-26. Ele
# declarava outputs com `allow_duplicate=True` conflitando com o callback
# principal (sem flag), o que corrompia o registro de callbacks e gerava
# KeyError no Dash. Os placeholders "—" sao agora setados diretamente no
# layout dos panel divs (confidence/trajectory/intent/rag/tools/safety).
#
# Optimistic UI (2026-05-26): clientside_callback pinta o balao USER e a
# bolha "Pensando..." instantaneamente. Callback Python substitui o
# chat-area completo quando responde — usuario percebe latencia zero.

# Bloco `if __name__ == "__main__": app.run(...)` removido pelo Passo 8.5.
# O servidor agora é iniciado por app/unified_app.py, que monta todas as
# páginas (chat, monitor, analise, gabriel) num único Flask na porta 8050.
