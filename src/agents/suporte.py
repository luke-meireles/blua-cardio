"""
Agente de Suporte Clínico — Sprint 2.
Filtro RAG: bula + protocolo + politica_care_plus.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.llm.qwen_client import chat, formatar_mensagens, TEMPERATURA_RACIOCINIO
from src.prompts import carregar_prompt
from src.tools import (
    consultar_historico_paciente,
    verificar_interacoes_medicamentosas,
    agendar_teleconsulta,
    gerar_relatorio_telemetria,
)
from src.rag import recuperar_contexto_detalhado

# ---- tools spec & system prompt -----------------------------------------

_TOOLS_SPEC_PATH = Path(__file__).resolve().parents[2] / "tools" / "tools_spec.json"
_TOOLS_SPEC = json.loads(_TOOLS_SPEC_PATH.read_text(encoding="utf-8"))

# Suporte clínico foca em dúvida medicamentosa, interações e agendamento.
_TOOLS_SUPORTE = [
    {"type": "function", "function": t}
    for t in _TOOLS_SPEC
    if t["name"] in {
        "consultar_historico_paciente",
        "verificar_interacoes_medicamentosas",
        "agendar_teleconsulta",
        "gerar_relatorio_telemetria",
    }
]

SYSTEM_PROMPT_SUPORTE = carregar_prompt("agente_suporte_clinico")


# ---- tool dispatcher -----------------------------------------------------

def _executar_tool(nome: str, argumentos: dict) -> str:
    """Executa a tool pedida pelo LLM e devolve resultado serializado em JSON."""
    mapa = {
        "consultar_historico_paciente": consultar_historico_paciente,
        "verificar_interacoes_medicamentosas": verificar_interacoes_medicamentosas,
        "agendar_teleconsulta": agendar_teleconsulta,
        "gerar_relatorio_telemetria": gerar_relatorio_telemetria,
    }
    func = mapa.get(nome)
    if not func:
        return json.dumps({"erro": f"Tool '{nome}' não encontrada."})
    try:
        return json.dumps(func(**argumentos), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"erro": str(exc)})


# ---- agente principal ---------------------------------------------------

def agente_suporte_clinico(
    mensagem: str,
    historico: list[dict],
    beneficiario_id: str = "GABRIEL",
) -> dict:
    """Responde dúvidas sobre medicação ativa, interações e agendamentos."""
    system = SYSTEM_PROMPT_SUPORTE + f"\n\nBENEFICIÁRIO ATIVO: {beneficiario_id}"

    # RAG focado em informação farmacológica + protocolos Care Plus.
    contexto_rag, documentos_rag = recuperar_contexto_detalhado(
        query=mensagem,
        n_resultados=3,
        filtro_categoria=["bula", "protocolo", "politica_care_plus"],
        usar_mmr=True,
        usar_auto_rag=True,
        usar_reranker=False,
    )
    if contexto_rag:
        system += f"\n\n{contexto_rag}"

    mensagens = formatar_mensagens(system, historico, mensagem)

    # enable_thinking=False pra reduzir latência (~3-8s economizados por turno).
    # Orientações de suporte permanecem com TEMPERATURA_RACIOCINIO pra qualidade.
    resposta = chat(
        messages=mensagens,
        tools=_TOOLS_SUPORTE,
        enable_thinking=False,
        temperature=TEMPERATURA_RACIOCINIO,
    )

    tools_chamadas = []

    # Loop de tool-calling: LLM pode encadear N tools antes da resposta final.
    while resposta.get("tool_calls"):
        for tc in resposta["tool_calls"]:
            nome = tc["name"]
            argumentos = json.loads(tc["arguments"])
            print(f"[suporte] Chamando tool: {nome}({argumentos})")
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

        # enable_thinking=False também no follow-up pós-tool (mesma justificativa)
        resposta = chat(
            messages=mensagens,
            tools=_TOOLS_SUPORTE,
            enable_thinking=False,
            temperature=TEMPERATURA_RACIOCINIO,
        )

    return {
        "resposta": resposta["content"],
        "agente": "suporte_clinico",
        "tools_chamadas": tools_chamadas,
        "documentos_rag": documentos_rag,
        "thinking": resposta.get("thinking"),
        "usage": resposta["usage"],
    }
