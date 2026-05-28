"""
Agente Supervisor (anteriormente "router")
Classifica a intenção do usuário e decide qual agente acionar.
thinking=OFF — prioridade em latência mínima.

REFATORADO Sprint 2:
- Renomeado conceitualmente para 'supervisor' (mantém função 'rotear' para compat)
- System prompt carregado de prompts/agente_supervisor.md
- Intent 'prescricao' adicionada para o novo agente
- Função 'supervisionar' adiciona lógica estatal (forçar triagem se RED_FLAG persistir)

REFATORADO Fase 3 (post-merge, bugfix #1):
- Extrator robusto de JSON (_extrair_json) tolera preâmbulo/pós-âmbulo do LLM
- Validação Pydantic (IntentClassification) garante intent + confianca válidos
- Retry com até 3 tentativas antes do fallback (reduz fallback indevido de ~33% para <5%)
- Contrato uniforme: todos os retornos têm _fallback (False=deliberado, True=erro de parsing)
- Fallback estruturado carrega _fallback=True e _motivo_fallback para diagnóstico
- 14 testes determinísticos em tests/test_supervisor_robusto.py
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.llm.qwen_client import chat, formatar_mensagens
from src.prompts import carregar_prompt

# ---- config -------------------------------------------------------------

log = logging.getLogger(__name__)

# System prompt agora vem do arquivo prompts/agente_supervisor.md
SYSTEM_PROMPT_SUPERVISOR = carregar_prompt("agente_supervisor")

_INTENTS_VALIDAS = {"checkup", "triagem", "suporte", "prescricao", "fora_de_escopo"}


# ---- extração robusta de JSON (Fase 3) ----------------------------------

def _extrair_json(texto: str) -> str:
    """
    Extrai o primeiro objeto JSON balanceado de uma string que pode ter
    texto extra antes/depois.

    LLMs frequentemente emitem preâmbulos ("Aqui está minha classificação:")
    ou pós-âmbulos ("Espero ter ajudado!") junto com o JSON. Esta função
    isola apenas o objeto JSON balanceado, respeitando strings literais que
    podem conter caracteres { ou } sem confundir o balanço de chaves.

    Args:
        texto: Texto bruto retornado pelo LLM.

    Returns:
        Substring contendo APENAS o objeto JSON balanceado.

    Raises:
        ValueError: se nenhum objeto JSON balanceado for encontrado.
    """
    texto_limpo = texto.strip()

    # Caso simples: já é JSON puro
    if texto_limpo.startswith("{") and texto_limpo.endswith("}"):
        return texto_limpo

    # Caso geral: localizar primeiro { e balancear chaves respeitando strings
    inicio = texto.find("{")
    if inicio == -1:
        raise ValueError(f"Nenhum '{{' encontrado em: {texto[:200]!r}")

    nivel = 0
    em_string = False
    escape = False

    for i in range(inicio, len(texto)):
        c = texto[i]

        if escape:
            escape = False
            continue

        if c == "\\":
            escape = True
            continue

        if c == '"':
            em_string = not em_string
            continue

        if em_string:
            continue

        if c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio:i + 1]

    raise ValueError(f"JSON não balanceado em: {texto[:200]!r}")


# ---- validação Pydantic (Fase 3) ----------------------------------------

class IntentClassification(BaseModel):
    """Saída validada do supervisor — garante intent + confianca consistentes."""

    intent: str = Field(...)
    confianca: float = Field(..., ge=0.0, le=1.0)

    @field_validator("intent")
    @classmethod
    def intent_em_whitelist(cls, v: str) -> str:
        if v not in _INTENTS_VALIDAS:
            raise ValueError(
                f"Intent inválida: {v!r}. "
                f"Esperado: {sorted(_INTENTS_VALIDAS)}"
            )
        return v


# ---- chamada LLM extraída para ser mockável em testes (Fase 3) ----------

def _llm_classify(mensagem: str, historico: list[dict] | None = None) -> str:
    """
    Chamada bruta ao LLM para classificação de intent.

    Extraída como função separada para permitir mock nos testes
    determinísticos. Retorna o conteúdo cru da resposta (texto que pode
    ter JSON + preâmbulo/pós-âmbulo, ou estar completamente malformado).
    """
    historico = historico or []
    mensagens = formatar_mensagens(
        system_prompt=SYSTEM_PROMPT_SUPERVISOR,
        historico=historico,
        mensagem_usuario=mensagem,
    )
    resposta = chat(
        messages=mensagens,
        enable_thinking=False,
        temperature=0.1,
    )
    return resposta["content"]


# ---- retry com extração + validação (Fase 3) ----------------------------

def _classificar_intent_com_retry(
    mensagem: str,
    historico: list[dict] | None = None,
    max_tentativas: int = 3,
) -> dict:
    """
    Tenta classificar intent até `max_tentativas` antes do fallback.

    Em cada tentativa:
      1. Chama o LLM (_llm_classify).
      2. Extrai JSON balanceado tolerando preâmbulo/pós-âmbulo (_extrair_json).
      3. Valida estrutura e whitelist com Pydantic (IntentClassification).

    Falhas em qualquer etapa disparam nova tentativa. Esgotadas as
    tentativas, retorna fallback estruturado com flag `_fallback=True`
    para diagnóstico.

    Contrato uniforme do retorno:
      - sucesso: _fallback=False (classificação deliberada do LLM)
      - fallback: _fallback=True + _motivo_fallback=<str> (erro de parsing)

    Returns:
        dict com chaves: intent, confianca, motivo, _fallback (sempre presente).
        Em caso de fallback, inclui também _motivo_fallback.
    """
    ultimo_erro: Exception | None = None
    ultima_resposta: str | None = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            resposta_bruta = _llm_classify(mensagem, historico)
            ultima_resposta = resposta_bruta

            json_limpo = _extrair_json(resposta_bruta)
            dados_brutos = json.loads(json_limpo)
            validado = IntentClassification(**dados_brutos)

            return {
                "intent": validado.intent,
                "confianca": validado.confianca,
                "motivo": "classificacao_llm",
                "_fallback": False,
            }

        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            ultimo_erro = e
            log.warning(
                "Supervisor parse falhou (tentativa %d/%d): %s: %s. "
                "Resposta bruta (200ch): %r",
                tentativa, max_tentativas, type(e).__name__, e,
                ultima_resposta[:200] if ultima_resposta else None,
            )
            continue

        except Exception as e:
            # Erro inesperado — log e tenta de novo
            ultimo_erro = e
            log.warning(
                "Supervisor erro inesperado (tentativa %d/%d): %s: %s",
                tentativa, max_tentativas, type(e).__name__, e,
            )
            continue

    # Esgotou tentativas — fallback estruturado
    log.error(
        "Supervisor falhou em %d tentativas. Último erro: %s: %s. "
        "Última resposta (200ch): %r. Caindo para fallback intent=triagem.",
        max_tentativas,
        type(ultimo_erro).__name__ if ultimo_erro else "?",
        ultimo_erro,
        ultima_resposta[:200] if ultima_resposta else None,
    )
    # Print legado mantido para compat visual com smoke tests pré-existentes
    print(
        f"[supervisor] Erro na classificação: {ultimo_erro}. "
        f"Usando fallback: triagem"
    )
    return {
        "intent": "triagem",
        "confianca": 0.5,
        "motivo": "fallback_erro_parsing",
        "_fallback": True,
        "_motivo_fallback": str(ultimo_erro),
    }


# ---- classificação base (sem estado) ------------------------------------

def rotear(mensagem: str, historico: list[dict] | None = None) -> dict:
    """
    Classifica a intenção do usuário (função base, sem lógica estatal).

    Args:
        mensagem: Mensagem atual do usuário.
        historico: Turnos anteriores da conversa.

    Returns:
        Dicionário com intent, confianca, motivo e _fallback.
        Em caso de erro persistente (após 3 tentativas), retorna intent
        triagem como fallback (mais seguro que checkup quando há ambiguidade
        — ativa thinking + RAG completo) com flags _fallback=True e
        _motivo_fallback para diagnóstico.
    """
    return _classificar_intent_com_retry(mensagem, historico)


# ---- supervisor com lógica estatal --------------------------------------

def supervisionar(
    mensagem: str,
    historico: list[dict] | None = None,
    flags_safety_anteriores: list[str] | None = None,
) -> dict:
    """
    Versão completa do supervisor com lógica estatal.

    Diferenças vs rotear():
    - Se RED_FLAG_SEM_ESCALADA persistiu do turno anterior, força triagem.
    - Pode aplicar outras regras de escalada baseadas em estado acumulado.

    Contrato uniforme de _fallback:
      _fallback=False → classificação DELIBERADA (LLM bem-sucedido OU escalada
                        explícita por RED_FLAG persistente).
      _fallback=True  → falha de parsing após N retries (baixa confiança).
    Consumers devem usar r.get("_fallback") para diferenciar.

    Args:
        mensagem: Mensagem atual.
        historico: Turnos anteriores.
        flags_safety_anteriores: Flags da safety do turno N-1.

    Returns:
        {"intent": str, "confianca": float, "motivo": str, "_fallback": bool}
    """
    flags = flags_safety_anteriores or []

    # Escalada persistente: RED_FLAG não resolvido → força triagem
    # Classificação DELIBERADA (_fallback=False), não falha de parsing.
    if "RED_FLAG_SEM_ESCALADA" in flags:
        return {
            "intent": "triagem",
            "confianca": 1.0,
            "motivo": "escalada_persistente_red_flag",
            "_fallback": False,
        }

    # Caso normal: classifica via LLM (agora com retry interno)
    return rotear(mensagem, historico)
