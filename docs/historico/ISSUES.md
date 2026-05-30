# Issues conhecidas

Lista de bugs e melhorias identificadas mas não corrigidas. Cada
issue inclui origem, sintoma, workaround atual (se houver), e
correção sugerida.

---

## Issue 1 — BENEF-CV-002 alergias com formato inconsistente

**Severidade:** Média
**Status:** Aberta
**Descoberto em:** 2026-05-28, durante PATCH_5.5 §3
**Origem:** Pré-existente do BluaDiagnostics Sprint 2

### Descrição

Paciente BENEF-CV-002 em `data/mocks/perfis_clinicos.json` tem campo
`alergias` como `list[str]` em vez do formato esperado `list[dict]`.

Exemplo do estado atual:
```json
"alergias": ["Varfarina (substituída por DOAC...)"]
```

Formato esperado:
```json
"alergias": [
  {
    "substancia": "Varfarina",
    "reacao": "...",
    "gravidade": "..."
  }
]
```

### Sintoma

`prescricao._verificar_alergias` quebrará com TypeError ao iterar
`a["substancia"]` numa string. Bug não exposto pelos 49 testes
baseline porque eles não exercitam esse fluxo específico (agent
prescrição + paciente BENEF-CV-002).

### Workaround

Não selecionar BENEF-CV-002 ao testar fluxos que envolvem
`prescricao._verificar_alergias`.

### Correção sugerida

Duas opções:

**A.** Normalizar BENEF-CV-002 no JSON pro formato `list[dict]`,
mantendo as informações originais como melhor possível:
```json
"alergias": [
  {
    "substancia": "Varfarina",
    "reacao": "não especificada",
    "gravidade": "não especificada",
    "observacao": "substituída por DOAC..."
  }
]
```

**B.** Adicionar tolerância em `_verificar_alergias` pra aceitar
ambos os formatos (`list[str]` e `list[dict]`), com warning quando
formato achatado for usado. Não corrige o dado, mas evita o crash.

Recomendação: **A** (corrige o dado na fonte; padrão único no
sistema). B é band-aid.

### Estimativa

15-30min (opção A) ou 1-2h (opção B com testes).

---

## Issue 2 — safety.py heurística "você tem" sem contexto

**Severidade:** Média (alta no impacto UX, baixa em risco real)
**Status:** Aberta
**Descoberto em:** 2026-05-28, durante smoke do Cenário C (Passo 7)
**Origem:** Pré-existente do BluaDiagnostics Sprint 2

### Descrição

Heurística determinística em `src/agents/safety.py:28-31` lista
`["você tem ", ...]` como gatilho de `DIAGNOSTICO_DEFINITIVO_DETECTADO`.
Quando o agent checkup lista dados reais do prontuário (condições,
medicações, alergias) usando fraseado natural pt-BR ("você tem
hipertensão"), a heurística acende flag, auditor LLM reprova, e a
resposta legítima é substituída por versão defensiva ("não consigo
acessar prontuário"). Usuário recebe mensagem contraditória com o
que pediu.

### Sintoma

Determinístico (2/2 ou 3/3 rodadas) quando intent=checkup E pergunta
envolve listar dados cadastrados. Falsa "flake" inicial era do
supervisor (erro de parser JSON, já corrigido na Fase 3 do
fix-bugs-passo-7).

### Workaround atual

Implementado no PATCH_5.6 (commit e24d65d): reforço do system prompt
do checkup com exemplos few-shot ensinando a fraseear como relato
("seu prontuário registra X") em vez de afirmação ("você tem X").
Não corrige a heurística — apenas evita acioná-la via prompt
engineering.

Validado: 2/2 rodadas pós-fix usaram "Seu prontuário registra" sem
acionar safety.

### Correção definitiva sugerida

Refinar `safety.py` com whitelist contextual:

- Se a tool `consultar_historico_paciente` foi chamada no mesmo
  turno COM `campo` retornando dados, então "você tem X" / "você
  possui X" onde X aparece no retorno da tool é **relato autorizado**,
  não diagnóstico.

Pseudocódigo:
```python
def _eh_diagnostico_definitivo(resposta, contexto_turno):
    if _bate_heuristica(resposta):
        # Antes de acender flag, conferir contexto
        tools_chamadas = contexto_turno.get('tool_calls', [])
        for tc in tools_chamadas:
            if tc['name'] == 'consultar_historico_paciente':
                retorno = tc['return']
                termos_no_retorno = _extrair_termos(retorno)
                if _todos_termos_da_resposta_em(resposta, termos_no_retorno):
                    return False  # relato autorizado
        return True
    return False
```

### Estimativa

1-2h pra implementar + testes determinísticos cobrindo casos:
- Sem tool no turno → flag mantida (comportamento atual).
- Tool no turno, termos batem → flag suprimida.
- Tool no turno, termos NÃO batem (paráfrase do LLM) → flag mantida.

### Prioridade

Média. O workaround do PATCH_5.6 endereça o sintoma de curto prazo,
mas a heurística continua frágil pra paráfrases não cobertas pelos
few-shot examples. Refatoração definitiva aumentaria robustez do
sistema de safety.

---
