"""
Testes determinísticos do supervisor robusto (Fase 3 — bug #1).

Validam extração de JSON, validação Pydantic, retry e fallback.
Determinísticos — usam mock para `_llm_classify` para evitar chamada
real ao DashScope. 14 testes total:
  - TestExtrairJSON: 7 testes
  - TestIntentClassification: 3 testes
  - TestRetry: 4 testes
"""
import json

import pytest
from pydantic import ValidationError
from unittest.mock import patch

from src.agents.router import (
    _classificar_intent_com_retry,
    _extrair_json,
    IntentClassification,
)


# =============================================================================
# TestExtrairJSON — extração robusta de JSON do output do LLM
# =============================================================================

class TestExtrairJSON:
    """Extração robusta de JSON do output cru do LLM."""

    def test_json_puro(self):
        """JSON sem texto extra (caso ideal)."""
        entrada = '{"intent": "checkup", "confianca": 0.9}'
        assert _extrair_json(entrada) == entrada

    def test_json_com_preambulo(self):
        """JSON precedido de texto (caso comum em LLMs verbosos)."""
        entrada = 'Claro! Aqui está: {"intent": "checkup", "confianca": 0.9}'
        esperado = '{"intent": "checkup", "confianca": 0.9}'
        assert _extrair_json(entrada) == esperado

    def test_json_com_posambulo(self):
        """JSON seguido de texto de despedida."""
        entrada = '{"intent": "checkup", "confianca": 0.9}\n\nEspero ter ajudado!'
        esperado = '{"intent": "checkup", "confianca": 0.9}'
        assert _extrair_json(entrada) == esperado

    def test_json_aninhado(self):
        """Objetos JSON aninhados (chaves dentro de chaves)."""
        entrada = 'Resposta: {"intent": "checkup", "meta": {"x": 1, "y": 2}}'
        esperado = '{"intent": "checkup", "meta": {"x": 1, "y": 2}}'
        assert _extrair_json(entrada) == esperado

    def test_json_com_strings_contendo_chaves(self):
        """String dentro do JSON contém { ou } — não deve confundir o parser."""
        entrada = '{"intent": "checkup", "msg": "literal { com chaves }"}'
        assert _extrair_json(entrada) == entrada

    def test_sem_json(self):
        """Texto sem '{' deve levantar ValueError com mensagem clara."""
        with pytest.raises(ValueError, match="Nenhum"):
            _extrair_json("não tem json aqui de jeito nenhum")

    def test_json_nao_balanceado(self):
        """JSON com chave aberta mas sem fechar (LLM truncado)."""
        with pytest.raises(ValueError, match="não balanceado"):
            _extrair_json('{"intent": "checkup"')


# =============================================================================
# TestIntentClassification — validação Pydantic da saída do supervisor
# =============================================================================

class TestIntentClassification:
    """Validação Pydantic da saída do supervisor."""

    def test_intent_valida(self):
        """Intent na whitelist + confianca em range → cria objeto OK."""
        ic = IntentClassification(intent="checkup", confianca=0.9)
        assert ic.intent == "checkup"
        assert ic.confianca == 0.9

    def test_intent_invalida(self):
        """Intent fora da whitelist deve levantar ValidationError."""
        with pytest.raises(ValidationError):
            IntentClassification(intent="INTENT_INEXISTENTE_PROPOSITAL", confianca=0.9)

    def test_confianca_fora_do_range(self):
        """Confianca > 1 ou < 0 deve levantar ValidationError."""
        with pytest.raises(ValidationError):
            IntentClassification(intent="checkup", confianca=1.5)
        with pytest.raises(ValidationError):
            IntentClassification(intent="checkup", confianca=-0.1)


# =============================================================================
# TestRetry — orquestração de retry e fallback do supervisor
# =============================================================================

class TestRetry:
    """Retry e fallback do supervisor."""

    @patch("src.agents.router._llm_classify")
    def test_sucesso_primeira_tentativa(self, mock_llm):
        """LLM responde JSON válido na 1ª chamada → retorna direto, sem retry."""
        mock_llm.return_value = '{"intent": "checkup", "confianca": 0.9}'
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "checkup"
        assert r["confianca"] == 0.9
        assert r["motivo"] == "classificacao_llm"
        assert r["_fallback"] is False
        mock_llm.assert_called_once()

    @patch("src.agents.router._llm_classify")
    def test_retry_recupera_apos_falha(self, mock_llm):
        """1ª e 2ª chamadas falham, 3ª retorna JSON válido → sucesso."""
        mock_llm.side_effect = [
            "isso aqui não é json nenhum",       # tentativa 1 → ValueError
            "ainda não é {ops",                   # tentativa 2 → ValueError (JSON não balanceado)
            '{"intent": "checkup", "confianca": 0.85}',  # tentativa 3 → OK
        ]
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "checkup"
        assert r["confianca"] == 0.85
        assert r["_fallback"] is False
        assert mock_llm.call_count == 3

    @patch("src.agents.router._llm_classify")
    def test_fallback_apos_tentativas_esgotadas(self, mock_llm):
        """Todas as tentativas falham → fallback estruturado."""
        mock_llm.return_value = "lixo permanente sem json"
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "triagem"
        assert r["confianca"] == 0.5
        assert r["motivo"] == "fallback_erro_parsing"
        assert r["_fallback"] is True
        assert "_motivo_fallback" in r
        assert mock_llm.call_count == 3

    @patch("src.agents.router._llm_classify")
    def test_fallback_em_intent_invalida(self, mock_llm):
        """JSON válido mas intent fora da whitelist → ValidationError → fallback após 3 tentativas."""
        # P1: side_effect explicito com 3 chamadas (documenta a expectativa)
        resposta_invalida = '{"intent": "INTENT_INEXISTENTE_PROPOSITAL", "confianca": 0.9}'
        mock_llm.side_effect = [resposta_invalida] * 3

        r = _classificar_intent_com_retry("oi")

        assert r["intent"] == "triagem"
        assert r["_fallback"] is True
        assert "_motivo_fallback" in r
        assert mock_llm.call_count == 3
