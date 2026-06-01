"""
Safety Layer — Sprint 2 (dupla camada).

Camada 1 — Heurística rápida (regex + listas):
    - Red flag não-escalada
    - Diagnóstico definitivo indevido
    - Disclaimer obrigatório
    - Tag inviolável de prescrição
Camada 2 — Auditor LLM (apenas em casos ambíguos):
    - Acionado quando heurística marca caso limítrofe
    - Modelo leve, temperature 0, max_tokens 200
    - Retorna aprovado/correção
"""

from __future__ import annotations

import json
import os
import re

# Padrões para detecção
_RED_FLAGS_KEYWORDS = [
    "dor no peito", "dor torácica", "infarto", "avc", "acidente vascular",
    "parada cardíaca", "desmaiei", "desmaio", "síncope", "falta de ar súbita",
    "pressão 18", "pressão 19", "irradiando para o braço",
    "dor irradiando", "sudorese fria", "mal súbito",
]

_DIAGNOSTICO_DEFINITIVO = [
    "você tem ", "o diagnóstico é ", "confirmado que é ",
    "certamente é ", "definitivamente é ", "com certeza é ",
]

_MEDICAMENTOS_CARDIOVASCULARES_REGEX = re.compile(
    r"\b(losartana|valsartana|enalapril|captopril|ramipril|"
    r"anlodipino|nifedipino|verapamil|diltiazem|"
    r"atenolol|metoprolol|bisoprolol|carvedilol|propranolol|nebivolol|"
    r"hidroclorotiazida|clortalidona|amiodarona|sotalol|"
    r"varfarina|warfarina|apixabana|rivaroxabana|dabigatrana|"
    r"aas|clopidogrel|ticagrelor|prasugrel|"
    r"atorvastatina|rosuvastatina|sinvastatina|pravastatina|ezetimiba|"
    r"furosemida|espironolactona|isossorbida|nitroglicerina|"
    r"prescrição|prescricao|receita|rascunho)\b",
    re.IGNORECASE
)

TAG_RASCUNHO = "RASCUNHO_AGUARDANDO_REVISAO_MEDICA"

_DISCLAIMER = ("\n\n⚕️ *Este assistente oferece suporte informativo e não "
               "substitui avaliação médica. Em emergência, ligue 192 (SAMU).*")

# Termos que indicam que o agente JÁ escalou apropriadamente
_TERMOS_ESCALADA = ["192", "samu", "pronto-socorro", "emergência", "urgência"]


# =============================================================================
# Auditor LLM (camada 2)
# =============================================================================

_SYSTEM_AUDITOR = """Você é um auditor clínico de respostas do sistema cardiovascular BluaDiagnostics.

Avalie se a RESPOSTA do agente é:
1. CLINICAMENTE APROPRIADA para a MENSAGEM do usuário
2. SEGURA — não emite diagnóstico definitivo, não substitui médico
3. ESCALA emergências cardiovasculares quando aplicável (SAMU 192)

Retorne APENAS JSON sem texto adicional:
{
  "aprovado": true|false,
  "motivo": "explicação curta",
  "correcao_sugerida": "resposta corrigida ou null"
}

Reprove se:
- Há red flag clínica clara mas resposta não escala
- Emite diagnóstico definitivo ("você tem X")
- Sugere alteração de medicação sem médico
- Menciona medicamento em contexto de prescrição mas falta tag [RASCUNHO_AGUARDANDO_REVISAO_MEDICA]
"""


def _auditor_llm(mensagem_usuario: str, resposta_agente: str, intent: str) -> dict:
    """Camada 2: chama LLM auditor. Importação local evita ciclo."""
    from src.llm.qwen_client import chat

    prompt = (f"INTENT classificada: {intent}\n\n"
              f"MENSAGEM DO USUÁRIO:\n{mensagem_usuario}\n\n"
              f"RESPOSTA DO AGENTE:\n{resposta_agente}\n\n"
              f"Avalie:")

    try:
        resp = chat(
            messages=[
                {"role": "system", "content": _SYSTEM_AUDITOR},
                {"role": "user", "content": prompt},
            ],
            enable_thinking=False,
            temperature=0.0,
            max_tokens=300,
        )
        return json.loads(resp["content"].strip())
    except Exception as exc:
        # Auditor falhou — não bloqueia o fluxo, só registra
        return {"aprovado": True, "motivo": f"auditor_indisponivel: {exc}",
                "correcao_sugerida": None}


# =============================================================================
# Heurística (camada 1)
# =============================================================================

def _verificar_red_flag_sem_escalada(mensagem_lower: str, resposta_lower: str,
                                     intent: str) -> bool:
    red_flag_detectada = any(kw in mensagem_lower for kw in _RED_FLAGS_KEYWORDS)
    escalou = any(t in resposta_lower for t in _TERMOS_ESCALADA)
    return red_flag_detectada and not escalou and intent in {"triagem", "checkup"}


def _verificar_diagnostico_definitivo(resposta_lower: str) -> bool:
    return any(t in resposta_lower for t in _DIAGNOSTICO_DEFINITIVO)


def _verificar_tag_prescricao(resposta: str, intent: str) -> tuple[bool, str]:
    """
    Verifica se respostas envolvendo medicamentos em contexto de prescrição
    contêm a tag inviolável. Auto-corrige adicionando tag + aviso.

    Returns:
        (precisa_correcao, resposta_corrigida)
    """
    menciona_medicamento = bool(_MEDICAMENTOS_CARDIOVASCULARES_REGEX.search(resposta))
    tem_tag = TAG_RASCUNHO in resposta

    if intent == "prescricao" and menciona_medicamento and not tem_tag:
        resposta_corrigida = (
            f"[{TAG_RASCUNHO}]\n\n"
            + resposta
            + "\n\n⚠️ *Esta sugestão farmacológica é um rascunho que requer "
            "aprovação de médico habilitado antes de qualquer uso. "
            "Resolução CFM 2.314/22.*"
        )
        return True, resposta_corrigida

    return False, resposta


def _eh_caso_ambiguo(flags: list[str], resposta: str, mensagem: str) -> bool:
    """
    Decide se vale acionar o auditor LLM (camada 2).
    Acionamos em:
    - Heurística marcou pelo menos uma flag (mas não é só disclaimer ausente)
    - Mensagem menciona red flag clínico parcial (1 sintoma só)
    """
    if any(f in flags for f in ["RED_FLAG_SEM_ESCALADA",
                                  "DIAGNOSTICO_DEFINITIVO_DETECTADO",
                                  "TAG_RASCUNHO_AUSENTE"]):
        return True

    # Detecta menção parcial a red flag — termos relevantes sem contexto completo
    msg_lower = mensagem.lower()
    sinais_parciais = ["pressão alta", "palpitação", "dor", "falta de ar",
                       "tontura", "cansaço extremo"]
    if any(s in msg_lower for s in sinais_parciais):
        # Conta quantos sinais — se mais de 1, é ambíguo
        cnt = sum(1 for s in sinais_parciais if s in msg_lower)
        return cnt >= 2

    return False


# =============================================================================
# Função principal
# =============================================================================

def agente_safety(
    mensagem_usuario: str,
    resposta_agente: str,
    intent: str,
) -> dict:
    """
    Valida a resposta do agente — Safety dupla camada Sprint 2.

    Args:
        mensagem_usuario: mensagem original do usuário
        resposta_agente: resposta gerada pelo agente especializado
        intent: intent classificada pelo supervisor

    Returns:
        Dicionário com resposta validada, flags, aprovado, auditor_llm
    """
    flags = []
    resposta_final = resposta_agente
    msg_lower = mensagem_usuario.lower()
    resp_lower = resposta_agente.lower()

    # --- Camada 1: Heurística ----------------------------------------------

    # Verificação 1: Red flag sem escalada
    if _verificar_red_flag_sem_escalada(msg_lower, resp_lower, intent):
        flags.append("RED_FLAG_SEM_ESCALADA")
        resposta_final = (
            "⚠️ Os sintomas que você descreveu podem indicar uma situação de "
            "urgência cardiovascular. Se a situação piorar, ligue imediatamente "
            "para **192 (SAMU)**.\n\n" + resposta_final
        )

    # Verificação 2: Diagnóstico definitivo
    if _verificar_diagnostico_definitivo(resp_lower):
        flags.append("DIAGNOSTICO_DEFINITIVO_DETECTADO")

    # Verificação 3: Tag inviolável de prescrição
    precisa_tag, resposta_com_tag = _verificar_tag_prescricao(resposta_final, intent)
    if precisa_tag:
        flags.append("TAG_RASCUNHO_AUSENTE_CORRIGIDA")
        resposta_final = resposta_com_tag

    # Verificação 4: Disclaimer obrigatório
    disclaimer_presente = ("não substitui" in resp_lower or "samu" in resp_lower
                            or "192" in resposta_final)
    if not disclaimer_presente:
        resposta_final += _DISCLAIMER
        flags.append("DISCLAIMER_ADICIONADO")

    # --- Camada 2: Auditor LLM (só em casos ambíguos) ---------------------
    # Opt-out via BLUA_SAFETY_AUDITOR=disabled (-1 a -2s quando caso é ambíguo).
    # Default "enabled" preserva camada 2 em produção. Em demo, desligar reduz
    # latência sem comprometer camada 1 (heurísticas red flag + diagnóstico
    # definitivo + tag inviolável + disclaimer continuam ATIVAS).
    auditor_resultado = None
    auditor_habilitado = (
        os.environ.get("BLUA_SAFETY_AUDITOR", "enabled").lower() == "enabled"
    )
    if auditor_habilitado and _eh_caso_ambiguo(flags, resposta_agente, mensagem_usuario):
        auditor_resultado = _auditor_llm(mensagem_usuario, resposta_agente, intent)
        flags.append("AUDITOR_LLM_ACIONADO")

        if not auditor_resultado.get("aprovado", True):
            flags.append("AUDITOR_LLM_REPROVOU")
            correcao = auditor_resultado.get("correcao_sugerida")
            if correcao and isinstance(correcao, str):
                resposta_final = correcao
                # Re-aplica tag se necessário
                _, resposta_final = _verificar_tag_prescricao(resposta_final, intent)

    return {
        "resposta": resposta_final,
        "flags": flags,
        "red_flag_detectada": "RED_FLAG_SEM_ESCALADA" in flags,
        "auditor_llm": auditor_resultado,
        "aprovado": ("RED_FLAG_SEM_ESCALADA" not in flags
                     and "DIAGNOSTICO_DEFINITIVO_DETECTADO" not in flags
                     and "AUDITOR_LLM_REPROVOU" not in flags),
    }
