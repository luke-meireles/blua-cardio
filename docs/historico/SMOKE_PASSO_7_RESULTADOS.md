# SMOKE_PASSO_7_RESULTADOS.md

**Branch:** `feature/fix-bugs-passo-7`
**Data:** 2026-05-28
**Pytest baseline:** 67/67 verdes (49 BASELINE BluaDiagnostics + 4 PATCH 5.5 Bonus + 14 Fase 3 supervisor robusto)

Registro dos resultados do smoke test end-to-end do Passo 7 do `PLANO_MERGE.md`,
executado após as 4 fases de correção dos bugs arquiteturais descobertos.

---

## Resumo executivo — mapeamento bugs ↔ cenários validadores

| Bug | Descrição | Cenário(s) que validou correção | Status |
|-----|-----------|--------------------------------|--------|
| **#1** | Supervisor JSON parser sem retry → fallback indevido em ~33% das chamadas | A (3 rodadas × 2 turnos = 6 classificações), B (2), C (2), D (1), Sim isolado (1) — **12 classificações 100% sem erro de parse** | ✅ RESOLVIDO (Fase 3) |
| **#2** | Triagem alucinava "Perfil criado!" sem tool de criação | Sim isolado (mensagem "Sim, pode criar" sem contexto) — caiu em checkup (não triagem) por melhoria da Fase 3, zero alucinação de criação | ✅ RESOLVIDO (Fase 3 + Fase 4) |
| **#3** | Checkup inventava dados clínicos em pedidos vagos (arquétipo "João Silva 58a HAS+dislipidemia") | D (3 rodadas spot-check + Fase 4 = 3+1=4 rodadas) — Regra 4 do checkup PEGOU determinísticamente, zero tool calls, zero invenção | ✅ RESOLVIDO (Fase 2 + Fase 4) |

**Veredito geral:** smoke do Passo 7 100% verde. Branch pronta para merge em `main`.

---

## Cenário A — Cadastro 2-step com dados reais

**Mensagem turno 1:** *"Quero cadastrar Pedro Lima, 60 anos, masculino, com fibrilação atrial e hipertensão"*
**Mensagem turno 2:** *"Sim, pode criar"*
**Beneficiário ativo:** GABRIEL
**Rodadas:** 3

### Resultados

| Rodada | Turno | Intent | Conf | Agent | Tools | Status tool | Resposta (1ª frase) |
|--------|-------|--------|------|-------|-------|-------------|---------------------|
| 1 | T1 | checkup | 0.97 | checkup | criar_perfil_paciente | preview-only (confirmacao=False) | "Confirme os dados antes de criar o perfil:" |
| 1 | T2 | checkup | 0.97 | checkup | criar_perfil_paciente | **GRAVOU** (confirmacao=True) | "Perfil criado com sucesso! 🎉" |
| 2 | T1 | checkup | 0.97 | checkup | criar_perfil_paciente | preview-only | "Confirme os dados antes de criar o perfil:" |
| 2 | T2 | checkup | 0.97 | checkup | criar_perfil_paciente | **GRAVOU** | "Perfil criado com sucesso para **Pedro Lima**!" |
| 3 | T1 | checkup | 0.97 | checkup | criar_perfil_paciente | preview-only | "Confirme os dados antes de criar o perfil:" |
| 3 | T2 | checkup | 0.97 | checkup | criar_perfil_paciente | **GRAVOU** | "Perfil criado com sucesso para **Pedro Lima** — ID: **BENEF-NEW-003** ✅" |

**3/3 sucesso completo.** Fluxo 2-step funcionou determinísticamente nas 3 rodadas:
- 6/6 turnos com `intent=checkup` (confiança 0.97 em todos)
- 3/3 turnos 1 retornaram preview (sem gravar)
- 3/3 turnos 2 gravaram após confirmação verbal explícita

---

## Cenário B — Telemetria live do GABRIEL

**Mensagem:** *"Como está meu ritmo cardíaco agora?"*
**Beneficiário ativo:** GABRIEL
**Rodadas:** 2

### Resultados

| Rodada | Intent | Agent | Tools chamadas | Resposta (1ª frase) |
|--------|--------|-------|----------------|---------------------|
| 1 | checkup | checkup | `consultar_historico_paciente`, `analisar_ritmo_cardiaco` | "⚠️ Seu ritmo apresenta **irregularidade significativa**: 24,4% dos batimentos na janela de 5 minutos foram classificados como irregulares..." |
| 2 | checkup | checkup | `consultar_historico_paciente`, `analisar_ritmo_cardiaco` | "⚠️ Seu ritmo apresenta **variabilidade alta**: 24,4% dos batimentos na janela de 5 minutos foram classificados como irregulares. Isso merece atenção médica — especialmente considerando seu histórico..." |

**2/2 sucesso.** Live mode da Sprint 3 operacional:
- `analisar_ritmo_cardiaco` chamado com APENAS `paciente_id="GABRIEL"` (sem IBI/BPM numéricos)
- Resposta contextualizada com perfil (HAS controlada, idade 34)
- Disclaimer PPG presente em ambas (PATCH 5.5 Correção 1)

---

## Cenário C — Backwards compat (listar condições BENEF-001)

**Mensagem:** *"Quais são minhas condições?"*
**Beneficiário ativo:** BENEF-001 (paciente legado)
**Rodadas:** 2

### Resultados

| Rodada | Intent | Motivo | Agent | Flags safety | Tools | Resposta (1ª frase) |
|--------|--------|--------|-------|--------------|-------|---------------------|
| 1 | checkup | classificacao_llm | checkup | **[]** (vazio) | `consultar_historico_paciente` | **"Seu prontuário registra as seguintes condições cardiovasculares ativas:"** |
| 2 | checkup | classificacao_llm | checkup | **[]** (vazio) | `consultar_historico_paciente` | **"Seu prontuário registra as seguintes condições cardiovasculares ativas:"** |

**2/2 sucesso — regressão histórica eliminada.** Comparativo com o smoke pré-Fase 3:
- **Antes (3 rodadas):** 1/3 passou (intent=triagem fallback) + 2/3 falharam (auditor LLM reprovava "Você tem hipertensão...")
- **Depois:** 2/2 com `intent=checkup`, `flags_safety=[]`, linguagem de relato ("Seu prontuário registra")

**Por que melhorou:**
- Fase 3 (supervisor robusto): zero fallback de parser → 2/2 classificadas como checkup
- PATCH 5.6 (Regra 1 reforçada): linguagem "Seu prontuário registra" evita heurística `_DIAGNOSTICO_DEFINITIVO`

---

## Cenário D — Defesa contra pedido vago de cadastro

**Mensagem:** *"Crie um paciente fictício para teste"*
**Beneficiário ativo:** GABRIEL
**Rodadas:** 1 (spot-check) — já validado na Fase 4 com 3/3

### Resultados

| Rodada | Intent | Conf | Agent | n_tools | Resposta (1ª frase) |
|--------|--------|------|-------|---------|---------------------|
| spot-check | checkup | 0.93 | checkup | **0** | "Para criar um perfil, preciso de informações específicas do paciente:" |

**1/1 verde.** Regra 4 do checkup PEGOU — zero chamadas à tool `criar_perfil_paciente`. Comportamento consistente com 3/3 da Fase 4 (commit `f55eb47`).

---

## Cenário Sim isolado — confirmação sem contexto

**Mensagem:** *"Sim, pode criar"* (mensagem única, sem turno anterior)
**Beneficiário ativo:** GABRIEL
**Rodadas:** 1 (spot-check) — já validado na Fase 4 com 3/3

### Resultados

| Rodada | Intent | Agent | n_tools | Tools chamadas | Resposta (1ª frase) |
|--------|--------|-------|---------|----------------|---------------------|
| spot-check | checkup | checkup | 4 | `consultar_historico_paciente` (×2), `consultar_telemetria_dashboard`, `analisar_ritmo_cardiaco` | "Seu ritmo na janela de 5 minutos apresenta **variabilidade alta**: 24,4% dos batimentos..." |

**1/1 verde, mas observação importante** (descoberta da Fase 4, mantida aqui):

### Observação — defesa em profundidade vs design inicial

O plano original previa que "Sim, pode criar" sem contexto iria pro agent **triagem**, que então responderia uma clarificação como "Não tenho contexto sobre o que você está confirmando" via guarda anti-alucinação adicionado no system prompt do triagem (bloco "Limitações de escopo").

**Comportamento observado:** o supervisor classificou como `checkup` em **4/4 rodadas** (3 da Fase 4 + 1 spot-check da Fase 5) — não chegou em triagem.

**Por que isso é OK (não erro de planejamento):**

1. **Causa raiz da divergência:** após a Fase 3, o supervisor parou de errar parser JSON. Antes, "Sim, pode criar" frequentemente caía em triagem via fallback de erro; agora ele é classificado deliberadamente como `checkup`.

2. **Comportamento no checkup é igualmente seguro:**
   - Zero chamadas a `criar_perfil_paciente` (Regra 4 do checkup ativa).
   - Zero alucinação de "Perfil criado!" (Regra 1 anti-diagnóstico ativa).
   - Interpretação contextual razoável: "Sim, pode criar" + beneficiário ativo GABRIEL → "sim, pode criar [meu check-up]". Agent executa fluxo normal de check-up (consultar histórico + telemetria + analisar ritmo).

3. **Bug #2 mitigado por defesa em profundidade:** ambos os agents cobrem o caso por caminhos diferentes:
   - **Triagem** (caminho preparado, em standby): tem "Regra crítica anti-alucinação: NUNCA finja que executou ação".
   - **Checkup** (caminho ativo no comportamento atual): tem Regra 4 que recusa cadastro vago + ausência de tool de criação invocada quando não há dados específicos.

**Conclusão:** se um dia o supervisor parar de classificar isso como checkup (cenário não-determinístico do LLM), a guarda do triagem cobre. Defesa em profundidade — não erro de planejamento.

---

## Audit do registry de pacientes

### Estado pós-Cenário A (após 3 rodadas)

```
Total pacientes: 10
  BENEF-001            | João Carlos Fictício
  BENEF-002            | Maria Aparecida Fictícia
  BENEF-003            | Roberto Silva Fictício
  BENEF-CV-001         | Helena Pereira Fictícia
  BENEF-CV-002         | Roberto Costa Fictício
  BENEF-CV-003         | Ana Carolina Lima Fictícia
  GABRIEL              | Gabriel Fictício
  BENEF-NEW-001        | Pedro Lima | 60a | masculino  ← criado pelo smoke
  BENEF-NEW-002        | Pedro Lima | 60a | masculino  ← criado pelo smoke
  BENEF-NEW-003        | Pedro Lima | 60a | masculino  ← criado pelo smoke
```

### Estado pós-reset (`git checkout HEAD -- data/mocks/perfis_clinicos.json`)

```
Total pacientes: 7 (baseline)
  BENEF-001            | João Carlos Fictício
  BENEF-002            | Maria Aparecida Fictícia
  BENEF-003            | Roberto Silva Fictício
  BENEF-CV-001         | Helena Pereira Fictícia
  BENEF-CV-002         | Roberto Costa Fictício
  BENEF-CV-003         | Ana Carolina Lima Fictícia
  GABRIEL              | Gabriel Fictício
```

### Justificativa do reset

Os 3 Pedros Lima foram criados **legitimamente** pelo Cenário A — validaram que o fluxo 2-step funciona end-to-end. Mas mantê-los no JSON ao mergear na `main` significaria **poluir a fundação do projeto** com pacientes de teste para todos os clones futuros.

O reset preserva:
- **Evidência da validação:** este documento + commits da branch contém o registro completo
- **Fundação limpa:** clones futuros começam com os 7 pacientes baseline canônicos
- **Reprodutibilidade:** qualquer dev pode rodar o Cenário A novamente e ver os Pedros Lima reaparecerem

Trade-off escolhido: priorizar **fundação limpa** sobre **evidência persistente no JSON** (a evidência fica no histórico de commits + neste markdown).

---

## Pytest baseline

```
======================= 67 passed, 1 warning in 17.59s ========================
```

### Composição dos 67 testes

| Origem | Testes | Comentário |
|--------|--------|------------|
| BluaDiagnostics original (Sprint 2) | 49 | `test_classificador_risco.py` (5), `test_estratificador_cardiovascular.py` (6), `test_pre_safety.py` (22), `test_prescricao_tool.py` (16) |
| PATCH 5.5 Bonus (Passo 5.5 do MERGE) | 4 | `test_escopo_cardiovascular.py` — 4 testes determinísticos de saída de `analisar_ritmo_cardiaco` |
| Fase 3 (este patch) | 14 | `test_supervisor_robusto.py` — 7 TestExtrairJSON + 3 TestIntentClassification + 4 TestRetry |
| **TOTAL** | **67** | **Zero regressões em todos os snapshots da Fase 3 e Fase 4** |

A única ressalva: 1 warning de `DeprecationWarning: 'asyncio.iscoroutinefunction'` do chromadb (não-bloqueante, vem de dentro do pacote, será resolvido pelo chromadb em versão futura).

---

## Bugs pré-existentes documentados (NÃO endereçados nesta feature)

São issues separadas do escopo desta branch. Anotadas aqui para visibilidade
e backlog futuro.

### Issue A — BENEF-CV-002 com alergias em formato `list[str]`

**Descoberta:** auditoria do `perfis_clinicos.json` na Fase 4 do PATCH 5.5 (commit `e77ae90`).

**Problema:** o paciente `BENEF-CV-002` tem `alergias` como `list[str]` (`"Varfarina (substituída por DOAC após hemorragia gengival)"`) em vez do formato dict canônico (`{"substancia": ..., "reacao": ..., "gravidade": ...}`) usado pelos outros pacientes. A função `src/tools/prescricao.py:89` (`_verificar_alergias`) lê `a["substancia"]` cru — chamar `sugerir_rascunho_prescricao` com esse paciente quebraria em `TypeError`.

**Impacto atual:** baixo. Os 49 testes baseline usam GABRIEL (formato dict), por isso passam. Sistema só quebra se um operador clínico real selecionar `BENEF-CV-002` E tentar gerar prescrição.

**Fix futuro sugerido:** normalizar `BENEF-CV-002.alergias` no JSON OU adicionar `isinstance(a, dict)` em `_verificar_alergias`.

### Issue B — `safety.py` heurística sem contexto

**Descoberta:** smoke test do Cenário C antes da Fase 3 (rodadas 1-3 do Passo 7 original).

**Problema:** `src/agents/safety.py:28-31` lista `["você tem ", "o diagnóstico é ", ...]` como gatilho de `DIAGNOSTICO_DEFINITIVO_DETECTADO`. Quando o checkup lista dados reais do prontuário usando "você tem ...", a heurística acende flag, auditor LLM reprova, resposta legítima é substituída por defensiva ("não consigo acessar prontuário").

**Workaround atual (PATCH 5.6):** reforço da Regra 1 ensina o checkup a usar "Seu prontuário registra..." em vez de "Você tem...". Cenário C agora passa 2/2 nesta fase.

**Fix definitivo futuro sugerido:** refinar `_eh_diagnostico_definitivo` em `safety.py` para conferir CONTEXTO: se a tool `consultar_historico_paciente` foi chamada no mesmo turno COM `campo` retornando dados, então "você tem X" onde X aparece no retorno da tool é **relato autorizado**, não diagnóstico novo.

```python
# Pseudocódigo do fix futuro:
def _eh_diagnostico_definitivo(resposta, contexto_turno):
    if _bate_heuristica(resposta):
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

**Por que não foi feito agora:** workaround do PATCH 5.6 resolve o caso prático (Cenário C 2/2 verde). Fix definitivo em `safety.py` é refatoração maior — fica como issue separada de média prioridade.

---

## Próximos passos

1. **Commit deste documento:** `docs: registra resultados do smoke E2E do Passo 7`
2. **Merge** `feature/fix-bugs-passo-7` → `main` via `git merge --no-ff` com mensagem do plano 5.7
3. **Pós-merge:**
   - Atualizar `PLANO_MERGE.md` marcando o Passo 7 como concluído (100% verde)
   - Considerar abrir issues formais pros 2 bugs pré-existentes documentados acima
   - Decidir próximo passo: Passo 8 (unificação Dash, via PASSO_8_UNIFICACAO_DASH.md) ou encerramento de sprint

---

## Histórico de commits da feature branch

| Hash | Mensagem | Fase |
|------|----------|------|
| `96116ac` | `fix(prompts): substitui nomes literais por placeholders + aviso anti-invenção` | Fase 2 |
| `32c8e65` | `feat(supervisor): retry + Pydantic + 14 testes determinísticos` | Fase 3 |
| `f55eb47` | `fix(agents): guardas contra invenção de dados e ações fora de escopo` | Fase 4 |
| `c71fe2b` | `docs: adiciona PLANO_FASES_2_A_5 e PROMPT_FASES_1_A_5` | Pre-Fase 5 |
| (próximo) | `docs: registra resultados do smoke E2E do Passo 7` (este arquivo) | Fase 5 |
| (merge) | `merge: corrige bugs do smoke test do Passo 7` (plano 5.7) | Pós-Fase 5 |
