# PATCH_5.6_REFORCO_REGRA_1.md

**Pré-requisito:** PATCH_5.5 aplicado e commitado. Cenário C do smoke test do Passo 7 reproduzindo falha determinística (2/2 com `intent=checkup`).

**Versão:** 1.0
**Tempo estimado:** 15-25min (5min de edição + 5-15min de smoke retest)
**Risco:** muito baixo (mudança aditiva no system prompt, sem tocar código)

---

## Por que este patch existe

Smoke test do Cenário C (backwards compat — listar condições de BENEF-001) revelou falha determinística:

- Checkup LLM lista condições do prontuário usando linguagem afirmativa ("você tem hipertensão").
- Heurística pré-existente em `src/agents/safety.py:28` detecta substring `"você tem "` e acende `DIAGNOSTICO_DEFINITIVO_DETECTADO`.
- Auditor LLM reprova a resposta.
- Resposta final é substituída por versão defensiva ("não consigo acessar prontuário"), confundindo o usuário.

**Causa-raiz:** bug pré-existente do BluaDiagnostics Sprint 2 — heurística sem contexto. Tratado como issue separada (ver seção "Bug pré-existente" no final).

**Escopo deste patch:** ensinar o checkup a fraseear relatos de prontuário de forma que **não acione a heurística**. Aditivo ao system prompt, sem tocar `safety.py`.

A Regra 1 do PATCH_5.5 §5.3 já cobria isso em princípio ("use linguagem descritiva, não diagnóstica"), mas com exemplos genéricos focados em **resultado de tool** (`analisar_ritmo_cardiaco`). Faltou cobrir o caso **listar dados do prontuário** (`consultar_historico_paciente`), que é semanticamente diferente.

---

## Correção única

### 1. Objetivo
Adicionar ao system prompt do checkup um bloco de exemplos few-shot específicos para o caso "relatar dados já cadastrados no prontuário".

### 2. Arquivo
System prompt do agent checkup. Localizar:
```bash
grep -rn "system_prompt\|SYSTEM_PROMPT" src/agents/checkup.py
# Ou, se estiver em arquivo separado:
find . -path "*prompts*checkup*" -not -path "*/.*"
```

### 3. Texto a adicionar

Adicionar **ao final da seção "Disciplina de escopo e linguagem clínica"** (criada no PATCH_5.5 §5.3), logo depois da Regra 3. Bloco novo:

```
---

## Reforço da Regra 1 — Relatar dados do prontuário

Quando você usar `consultar_historico_paciente` (com qualquer `campo`:
'condicoes', 'medicacoes', 'alergias', 'historico') e precisar relatar
o resultado ao usuário, NUNCA use frases afirmativas do tipo "você tem X"
ou "você possui X". O sistema de auditoria de segurança bloqueia esse
fraseado automaticamente porque ele soa como diagnóstico, mesmo quando
você está apenas listando dado cadastrado.

Use SEMPRE linguagem de RELATO sobre o prontuário existente:

✅ EXEMPLOS CERTOS (relato de prontuário):
  - "Seu prontuário registra: hipertensão arterial sistêmica, arritmia
    e taquicardia."
  - "No seu cadastro constam as seguintes condições: HAS, arritmia,
    taquicardia (CID I10, I49.9, R00.0)."
  - "De acordo com os dados cadastrados em 14/03/2024, as condições
    registradas são: hipertensão arterial sistêmica e arritmia."
  - "O prontuário lista 3 condições ativas: hipertensão, arritmia
    e taquicardia."
  - "Constam no histórico: HAS (desde 2020), arritmia (desde 2023)."
  - "As alergias registradas no seu cadastro são: penicilina e dipirona."
  - "Seu histórico médico indica uso atual de: Losartana 50mg, AAS 100mg."

❌ EXEMPLOS PROIBIDOS (soam como diagnóstico):
  - "Você tem hipertensão arterial sistêmica."
  - "Você possui arritmia e taquicardia."
  - "Suas condições são hipertensão e arritmia."
  - "Você apresenta HAS, FA e taquicardia."
  - "Você é alérgico a penicilina."
  - "Você toma Losartana."

A diferença é semântica:
  - "Seu prontuário registra X" → RELATO de dado cadastrado (autorizado).
  - "Você tem X" → AFIRMAÇÃO clínica direta (bloqueada pela auditoria).

Construções seguras que você pode usar livremente:
  - "consta...", "registra...", "indica..."
  - "o prontuário...", "seu cadastro...", "no histórico..."
  - "de acordo com os dados...", "segundo o cadastro..."
  - "as condições registradas são...", "os medicamentos em uso são..."

Aplique este princípio para QUALQUER dado do histórico: condições,
medicações, alergias, histórico clínico. Sempre prefira construções
indiretas que descrevem o prontuário, não construções diretas que
afirmam sobre o paciente.
```

### 4. Validação

Aplicar o patch e rodar o **Cenário C do Passo 7 três vezes consecutivas** (sem reset de sessão entre rodadas):

**Procedimento:**

```
1. Iniciar nova sessão do chatbot
2. Selecionar paciente BENEF-001
3. Enviar: "Quais são minhas condições?"
4. Aguardar resposta
5. Inspecionar logs:
   - intent_classificada deve ser 'checkup' (se for fallback triagem
     por erro de parser, repetir até pegar checkup — bug separado)
   - safety flags devem ser [] (vazio)
   - resposta final deve listar as condições reais
6. Repetir 2x mais (rodadas 2 e 3)
```

**Critérios de sucesso:**

| Cenário | Status |
|---------|--------|
| 3/3 com `intent=checkup` E sem safety flag | ✅ Sucesso. Aplicar e commitar. |
| 2/3 sucesso | ⚠️ Marginal. Documentar e considerar iteração. |
| ≤1/3 sucesso | ❌ Insuficiente. Iterar (ver seção 6). |

### 5. Critério de parada

- Se 3/3 sucesso → fechar patch, commitar, seguir smoke test.
- Se 2/3 → analisar o output que falhou. Se foi pela mesma "você tem", o reforço precisa ser ainda mais imperativo (adicionar `IMPORTANTE:` ou `OBRIGATÓRIO:` nas linhas críticas). Se foi por outra heurística (`"o diagnóstico é"`, etc.), abrir investigação nova.
- Se ≤1/3 → o LLM não está respeitando o prompt. Causas possíveis:
  1. Prompt está sendo truncado por context length.
  2. Prompt tem instruções conflitantes em outra parte.
  3. LLM (Qwen) tem viés forte por "você tem" em pt-BR que prompt não desfaz.
  - Aí escalar pra Opção A da análise anterior: refinar `safety.py` com contexto (whitelist quando tool de prontuário foi chamada no turno).

### 6. Iteração (se necessário)

Se 2/3 ou ≤1/3 sucesso, reforçar com **prefixo imperativo** no início do bloco:

```diff
- ## Reforço da Regra 1 — Relatar dados do prontuário
+ ## Reforço da Regra 1 — Relatar dados do prontuário [REGRA CRÍTICA]
+
+ ⚠️ ATENÇÃO: a auditoria automática deste sistema BLOQUEIA respostas que
+ usam fraseado afirmativo. Se você usar "você tem" ou "você possui",
+ sua resposta SERÁ DESCARTADA e substituída por mensagem genérica de
+ erro. O usuário NÃO verá o que você escreveu. Para a sua resposta ser
+ entregue, você DEVE usar linguagem de relato sobre o prontuário.

  Quando você usar `consultar_historico_paciente`...
```

Esse tipo de aviso "sua resposta será descartada" é forte sinal pro LLM mudar comportamento. Use apenas se a versão padrão não bastar.

### 7. Commit

```
feat(checkup): reforça Regra 1 com exemplos few-shot de relato de prontuário

Adiciona ao system prompt do checkup um bloco específico ensinando a
fraseear resultados de consultar_historico_paciente como RELATO de
prontuário ("seu prontuário registra X") em vez de AFIRMAÇÃO direta
("você tem X").

Motivação: smoke test do Cenário C do Passo 7 (PATCH_5.5) revelou falha
determinística onde o checkup LLM listava condições reais do paciente
BENEF-001 usando "você tem hipertensão", o que acionava a heurística
pré-existente _DIAGNOSTICO_DEFINITIVO em src/agents/safety.py:28 e
fazia o auditor reprovar a resposta legítima.

Este patch corrige o sintoma (linguagem do LLM) sem tocar a causa-raiz
(heurística sem contexto em safety.py). Ver issue [XXX] para correção
definitiva.

Validação: 3/3 rodadas do Cenário C com intent=checkup e sem safety flag.
```

---

## Bug pré-existente — registrar como issue separada

Independente deste patch, registrar formalmente o bug do BluaDiagnostics Sprint 2:

### Issue: `[bug] safety.py — falso-positivo ao relatar dados do prontuário`

**Descrição:**
Heurística determinística em `src/agents/safety.py:28-31` lista `["você tem ", ...]` como gatilho de `DIAGNOSTICO_DEFINITIVO_DETECTADO`. Quando o agent checkup lista dados reais do prontuário (condições, medicações, alergias) usando fraseado natural pt-BR ("você tem hipertensão"), a heurística acende flag, auditor LLM reprova, e a resposta legítima é substituída por versão defensiva ("não consigo acessar prontuário"). Usuário recebe mensagem contraditória com o que pediu.

**Origem:** Bug pré-existente do BluaDiagnostics Sprint 2. Exposto durante smoke test do Cenário C do Passo 7 (PATCH_5.5). Os 49 testes baseline não cobriam esse fluxo (checkup + listar dados de paciente já cadastrado).

**Reprodução:** Determinística — 2/2 ou 3/3 rodadas falhavam quando `intent_classificada=checkup`. Falsa "flake" anterior era do supervisor (erro de parser JSON em outra parte do grafo).

**Workaround atual:** PATCH_5.6 reforça o system prompt do checkup com exemplos few-shot ensinando a fraseear como relato ("seu prontuário registra X") em vez de afirmação ("você tem X"). Não corrige a heurística — apenas evita acioná-la.

**Correção definitiva (futura):** refinar `safety.py` pra ter contexto. Whitelist contextual:
- Se a tool `consultar_historico_paciente` foi chamada no mesmo turno COM `campo` retornando dados, então "você tem X" / "você possui X" onde X aparece no retorno da tool é **relato autorizado**, não diagnóstico.
- Pseudocódigo:
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

**Prioridade:** Média. Workaround do PATCH_5.6 endereça o sintoma de curto prazo, mas a heurística continua frágil pra outros casos (ex.: paraphraseações do LLM que não estão nos exemplos few-shot).

**Estimativa:** 1-2h pra implementar + testes.

---

## Validação final do patch inteiro

Depois de aplicar o reforço e validar Cenário C 3/3:

```bash
# 1. Pytest verde (esperado — não tocamos código)
pytest --tb=short 2>&1 | tail -5

# 2. Smoke test do Cenário C 3 vezes (manual no chat)
# Documentar resultado de cada rodada.

# 3. Confirmação de que o resto do PATCH_5.5 não regrediu
# (cenários 5.A, 5.B, 5.C ainda devem se comportar como esperado)
```

Quando os 3 verdes, este patch fecha. Retomar a Onda 1 do smoke test pelo Cenário D.

---

## Notas

- **Este patch toca apenas o system prompt do checkup.** Nenhum arquivo `.py` é modificado. Nenhum teste pytest precisa ser ajustado.
- **A taxa de sucesso depende do LLM (Qwen).** LLMs diferentes podem precisar de reforço diferente. Se trocar de backend (Ollama ↔ DashScope), revalidar.
- **Não é solução definitiva.** É workaround consciente. A issue do `safety.py` deve ser tratada em sprint futuro.
- **Se a iteração reforçada (seção 6) também falhar**, considerar fix na Opção A (refinar `safety.py`). Mas só nesse cenário — não antecipar.

Boa execução.
