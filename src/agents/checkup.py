"""
Agente de Check-up — Sprint 2.

Mudanças vs Lote 1:
- Usa recuperar_contexto_detalhado (Sprint 2) para popular documentos_rag no estado.
- RAG filtra por categorias relevantes para check-up: cartilha, protocolo, especialidades.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.llm.qwen_client import chat, formatar_mensagens
from src.prompts import carregar_prompt
from src.tools import (
    consultar_historico_paciente,
    analisar_ritmo_cardiaco,
    consultar_sinais_vitais_wearable,
    agendar_teleconsulta,
    criar_perfil_paciente,
    consultar_telemetria_dashboard,
)
from src.rag import recuperar_contexto_detalhado

# ---- tools spec & system prompt -----------------------------------------

_TOOLS_SPEC_PATH = Path(__file__).resolve().parents[2] / "tools" / "tools_spec.json"
_TOOLS_SPEC = json.loads(_TOOLS_SPEC_PATH.read_text(encoding="utf-8"))

# Subset orientado a prevenção: histórico, ritmo, wearable e agendamento.
_TOOLS_CHECKUP = [
    {"type": "function", "function": t}
    for t in _TOOLS_SPEC
    if t["name"] in {
        "consultar_historico_paciente",
        "analisar_ritmo_cardiaco",
        "consultar_sinais_vitais_wearable",
        "agendar_teleconsulta",
        "criar_perfil_paciente",
        "consultar_telemetria_dashboard",
    }
]

SYSTEM_PROMPT_CHECKUP = carregar_prompt("agente_checkup")


# ---- tool dispatcher -----------------------------------------------------

def _executar_tool(nome: str, argumentos: dict) -> str:
    """Executa a tool pedida pelo LLM e devolve resultado serializado em JSON."""
    mapa = {
        "consultar_historico_paciente": consultar_historico_paciente,
        "analisar_ritmo_cardiaco": analisar_ritmo_cardiaco,
        "consultar_sinais_vitais_wearable": consultar_sinais_vitais_wearable,
        "agendar_teleconsulta": agendar_teleconsulta,
        "criar_perfil_paciente": criar_perfil_paciente,
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

def agente_checkup(
    mensagem: str,
    historico: list[dict],
    beneficiario_id: str = "GABRIEL",
) -> dict:
    """Conduz coleta de FRCV e orientação preventiva. Não prescreve."""
    system = SYSTEM_PROMPT_CHECKUP + f"\n\nBENEFICIÁRIO ATIVO: {beneficiario_id}"

    # RAG estruturado — categorias relevantes para check-up
    contexto_rag, documentos_rag = recuperar_contexto_detalhado(
        query=mensagem,
        n_resultados=2,
        filtro_categoria=["cartilha", "protocolo", "especialidades"],
        usar_mmr=True,
        usar_auto_rag=True,
        usar_reranker=False,  # latência baixa em checkup
    )
    if contexto_rag:
        system += f"\n\n{contexto_rag}"

    mensagens = formatar_mensagens(system, historico, mensagem)

    # Thinking OFF: checkup é mais conversacional e prioriza latência.
    resposta = chat(
        messages=mensagens,
        tools=_TOOLS_CHECKUP,
        enable_thinking=False,
        temperature=0.3,
    )

    tools_chamadas = []

    # Loop de tool-calling: LLM pode encadear N tools antes da resposta final.
    while resposta.get("tool_calls"):
        for tc in resposta["tool_calls"]:
            nome = tc["name"]
            argumentos = json.loads(tc["arguments"])
            print(f"[checkup] Chamando tool: {nome}({argumentos})")
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
            tools=_TOOLS_CHECKUP,
            enable_thinking=False,
            temperature=0.3,
        )

    return {
        "resposta": resposta["content"],
        "agente": "checkup",
        "tools_chamadas": tools_chamadas,
        "documentos_rag": documentos_rag,
        "usage": resposta["usage"],
    }
