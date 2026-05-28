"""
Tool: analisar_ritmo_cardiaco

EVOLUÇÃO POS-MERGE:
- Sprint 1: lógica determinística mockada (regra batimentos_anormais → status).
- Sprint 2: idem.
- Sprint 3 (este arquivo): se `paciente_id` for fornecido, lê telemetria
  REAL do dashboard (cardiac_data.csv via shared.telemetry_store) e gera
  um relatório completo com janela + observação contextualizada.

Backward compatibility:
- A assinatura legada (apenas parâmetros IBI/BPM/desvio sem paciente_id)
  continua funcionando. Os 4 arquivos pytest existentes não quebram.
- O `paciente_id` é opcional e é o ÚNICO parâmetro novo.

Fluxo de decisão:
    paciente_id presente E telemetria existe  → modo "live" (preferido)
    paciente_id presente E telemetria ausente → modo "live" com mensagem clara de erro
    sem paciente_id, mas IBI presente         → modo "manual" (legado mock)
    nada                                       → erro
"""
from __future__ import annotations

from typing import Any, Optional

# Import opcional para permitir testes da lógica mock sem ter o shared/ no path
try:
    from shared.telemetry_store import latest_beat, window_summary
    from shared.patient_registry import get_patient
    _SHARED_DISPONIVEL = True
except ImportError:
    _SHARED_DISPONIVEL = False


def analisar_ritmo_cardiaco(
    paciente_id: Optional[str] = None,
    # Parâmetros legados — continuam aceitos para compat
    timestamp_s: Optional[float] = None,
    IBI_ms: Optional[float] = None,
    BPM: Optional[float] = None,
    media_IBI: Optional[float] = None,
    desvio_medio: Optional[float] = None,
    batimentos_anormais: Optional[int] = None,
    # Configuração da janela quando em modo live
    janela_min: int = 5,
) -> dict[str, Any]:
    """
    Analisa ritmo cardíaco do paciente.

    Modo preferido (live):
        analisar_ritmo_cardiaco(paciente_id="GABRIEL")
        → puxa último batimento + sumário dos últimos 5 min do CardioMonitor.

    Modo legado (mock):
        analisar_ritmo_cardiaco(
            timestamp_s=10.0, IBI_ms=820, BPM=73,
            media_IBI=815, desvio_medio=18, batimentos_anormais=1,
        )
        → classifica via regra determinística (Sprint 1).

    Returns:
        dict com 'classificacao' (regular | atencao | irregular),
        'observacao' em português, e — no modo live — sumário da janela.
    """
    # ---- modo live (preferido) ----
    if paciente_id and _SHARED_DISPONIVEL:
        return _modo_live(paciente_id, janela_min=janela_min)

    # ---- modo legado (compat) ----
    if batimentos_anormais is not None:
        return _modo_mock(
            timestamp_s=timestamp_s or 0.0,
            IBI_ms=IBI_ms or 0.0,
            BPM=BPM or 0.0,
            media_IBI=media_IBI or 0.0,
            desvio_medio=desvio_medio or 0.0,
            batimentos_anormais=batimentos_anormais,
        )

    return {
        "erro": "Forneça paciente_id (modo live) ou os parâmetros IBI "
                "completos (modo manual).",
        "modos_suportados": ["live", "manual"],
    }


# =============================================================================
# Modo live — usa dashboard
# =============================================================================

def _modo_live(paciente_id: str, *, janela_min: int) -> dict[str, Any]:
    beat = latest_beat(paciente_id)
    if beat is None:
        return {
            "paciente_id": paciente_id,
            "telemetria_disponivel": False,
            "erro": "Sem leituras de PPG no CardioMonitor para este paciente.",
            "sugestao": ("Abra a página /monitor, selecione o paciente e "
                         "inicie uma sessão (simulação ou ESP32 ao vivo)."),
        }

    sumario = window_summary(paciente_id, minutes=janela_min)
    classificacao = _classificar_janela(sumario)
    perfil = get_patient(paciente_id) or {}

    return {
        "fonte": "dashboard_csv_live",
        "paciente_id": paciente_id,
        "ultimo_batimento": beat,
        "janela": sumario,
        "classificacao": classificacao,
        "observacao": _observacao_contextualizada(
            beat=beat, sumario=sumario, perfil=perfil,
            classificacao=classificacao,
        ),
        "perfil_considerado": {
            "idade": perfil.get("idade"),
            "sexo": perfil.get("sexo"),
            "condicoes": [c.get("nome") for c in perfil.get("condicoes_ativas", [])],
            "score_risco": perfil.get("score_risco_cardiovascular"),
        },
    }


def _classificar_janela(sumario: dict[str, Any]) -> str:
    """Classificação baseada na janela inteira, não em um batimento isolado."""
    if not sumario.get("telemetria_disponivel"):
        return "indisponivel"
    irr = sumario.get("irregulares_pct", 0)
    att = sumario.get("atencao_pct", 0)
    if irr >= 20 or sumario.get("ultimo_status") == "irregular":
        return "irregular"
    if irr + att >= 10:
        return "atencao"
    return "regular"


def _observacao_contextualizada(
    *,
    beat: dict[str, Any],
    sumario: dict[str, Any],
    perfil: dict[str, Any],
    classificacao: str,
) -> str:
    """Gera observação humana considerando o perfil do paciente."""
    bpm = beat.get("BPM", 0)
    idade = perfil.get("idade")
    condicoes_str = ", ".join(
        c.get("nome", "") for c in perfil.get("condicoes_ativas", [])
    ) or "sem condições ativas registradas"

    irr_pct = sumario.get("irregulares_pct", 0)
    janela = sumario.get("janela_min", 5)

    partes = []

    # Linha 1 — diagnóstico curto
    if classificacao == "irregular":
        partes.append(
            f"Variabilidade ALTA: {irr_pct}% dos batimentos na janela "
            f"de {janela}min foram irregulares."
        )
    elif classificacao == "atencao":
        partes.append(
            f"Variabilidade limítrofe ({irr_pct}% irregulares + "
            f"{sumario.get('atencao_pct', 0)}% em atenção)."
        )
    else:
        partes.append(
            f"Ritmo dentro do esperado. BPM médio "
            f"{sumario.get('bpm_medio', '-')} na janela de {janela}min."
        )

    # Linha 2 — BPM zona
    zona = _zona_bpm(bpm)
    if zona != "normal":
        partes.append(f"Atual: {bpm:.0f} BPM ({zona}).")

    # Linha 3 — contexto do perfil
    if idade is not None:
        partes.append(f"Paciente {idade}a — {condicoes_str}.")

    # Linha 4 — recomendação
    if classificacao == "irregular":
        partes.append(
            "Recomenda-se avaliação médica. "
            "Se houver dor torácica, dispneia ou síncope: SAMU 192."
        )
    elif classificacao == "atencao":
        partes.append("Monitoramento contínuo recomendado.")

    # Linha 5 — disclaimer (sempre que não for ritmo regular)
    if classificacao != "regular":
        partes.append(
            "Estimativa baseada em PPG (sensor óptico), não substitui ECG "
            "nem avaliação clínica presencial."
        )

    return " ".join(partes)


def _zona_bpm(bpm: float) -> str:
    if bpm < 50:
        return "bradicardia severa"
    if bpm < 60:
        return "bradicardia"
    if bpm <= 100:
        return "normal"
    if bpm <= 120:
        return "taquicardia leve"
    if bpm <= 150:
        return "taquicardia moderada"
    return "taquicardia severa"


# =============================================================================
# Modo mock — mantém o comportamento original Sprint 1 para backward compat
# =============================================================================

def _modo_mock(
    *,
    timestamp_s: float,
    IBI_ms: float,
    BPM: float,
    media_IBI: float,
    desvio_medio: float,
    batimentos_anormais: int,
) -> dict[str, Any]:
    """Lógica determinística original — não tocar, há testes pytest contra ela."""
    if not (0 <= batimentos_anormais <= 5):
        return {"erro": "batimentos_anormais deve ser entre 0 e 5."}

    if batimentos_anormais <= 1:
        classificacao = "regular"
        observacao = (
            "Ritmo sinusal regular. "
            "Variabilidade dentro dos parâmetros fisiológicos normais."
        )
    elif batimentos_anormais <= 3:
        classificacao = "regular"
        observacao = (
            f"{batimentos_anormais} de 5 batimentos com variação detectada. "
            "Dentro do limiar aceitável. Monitoramento contínuo recomendado."
        )
    else:
        classificacao = "irregular"
        observacao = (
            f"Irregularidade detectada. {batimentos_anormais} de 5 registros "
            "classificados como anormais. Alta variabilidade de IBI. "
            "Recomenda avaliação médica. "
            "Se houver dor torácica, dispneia ou síncope: SAMU 192. "
            "Estimativa baseada em PPG (sensor óptico), não substitui ECG "
            "nem avaliação clínica presencial."
        )

    return {
        "fonte": "mock_manual",
        "timestamp_s": timestamp_s,
        "IBI_ms": IBI_ms,
        "BPM": BPM,
        "media_IBI": media_IBI,
        "desvio_medio": desvio_medio,
        "batimentos_anormais": batimentos_anormais,
        "classificacao": classificacao,
        "observacao": observacao,
        "nota": "Modo manual — sem telemetria do dashboard.",
    }
