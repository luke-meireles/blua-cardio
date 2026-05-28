"""
Agente de Triagem Cardiovascular — Sprint 2.

Mudanças vs Lote 1:
- Usa recuperar_contexto_detalhado.
- Filtro: red_flag + apresentacao_atipica + estratificacao + protocolo.
- Reranker ATIVO (precisão > latência em casos clínicos críticos).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.llm.qwen_client import chat, formatar_mensagens, TEMPERATURA_RACIOCINIO
from src.prompts import carregar_prompt
from src.tools import (
    consultar_historico_paciente,
    agendar_teleconsulta,
    estratificar_dor_toracica,
    consultar_telemetria_dashboard,
)
from src.rag import recuperar_contexto_detalhado

# ---- tools spec & system prompt -----------------------------------------

_TOOLS_SPEC_PATH = Path(__file__).resolve().parents[2] / "tools" / "tools_spec.json"
_TOOLS_SPEC = json.loads(_TOOLS_SPEC_PATH.read_text(encoding="utf-8"))

# Triagem foca em estratificar gravidade e encaminhar — não medica.
_TOOLS_TRIAGEM = [
    {"type": "function", "function": t}
    for t in _TOOLS_SPEC
    if t["name"] in {"consultar_historico_paciente", "agendar_teleconsulta",
                     "estratificar_dor_toracica", "consultar_telemetria_dashboard"}
]

SYSTEM_PROMPT_TRIAGEM = carregar_prompt("agente_triagem")


# ---- tool dispatcher -----------------------------------------------------

def _executar_tool(nome: str, argumentos: dict) -> str:
    """Executa a tool pedida pelo LLM e devolve resultado serializado em JSON."""
    mapa = {
        "consultar_historico_paciente": consultar_historico_paciente,
        "agendar_teleconsulta": agendar_teleconsulta,
        "estratificar_dor_toracica": estratificar_dor_toracica,
        "consultar_telemetria_dashboard": consultar_telemetria_dashboard,
    }
    func = mapa.get(nome)
    if not func:
        return json.dumps({"erro": f"Tool '{nome}' não encontrada."})
    try:
        return json.dumps(func(**argumentos), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"erro": str(exc)})


# ---- agente principal ---------------------------------------------------

def agente_triagem(
    mensagem: str,
    historico: list[dict],
    beneficiario_id: str = "GABRIEL",
) -> dict:
    """Estratifica risco CV e encaminha (autocuidado / consulta / SAMU)."""
    system = SYSTEM_PROMPT_TRIAGEM + f"\n\nBENEFICIÁRIO ATIVO: {beneficiario_id}"

    # RAG com reranker ATIVO + filtro em red_flag e apresentações atípicas
    contexto_rag, documentos_rag = recuperar_contexto_detalhado(
        query=mensagem,
        n_resultados=4,
        filtro_categoria=["red_flag", "apresentacao_atipica",
                          "estratificacao", "protocolo"],
        usar_mmr=True,
        usar_auto_rag=True,
        usar_reranker=True,  # ⚡ ATIVO em triagem
    )
    if contexto_rag:
        system += f"\n\n{contexto_rag}"

    mensagens = formatar_mensagens(system, historico, mensagem)

    # Thinking ON + temperatura de raciocínio: triagem é o cenário mais crítico.
    resposta = chat(
        messages=mensagens,
        tools=_TOOLS_TRIAGEM,
        enable_thinking=True,
        temperature=TEMPERATURA_RACIOCINIO,
    )

    tools_chamadas = []

    # Loop de tool-calling: LLM pode encadear N tools antes da resposta final.
    while resposta.get("tool_calls"):
        for tc in resposta["tool_calls"]:
            nome = tc["name"]
            argumentos = json.loads(tc["arguments"])
            print(f"[triagem] Chamando tool: {nome}({argumentos})")
            resultado = _executar_tool(nome, argumentos)
            tools_chamadas.append({"tool": nome, "resultado": resultado})

            # Reinjeta a tool call + resultado no histórico pra próxima rodada.
            mensagens.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": nome, "arguments": tc["arguments"]}
                }]
            })
            mensagens.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": resultado
            })

        resposta = chat(
            messages=mensagens,
            tools=_TOOLS_TRIAGEM,
            enable_thinking=True,
            temperature=TEMPERATURA_RACIOCINIO,
        )

    return {
        "resposta": resposta["content"],
        "agente": "triagem",
        "tools_chamadas": tools_chamadas,
        "documentos_rag": documentos_rag,
        "thinking": resposta.get("thinking"),
        "usage": resposta["usage"],
    }
