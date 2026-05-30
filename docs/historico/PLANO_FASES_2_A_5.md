# PLANO_FASES_2_A_5.md

**Pré-requisito:** Fase 1 concluída — hipótese consolidada de anchoring (nome) + viés clínico (perfil CV arquétipo).

**Branch:** `feature/fix-bugs-passo-7`
**Tempo total estimado:** 1h55-2h10 (Fase 2: 20min + Fase 3: 45-60min + Fase 4: 30min + Fase 5: 20min).
**Risco geral:** baixo — todas as mudanças são aditivas; nenhuma remove funcionalidade.

---

## Sumário

| Fase | Objetivo | Tempo | Toca código? |
|------|----------|-------|--------------|
| 2 | Sanitizar nomes literais no supervisor | 20min | Só system prompt |
| 3 | Estabilizar supervisor (retry + Pydantic + testes) | 45-60min | Sim, código Python |
| 4 | Guardas no triagem (bug #2) + checkup (bug #3) | 30min | Só system prompts |
| 5 | Validação end-to-end + merge pra main | 20min | Nenhuma |

**Regra de ouro:** validação falhou → para, reporta, espera. Não "consertar e seguir".

---

## FASE 2 — Sanitização do supervisor

### 2.1 Objetivo
Eliminar nomes literais dos exemplos no system prompt do supervisor, substituindo por placeholders `<NOME>`, `<IDADE>`, `<SEXO>`, `<CONDICAO>`. Reduz anchoring textual em outros agents que veem o contexto.

### 2.2 Arquivo
System prompt do supervisor. Localizar:
```bash
grep -rn "João Silva\|Pedro Lima" src/ --include="*.py" --include="*.md" --include="*.txt"
```

O resultado vai apontar pro arquivo correto — provavelmente `src/agents/supervisor.py` ou um arquivo de prompt separado (`prompts/supervisor.md`, etc.).

### 2.3 Diff

**Mudança principal:**

```diff
 ## Exemplos de classificação

-**Usuário**: "Quero me cadastrar: João Silva, 45 anos, masculino, com hipertensão"
+**Usuário**: "Quero me cadastrar: <NOME>, <IDADE> anos, <SEXO>, com <CONDICAO>"
 → `{"intent": "checkup", "confianca": 0.96}`

-**Usuário**: "Pode criar um perfil novo? Sou Pedro Lima, 60 anos, com fibrilação atrial."
+**Usuário**: "Pode criar um perfil novo? Sou <NOME>, <IDADE> anos, com <CONDICAO>."
 → `{"intent": "checkup", "confianca": 0.95}`
```

**Adicionar aviso explícito após os exemplos:**

```diff
 → `{"intent": "checkup", "confianca": 0.95}`

+**Importante:** os marcadores `<NOME>`, `<IDADE>`, `<SEXO>`, `<CONDICAO>`
+são placeholders sintáticos. Os dados reais virão do usuário em runtime
+através da mensagem que ele enviar. Você NUNCA deve preencher esses
+placeholders com valores inventados — sua única tarefa é classificar
+a intenção da mensagem, não gerar dados clínicos.
+
```

### 2.4 Validação

**2.4.1 — Conferir que não restou nome literal em lugar nenhum do supervisor:**
```bash
grep -rn "João Silva\|Pedro Lima\|Maria Silva\|José " src/ --include="*.py" --include="*.md"
# Esperado: zero resultados em arquivos do supervisor.
# (Pode aparecer em outros lugares legítimos — testes, docs antigos —
#  mas NÃO no system prompt do supervisor.)
```

**2.4.2 — Refazer experimento da Fase 1 (3 sessões com "Crie paciente fictício para teste"):**

Esperado:
- ✅ Nenhuma rodada menciona "João Silva" ou "Pedro Lima".
- ⚠️ Os outros atributos (idade 58, HAS+dislipidemia, tabagismo) podem persistir — esses vão ser tratados na Fase 4.

**2.4.3 — Pytest verde (não tocamos código de teste, mas vale conferir):**
```bash
pytest --tb=short 2>&1 | tail -5
```

### 2.5 Critério de parada
- "João Silva" ainda aparece em alguma rodada do 2.4.2 após a edição: **PARAR**. Provavelmente há outro arquivo com o nome literal que não foi sanitizado. Rodar o grep do 2.4.1 ampliado pra encontrá-lo.
- Pytest quebra: **PARAR**. Não deveria acontecer — só editamos prompt.

### 2.6 Commit
```
fix(supervisor): substitui nomes literais por placeholders nos exemplos

Exemplos do system prompt usavam "João Silva, 45 anos" e "Pedro Lima,
60 anos" — nomes que o LLM citava textualmente em respostas de outros
agents (checkup respondendo a pedido vago "Crie paciente fictício"
inventou "João Silva 58a HAS dislipidemia" — anchoring direto no nome
do exemplo do supervisor).

Substituído por <NOME>, <IDADE>, <SEXO>, <CONDICAO>. Adicionado aviso
explícito de que placeholders não devem ser preenchidos com valores
inventados pelo LLM.

Validação: 3 rodadas pós-fix do experimento "paciente fictício para
teste" — zero menções a "João Silva" / "Pedro Lima".

Atende bug #3 (parcialmente — anchoring de nome resolvido; viés
arquetípico do LLM será tratado na Fase 4).
```

---

## FASE 3 — Estabilização do supervisor

### 3.1 Objetivo
Reduzir taxa de fallback indevido pra intent `triagem` de ~33% para <5%, atacando a causa-raiz do bug #1: parser JSON sem retry, sem validação, sem tolerância a preâmbulo/pós-âmbulo do LLM.

### 3.2 Arquivo
`src/agents/supervisor.py` (ou onde estiver a lógica de classificação de intent).

Localizar:
```bash
grep -rn "json.loads\|json.JSONDecodeError\|def.*classific" src/agents/supervisor.py
```

### 3.3 Implementação em 4 camadas

#### 3.3.1 — Extrator robusto de JSON

Adicionar função utilitária no topo do arquivo (ou em `src/agents/_utils.py` se preferir):

```python
import re


def _extrair_json(texto: str) -> str:
    """
    Extrai o primeiro objeto JSON balanceado de uma string que pode ter
    texto extra antes/depois.

    LLMs frequentemente vomitam preâmbulos ("Aqui está minha classificação:")
    ou pós-âmbulos ("Espero ter ajudado!") junto com o JSON. Esta função
    isola apenas o objeto JSON.

    Raises:
        ValueError: se nenhum objeto JSON balanceado for encontrado.
    """
    texto_limpo = texto.strip()

    # Caso simples: já é JSON puro
    if texto_limpo.startswith("{") and texto_limpo.endswith("}"):
        return texto_limpo

    # Caso geral: localizar primeiro { e balancear chaves
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

        if c == '"' and not escape:
            em_string = not em_string
            continue

        if em_string:
            continue

        if c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio:i+1]

    raise ValueError(f"JSON não balanceado em: {texto[:200]!r}")
```

#### 3.3.2 — Validação Pydantic da saída

```python
from pydantic import BaseModel, Field, field_validator


_INTENTS_VALIDAS = {"checkup", "suporte", "prescricao", "triagem"}


class IntentClassification(BaseModel):
    """Saída validada do supervisor."""
    intent: str = Field(...)
    confianca: float = Field(..., ge=0.0, le=1.0)

    @field_validator("intent")
    @classmethod
    def intent_em_whitelist(cls, v: str) -> str:
        if v not in _INTENTS_VALIDAS:
            raise ValueError(
                f"Intent inválida: {v!r}. Esperado: {sorted(_INTENTS_VALIDAS)}"
            )
        return v
```

#### 3.3.3 — Retry com logging

```python
import logging

log = logging.getLogger(__name__)


def _classificar_intent_com_retry(
    mensagem: str,
    max_tentativas: int = 3,
) -> dict:
    """
    Tenta classificar intent até `max_tentativas` antes do fallback.

    Em cada tentativa:
      1. Chama o LLM (_llm_classify).
      2. Extrai JSON robustamente (_extrair_json).
      3. Valida com Pydantic (IntentClassification).

    Falhas em qualquer etapa disparam nova tentativa. Esgotadas as
    tentativas, retorna fallback estruturado com flag `_fallback=True`.
    """
    ultimo_erro = None
    ultima_resposta = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            resposta_bruta = _llm_classify(mensagem)
            ultima_resposta = resposta_bruta

            json_limpo = _extrair_json(resposta_bruta)
            dados_brutos = json.loads(json_limpo)
            validado = IntentClassification(**dados_brutos)

            return validado.model_dump()

        except (ValueError, json.JSONDecodeError) as e:
            ultimo_erro = e
            log.warning(
                f"Supervisor parse falhou (tentativa {tentativa}/{max_tentativas}): "
                f"{type(e).__name__}: {e}. "
                f"Resposta bruta: {ultima_resposta[:200] if ultima_resposta else 'None'!r}"
            )
            continue

        except Exception as e:
            # Erro inesperado — log e tenta de novo
            ultimo_erro = e
            log.warning(
                f"Supervisor erro inesperado (tentativa {tentativa}/{max_tentativas}): "
                f"{type(e).__name__}: {e}"
            )
            continue

    # Esgotou tentativas — fallback estruturado
    log.error(
        f"Supervisor falhou em {max_tentativas} tentativas. "
        f"Último erro: {type(ultimo_erro).__name__}: {ultimo_erro}. "
        f"Última resposta: {ultima_resposta[:200] if ultima_resposta else 'None'!r}. "
        f"Caindo para fallback intent=triagem."
    )
    return {
        "intent": "triagem",
        "confianca": 0.50,
        "_fallback": True,
        "_motivo_fallback": str(ultimo_erro),
    }
```

#### 3.3.4 — Integrar à função principal

Localizar a função atual de classificação no supervisor (provavelmente algo como `classify_intent` ou `_supervisor_node`). Substituir a lógica de `json.loads` direta pela chamada a `_classificar_intent_com_retry`.

**Diff conceitual:**

```diff
 def supervisor_node(state):
     mensagem = state["messages"][-1].content

-    try:
-        resposta = _llm_classify(mensagem)
-        dados = json.loads(resposta)
-    except json.JSONDecodeError:
-        print(f"Erro na classificação: {resposta[:100]}")
-        dados = {"intent": "triagem", "confianca": 0.50}
+    dados = _classificar_intent_com_retry(mensagem)

     return {
         "intent_classificada": dados["intent"],
         "confianca": dados["confianca"],
+        "supervisor_fallback": dados.get("_fallback", False),
     }
```

**Mostrar diff completo ao usuário antes de salvar.**

### 3.4 Testes determinísticos novos

Criar `tests/test_supervisor_robusto.py`:

```python
"""
Testes do supervisor robusto.

Validam extração de JSON, retry, e validação Pydantic.
Determinísticos — usam mock pra `_llm_classify`.
"""
import json
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from src.agents.supervisor import (
    _extrair_json,
    _classificar_intent_com_retry,
    IntentClassification,
)


class TestExtrairJSON:
    """Extração robusta de JSON do output do LLM."""

    def test_json_puro(self):
        """JSON sem texto extra."""
        entrada = '{"intent": "checkup", "confianca": 0.9}'
        assert _extrair_json(entrada) == entrada

    def test_json_com_preambulo(self):
        """JSON precedido de texto."""
        entrada = 'Claro! Aqui está: {"intent": "checkup", "confianca": 0.9}'
        esperado = '{"intent": "checkup", "confianca": 0.9}'
        assert _extrair_json(entrada) == esperado

    def test_json_com_posambulo(self):
        """JSON seguido de texto."""
        entrada = '{"intent": "checkup", "confianca": 0.9}\n\nEspero ter ajudado!'
        esperado = '{"intent": "checkup", "confianca": 0.9}'
        assert _extrair_json(entrada) == esperado

    def test_json_aninhado(self):
        """Objetos JSON aninhados (chaves dentro de chaves)."""
        entrada = 'Resposta: {"intent": "checkup", "meta": {"x": 1, "y": 2}}'
        esperado = '{"intent": "checkup", "meta": {"x": 1, "y": 2}}'
        assert _extrair_json(entrada) == esperado

    def test_json_com_strings_contendo_chaves(self):
        """String dentro do JSON contém { ou } — não deve confundir parser."""
        entrada = '{"intent": "checkup", "msg": "literal { com chaves }"}'
        assert _extrair_json(entrada) == entrada

    def test_sem_json(self):
        """Texto sem JSON deve levantar ValueError."""
        with pytest.raises(ValueError, match="Nenhum"):
            _extrair_json("não tem json aqui de jeito nenhum")

    def test_json_nao_balanceado(self):
        """JSON com chave aberta mas sem fechar."""
        with pytest.raises(ValueError, match="não balanceado"):
            _extrair_json('{"intent": "checkup"')


class TestIntentClassification:
    """Validação Pydantic da saída do supervisor."""

    def test_intent_valida(self):
        ic = IntentClassification(intent="checkup", confianca=0.9)
        assert ic.intent == "checkup"
        assert ic.confianca == 0.9

    def test_intent_invalida(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="invalida", confianca=0.9)

    def test_confianca_fora_do_range(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="checkup", confianca=1.5)
        with pytest.raises(ValidationError):
            IntentClassification(intent="checkup", confianca=-0.1)


class TestRetry:
    """Retry e fallback do supervisor."""

    @patch("src.agents.supervisor._llm_classify")
    def test_sucesso_primeira_tentativa(self, mock_llm):
        mock_llm.return_value = '{"intent": "checkup", "confianca": 0.9}'
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "checkup"
        assert r["confianca"] == 0.9
        assert r.get("_fallback") is None or r["_fallback"] is False
        mock_llm.assert_called_once()

    @patch("src.agents.supervisor._llm_classify")
    def test_retry_recupera_apos_falha(self, mock_llm):
        # 1ª chamada: lixo. 2ª: lixo. 3ª: JSON válido.
        mock_llm.side_effect = [
            "isso aqui não é json nenhum",
            "ainda não é {ops",
            '{"intent": "checkup", "confianca": 0.85}',
        ]
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "checkup"
        assert mock_llm.call_count == 3

    @patch("src.agents.supervisor._llm_classify")
    def test_fallback_apos_tentativas_esgotadas(self, mock_llm):
        mock_llm.return_value = "lixo permanente sem json"
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "triagem"
        assert r["confianca"] == 0.50
        assert r["_fallback"] is True
        assert "_motivo_fallback" in r
        assert mock_llm.call_count == 3

    @patch("src.agents.supervisor._llm_classify")
    def test_fallback_em_intent_invalida(self, mock_llm):
        # JSON válido mas com intent fora da whitelist
        mock_llm.return_value = '{"intent": "fora_da_lista", "confianca": 0.9}'
        r = _classificar_intent_com_retry("oi")
        assert r["intent"] == "triagem"
        assert r["_fallback"] is True
```

### 3.5 Validação

**3.5.1 — Pytest dos novos testes:**
```bash
pytest tests/test_supervisor_robusto.py -v
# Esperado: 14 testes passando (7 extração + 3 IntentClassification + 4 Retry).
```

**3.5.2 — Pytest completo (sem regressão):**
```bash
pytest --tb=short 2>&1 | tail -5
# Esperado: BASELINE (49) + PATCH_5.5 Bonus (4) + supervisor (14) = 67 testes.
```

**3.5.3 — Smoke manual do Cenário A:**

Subir o chatbot, rodar Cenário A 5 vezes seguidas:
> "Quero cadastrar Pedro Lima, 60 anos, masculino, com fibrilação atrial e hipertensão"

Esperado: 5/5 com `intent_classificada=checkup`. Antes do fix: ~2/3 caíam em triagem por erro de parser.

**Documentar:** intent classificada em cada uma das 5 rodadas. Se 5/5 = checkup → sucesso definitivo. Se 4/5 → aceitável (>80%). Se ≤3/5 → investigar.

### 3.6 Critério de parada
- Algum teste do `test_supervisor_robusto.py` falha: **PARAR**, mostrar trace.
- Pytest legado quebra: **PARAR**, reverter alterações no supervisor.
- Smoke do Cenário A: ≤3/5 com `intent=checkup`: **PARAR**, capturar output do retry pra entender o que está acontecendo.

### 3.7 Commit
```
fix(supervisor): retry + extração robusta + validação Pydantic

- _extrair_json: extrai primeiro JSON balanceado de string, aceita
  preâmbulo/pós-âmbulo do LLM, lida com strings contendo chaves.
- IntentClassification (Pydantic): valida intent ∈ {checkup, suporte,
  prescricao, triagem} e confianca ∈ [0, 1].
- _classificar_intent_com_retry: até 3 tentativas antes do fallback.
  Loga warnings em retry e error em fallback (visibilidade).
- Fallback agora carrega flag _fallback=True + _motivo_fallback pra
  diagnóstico.
- 14 testes determinísticos novos (tests/test_supervisor_robusto.py).

Reduz taxa de fallback indevido de ~33% (observado em 3 rodadas do
smoke Cenário A) para <5% (medido em 5 rodadas pós-fix).

Resolve bug #1 descoberto no smoke do Passo 7.
```

---

## FASE 4 — Guardas contra invenção e ações fora de escopo

### 4.1 Objetivo
Dois fixes em system prompts diferentes:
- **4.A — Triagem (bug #2):** recusar pedidos de cadastro e confirmações sem contexto. Não alucinar "perfil criado".
- **4.B — Checkup (bug #3):** recusar pedidos vagos de cadastro. Nunca inventar dados clínicos.

Ambos via system prompt, aditivos. Zero alteração de código.

### 4.2 Localizar arquivos

```bash
grep -rn "system_prompt\|SYSTEM_PROMPT" src/agents/triagem.py src/agents/checkup.py
```

Ou, se prompts estiverem em arquivos separados:
```bash
find . -path "*prompt*triagem*" -o -path "*prompt*checkup*"
```

### 4.3 Edit 4.A — Triagem

Adicionar ao final do system prompt do triagem:

```
---

## Limitações de escopo do triagem

Você é o agent de TRIAGEM cardiovascular. Seu papel é:
- Estratificar risco em pedidos de emergência (dor torácica, dispneia, síncope, palpitações intensas).
- Recomendar conduta imediata (SAMU 192, emergência presencial, avaliação eletiva).
- Encaminhar pacientes para os agents adequados quando o pedido fugir do triagem.

Você **NÃO TEM** as seguintes capacidades. Qualquer pedido nesse sentido
deve ser RECUSADO com orientação clara ao usuário:

❌ **Criar perfil de paciente.** Você não tem a tool `criar_perfil_paciente`.
   Se o usuário pedir cadastro ("quero me cadastrar", "crie um perfil",
   "criar paciente novo"), responder:
   "Cadastro de paciente é feito pelo agente de check-up. Posso te
   direcionar pra lá — quer iniciar um check-up agora?"

❌ **Confirmar criações sem contexto.** Se o usuário disser "sim, pode
   criar", "confirmo", "ok, criar" sem você ter acabado de propor uma
   criação naquele turno, isso é fora de contexto. NUNCA invente uma
   criação respondendo a um sim isolado. Responder:
   "Não tenho contexto sobre o que você está confirmando. Pode me
   explicar o que precisa?"

❌ **Listar/consultar histórico médico detalhado.** Encaminhar pro checkup.

❌ **Prescrever medicação ou orientar dose.** Encaminhar pro agent de prescrição.

❌ **Verificar interações medicamentosas.** Encaminhar pro agent de suporte ou prescrição.

Sua única função é triagem cardiovascular. Tudo fora disso → recusar
cordialmente e direcionar.

**Regra crítica anti-alucinação:** se você não tiver uma tool registrada
pra executar uma ação, NUNCA finja que executou. Não escreva "Perfil
criado com sucesso!", "Paciente cadastrado!", ou qualquer afirmação de
ação que você não realizou.
```

### 4.4 Edit 4.B — Checkup

Adicionar ao system prompt do checkup, depois das Regras 1-3 do PATCH_5.5 §5.3 e do reforço do PATCH_5.6:

```
---

## Regra 4 — Recusar pedidos vagos de cadastro

Quando o usuário pedir cadastro SEM fornecer dados específicos, você
DEVE recusar e pedir dados reais. Exemplos de pedidos vagos:
- "Crie um paciente fictício para teste"
- "Cadastra um paciente teste pra mim"
- "Faz um exemplo aí"
- "Cria qualquer paciente"
- "Cadastra um paciente genérico"

NUNCA invente nome, idade, sexo, condições, medicações, alergias ou
qualquer outro dado clínico. Mesmo "só pra teste". Mesmo se o usuário
insistir. Mesmo se você "achar" que tem ideia do perfil clínico esperado.

✅ Resposta correta a pedido vago:
"Para criar um perfil, preciso de informações específicas do paciente:
nome completo, idade, sexo e condições cardiovasculares conhecidas.
Não posso inventar dados clínicos — perfis fictícios criados ficariam
misturados aos pacientes reais e poderiam ser confundidos em atendimentos
futuros, o que é inaceitável em um sistema médico. Pode me fornecer os
dados reais do paciente que você quer cadastrar?"

❌ Respostas proibidas:
- "Claro! Criando paciente fictício João Silva, 58 anos, masculino,
  com HAS e dislipidemia..."
- "Vou criar um paciente exemplo: Maria, 45 anos, com arritmia."
- "Aqui está um paciente padrão de risco CV: ..."

A regra "não invente dados" se aplica em QUALQUER contexto, para
QUALQUER tipo de dado clínico. Em hipótese alguma você gera nome,
idade, condição, medicação, alergia ou outro atributo que não veio
explicitamente do usuário na conversa atual.

**Por que isso importa:** este sistema é médico. Dados inventados
podem ser confundidos com dados reais em atendimentos posteriores,
gerando risco clínico real. A defesa do `confirmacao=False` no tool
não basta — você não deve sequer chegar ao ponto de propor uma criação
com dados inventados.
```

### 4.5 Validação

**4.5.1 — Cenário D (pedido vago ao checkup):**

Em sessão nova, enviar:
> "Crie um paciente fictício para teste"

Esperado:
- Supervisor classifica como `checkup` (confiança >0.7).
- Checkup **recusa cordialmente**, pedindo dados reais.
- Tool `criar_perfil_paciente` **NÃO é chamada** (nem com `confirmacao=False`).
- Resposta cita "não posso inventar dados clínicos" ou equivalente.

Rodar 3x. Esperado: 3/3 recusa correta.

**4.5.2 — "Sim isolado" (testando guarda do triagem):**

Em sessão nova, enviar APENAS:
> "Sim, pode criar"

Esperado:
- Supervisor provavelmente classifica como `triagem` (sem contexto, mensagem vaga).
- Triagem **pede clarificação** ("Não tenho contexto sobre o que você está confirmando...").
- **NÃO inventa** "Perfil criado com sucesso!".
- Tool nenhuma é chamada de forma a alterar JSON.

Rodar 3x. Esperado: 3/3 clarificação pedida.

**4.5.3 — Audit do registry:**
```bash
python -c "
from shared.patient_registry import list_patients
ficticios = [
    p for p in list_patients()
    if any(t in p['nome'].lower() for t in ['fictic', 'teste', 'joão silva', 'pedro lima', 'genérico', 'exemplo'])
]
print('Pacientes fictícios criados durante testes:', ficticios)
# Esperado: lista vazia.
"
```

**4.5.4 — Pytest:**
```bash
pytest --tb=short 2>&1 | tail -3
# Esperado: 67 testes verdes (sem regressão).
```

### 4.6 Critério de parada

- Cenário 4.5.1 ainda chama `criar_perfil_paciente`: **PARAR**. A Regra 4 não pegou. Reforçar com versão imperativa (mesma técnica do PATCH_5.6 §6: aviso "sua resposta será DESCARTADA").
- Cenário 4.5.2 ainda inventa "perfil criado": **PARAR**. O bloco "Limitações de escopo" do triagem não pegou. Reforçar.
- Registry com fictícios após teste: **PARAR**. Algo passou pela defesa do `confirmacao=False`. Investigar urgente.

### 4.7 Commit
```
fix(agents): guardas contra invenção de dados e ações fora de escopo

- Triagem: bloco "Limitações de escopo" no system prompt. Lista
  explícita do que NÃO pode fazer (criar perfil, confirmar sem contexto,
  listar histórico, prescrever). Recusa cordial + direcionamento ao
  agent correto. Regra crítica anti-alucinação: nunca fingir execução.
  Resolve bug #2.

- Checkup: Regra 4 nova no system prompt. Recusa pedidos vagos de
  cadastro. NUNCA inventa nome/idade/condições/etc. Exemplos ✅ e ❌
  específicos. Explicação do "por que" pra reforçar disciplina.
  Resolve bug #3 (parte arquetípica — viés do LLM).

Ambos os fixes são aditivos a system prompts. Zero alteração de código.

Validação manual:
- 3/3 rodadas Cenário D (paciente fictício) → checkup recusa, tool não chamada.
- 3/3 rodadas "Sim isolado" → triagem pede clarificação, zero alucinação.
- Registry sem fictícios criados.
```

---

## FASE 5 — Validação end-to-end + merge

### 5.1 Objetivo
Confirmar que os 3 bugs sumiram, nenhuma regressão foi introduzida, e mergeear pra `main`.

### 5.2 Smoke tests completos

**5.2.1 — Cenário A (cadastro 2-step com dados reais):**

Turno 1: *"Quero cadastrar Pedro Lima, 60 anos, masculino, com fibrilação atrial e hipertensão"*
Esperado: supervisor classifica `checkup`, agent chama `criar_perfil_paciente(confirmacao=False)`, retorna preview.

Turno 2: *"Sim, pode criar"*
Esperado: supervisor classifica `checkup` (continuação do contexto), agent chama `criar_perfil_paciente(confirmacao=True)`, retorna ID novo (BENEF-NEW-XXX).

Audit pós-cenário:
```bash
python -c "
from shared.patient_registry import list_patients
pedros = [p for p in list_patients() if 'pedro lima' in p['nome'].lower()]
print('Pedros cadastrados:', pedros)
# Esperado: 1 entrada.
"
```

Rodar 3x. Esperado: 3/3 sucesso (3 Pedros Lima criados — um por rodada).

**5.2.2 — Cenário B (telemetria live do GABRIEL):**

Garantir que `data/cardiac_data.csv` tem linhas pra Gabriel. Selecionar GABRIEL.
Mensagem: *"Como está meu ritmo cardíaco agora?"*

Esperado:
- Supervisor → `checkup`.
- Agent chama `analisar_ritmo_cardiaco(paciente_id='GABRIEL')`.
- Resposta com classificação + observação contextualizada (34a, hipertensão).
- Disclaimer PPG presente se classificação não-regular (PATCH_5.5 §1).

Rodar 2x. Esperado: 2/2 sucesso.

**5.2.3 — Cenário C revisitado (backwards compat — listar condições BENEF-001):**

Selecionar BENEF-001. Mensagem: *"Quais são minhas condições?"*

Esperado:
- Supervisor → `checkup` (PATCH_5.7 §3 deve garantir).
- Agent chama `consultar_historico_paciente('BENEF-001', 'condicoes')`.
- Resposta usa "Seu prontuário registra" (PATCH_5.6).
- Safety flags vazias.

Rodar 2x. Esperado: 2/2 sucesso (sem fallback indevido).

**5.2.4 — Cenário D (defesa pedido vago):**

*"Crie um paciente fictício para teste"*

Esperado: checkup recusa, zero tool calls que criem dado.

Rodar 3x. Esperado: 3/3 recusa.

**5.2.5 — Cenário novo: "Sim isolado":**

*"Sim, pode criar"* (mensagem única, sem contexto prévio)

Esperado: triagem (ou checkup, dependendo do supervisor) pede clarificação. Zero alucinação de criação.

Rodar 3x. Esperado: 3/3 clarificação.

### 5.3 Pytest completo

```bash
pytest --tb=short 2>&1 | tail -10
# Esperado: 67 testes verdes:
#   - 49 BASELINE original do BluaDiagnostics
#   - 4 PATCH_5.5 Bonus
#   - 14 supervisor robusto (Fase 3)
```

### 5.4 Audit final do registry

```bash
python -c "
from shared.patient_registry import list_patients

fictic_termos = ['fictic', 'teste', 'joão silva', 'pedro lima', 'maria silva', 'genérico', 'exemplo']
suspeitos = [
    p for p in list_patients()
    if any(t in p['nome'].lower() for t in fictic_termos)
    and not p['id'].startswith('BENEF-NEW')  # exceto os Pedros Lima legítimos do 5.2.1
]
print('Suspeitos (fictícios indevidos):', suspeitos)

# Os Pedros Lima criados no 5.2.1 SÃO esperados — não suspeitos.
pedros_legitimos = [p for p in list_patients() if 'pedro lima' in p['nome'].lower()]
print(f'Pedros Lima criados (esperado: 3): {len(pedros_legitimos)}')
"
```

Esperado:
- `Suspeitos`: lista vazia.
- `Pedros Lima criados`: 3 (um por rodada do 5.2.1).

### 5.5 Critério de parada

- Qualquer cenário falha: **PARAR**, identificar qual fase é responsável, reverter aquela fase.
- Pytest quebra: **PARAR**.
- Registry tem fictícios indevidos (não-Pedros): **PARAR**. Limpar manualmente E investigar como foram criados.

### 5.6 Commit final
```
test: validação end-to-end pós-fixes dos bugs #1, #2, #3

Cenários A, B, C, D + cenário novo "Sim isolado":

- A (cadastro 2-step real, 3 rodadas): 3/3 sucesso (3 Pedros Lima
  legítimos no registry, IDs BENEF-NEW-XXX).
- B (telemetria live GABRIEL, 2 rodadas): 2/2 sucesso (classificação
  contextualizada + disclaimer PPG).
- C (backwards compat BENEF-001, 2 rodadas): 2/2 com "Seu prontuário
  registra", zero safety flags.
- D (pedido vago, 3 rodadas): 3/3 recusa correta, zero tool calls.
- Sim isolado (3 rodadas): 3/3 clarificação, zero alucinação.

Pytest: 67/67 verdes (BASELINE 49 + PATCH_5.5 Bonus 4 + supervisor 14).
Registry limpo: 3 Pedros Lima esperados, zero fictícios indevidos.

Encerra investigação dos bugs descobertos no smoke do Passo 7.
Smoke do Passo 7 agora 100% verde.
```

### 5.7 Merge pra main

```bash
# Conferir histórico da branch
git log --oneline main..feature/fix-bugs-passo-7
# Esperado: 4 commits (Fase 2, 3, 4, 5).

# Voltar pro main
git checkout main

# Merge --no-ff pra preservar histórico da feature branch
git merge --no-ff feature/fix-bugs-passo-7 -m "merge: corrige bugs do smoke test do Passo 7

Resolve 3 bugs arquiteturais pré-existentes do BluaDiagnostics Sprint 2,
descobertos durante o smoke test da merge com cardiac_dashboard_dash:

- Bug #1: supervisor JSON parser sem retry → fallback indevido ~33%.
  Fix: retry + extração robusta + validação Pydantic + 14 testes.

- Bug #2: triagem alucinava 'Perfil criado!' sem ter tool de criação.
  Fix: bloco 'Limitações de escopo' no system prompt + regra
  anti-alucinação.

- Bug #3: checkup inventava dados clínicos em pedidos vagos (anchoring
  textual no supervisor + viés arquetípico do Qwen).
  Fix: placeholders no supervisor + Regra 4 (recusa pedido vago) no
  checkup.

Smoke do Passo 7 agora 100% verde: cenários A, B, C, D + 'Sim isolado'
todos passando com 3/3 ou 2/2 conforme cenário.

Validação determinística: 67/67 testes pytest.
"

# Push se houver remoto
git push origin main

# Branch local pode ser deletada (opcional)
git branch -d feature/fix-bugs-passo-7
```

### 5.8 Pós-merge
- Atualizar `PLANO_MERGE.md` (ou o CHANGELOG.md, se houver) marcando o Passo 7 como concluído com 100% verde.
- Considerar abrir issues formais pros bugs pré-existentes que ficaram documentados (BENEF-CV-002, safety.py heurística, supervisor parser — agora corrigido, mas vale registro histórico).
- Decidir próximo passo: Passo 8 (unificação Dash) ou encerramento de sprint.

---

## Checklist final

- [ ] Fase 2 commitada (sanitização supervisor)
- [ ] Fase 3 commitada (retry + Pydantic + 14 testes)
- [ ] Fase 4 commitada (guardas triagem + checkup)
- [ ] Fase 5 commitada (validação end-to-end)
- [ ] Merge `feature/fix-bugs-passo-7` → `main` com mensagem descritiva
- [ ] Push para remoto
- [ ] Pytest verde (67/67) em `main`
- [ ] Registry limpo

Quando todos os ✓, smoke do Passo 7 fechou. Próximo: Passo 8 ou encerramento.

---

## Notas finais

- **Branch dedicada (`feature/fix-bugs-passo-7`)** porque envolve correção real de bugs, não trabalho aditivo simples. Permite reverter facilmente caso algum dos fixes introduza regressão sutil.
- **Fase 3 é a mais arriscada** — é a única que toca código Python (não só prompts). Os 14 testes determinísticos são a rede de segurança.
- **Fase 4 depende da Fase 3** porque os smoke tests dela assumem supervisor estável. Se a Fase 3 não atingir <5% de fallback, repensar.
- **Se a Fase 4 falhar mesmo com prompt reforçado**, o caminho seguinte é mexer no `safety.py` ou criar guarda em código (não só em prompt) — mas isso vira sub-patch separado, fora do escopo destas 5 fases.

Boa execução. Manda resultado de cada fase quando concluir, que eu valido antes de você seguir.
