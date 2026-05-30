# PROMPT_FASES_1_A_5.md

> Cole o bloco abaixo na primeira mensagem da sessão do Claude Code Desktop, dentro do diretório raiz do projeto `blua-cardio`. Pré-requisito: PATCH_5.5 e PATCH_5.6 aplicados e commitados em `main`. Working tree com o fix do supervisor ainda como `M` (não commitado).

---

```
Você é um engenheiro de software sênior e vai me ajudar a corrigir 3 bugs
arquiteturais descobertos durante o smoke test do Passo 7 da merge entre
BluaDiagnostics e cardiac_dashboard_dash.

CONTEXTO IMPORTANTE:

Estado atual:
- Passos 0-6 do PLANO_MERGE.md concluídos e commitados.
- PATCH_5.5 (disciplina de escopo) aplicado e commitado.
- PATCH_5.6 (reforço Regra 1 do checkup) aplicado e commitado.
- Smoke test do Passo 7 em andamento. Cenários B e C verdes. Cenários
  A e D expuseram 3 bugs pré-existentes do BluaDiagnostics Sprint 2.
- Fix parcial do supervisor está no working tree como `M`, NÃO commitado.

3 BUGS A CORRIGIR (em ordem de severidade):

#1 Supervisor falha em parsear JSON ~30% das vezes
   - Causa: LLM emite texto extra antes/depois do JSON, sem retry, sem validação.
   - Sintoma: fallback indevido pra intent=triagem com confiança 0.50.
   - Severidade: ALTA (~33% de roteamento errado).

#2 Triagem alucina "perfil criado" quando recebe "Sim, pode criar" sem contexto
   - Causa: triagem não tem `criar_perfil_paciente` em suas tools, mas
     responde como se tivesse criado.
   - Sintoma: usuário vê "Perfil criado com sucesso!" mas JSON inalterado.
     UX-fraude.
   - Severidade: GRAVE (engana o usuário em sistema médico).

#3 Checkup inventa dados clínicos em pedidos vagos
   - Causa: LLM Qwen tem viés determinístico — gera arquétipo de paciente
     CV ("João Silva 58 anos HAS dislipidemia tabagismo") quando recebe
     pedido vago.
   - Hipótese consolidada: o NOME "João Silva" vem de exemplo no system
     prompt do supervisor (anchoring). Os outros atributos vêm de viés
     do LLM treinado em conteúdo médico.
   - Sintoma: checkup chama criar_perfil_paciente(confirmacao=False)
     com dados inventados, retorna preview enganoso.
   - Severidade: MÉDIA (defesa do confirmacao=False segura, mas viola
     Regra "não invente dados").

PLANO EM 5 FASES (total estimado: 2h10-2h25):

REGRAS OBRIGATÓRIAS (não negociáveis):

1. Trabalhe UMA fase de cada vez, na ordem. Não pule, não combine.
2. Antes de cada fase, releia esta seção do plano. Mostre ao usuário
   um resumo de 1-2 frases do que vai fazer.
3. NÃO avance pra próxima fase enquanto TODAS as validações da fase
   atual passarem.
4. Se uma validação falhar: PARE imediatamente, mostre output completo
   do erro, e espere instrução do usuário. NÃO tente "consertar e seguir".
5. Pytest baseline (49 originais + 4 PATCH_5.5 + futuros 8 do supervisor)
   DEVE continuar verde após cada fase. Backwards compat é não-negociável.
6. Trabalhe na branch `feature/fix-bugs-passo-7`. Crie agora.
7. Commits pequenos e atômicos: 1 commit por fase, em pt-BR, estilo
   Conventional Commits.
8. Antes de modificar QUALQUER arquivo, mostre diff proposto e peça
   confirmação explícita do usuário.
9. Após cada fase, mostre `git log --oneline -5` e aguarde "pode seguir
   pra próxima fase" antes de avançar.
10. Linguagem dos commits, comentários e prompts: pt-BR.

================================================================
FASE 1 — INVESTIGAÇÃO EXPERIMENTAL DO VIÉS (15min, ZERO EDIÇÃO)
================================================================

Objetivo: confirmar experimentalmente que o "perfil arquétipo CV"
inventado pelo checkup é viés do LLM, e não algo mais sutil (cache,
leak, memo).

Procedimento:
1. Executar 3 processos Python independentes (kill+restart entre cada).
2. Em cada um, enviar EXATAMENTE a mensagem: "Crie um paciente fictício
   para teste"
3. Capturar pra cada rodada:
   - Intent classificada
   - Agent que respondeu
   - Tool chamada (sim/qual) e valor de confirmacao
   - Nome, idade, sexo, condições, outros atributos inventados
   - Safety flags
   - Primeira frase da resposta

Importante:
- Terminal NOVO entre rodadas (não reusar shell).
- thread_id fixo nas 3 rodadas (confirma diagnóstico de zero leak).
- Não editar nada de código nesta fase.

Critério de interpretação:
- Nomes/idades/condições variados → viés normal de LLM. OK, segue Fase 2.
- Mesmo nome em 2-3/3 mas outros variam → anchoring no supervisor. Confirma. Segue Fase 2.
- IDÊNTICOS em 3/3 (nome, idade, condições) → PARAR. Investigar mais.

Apresentar resultado em tabela ao usuário. Aguardar confirmação antes
de avançar pra Fase 2.

Validação Fase 1: usuário aprova interpretação.

Sem commit nesta fase (zero edição).

================================================================
FASE 2 — SANITIZAÇÃO DO SUPERVISOR (20min)
================================================================

Objetivo: substituir nomes literais ("João Silva", "Pedro Lima") no
system prompt do supervisor por placeholders <NOME>, <IDADE>, etc.

Localizar o trecho atualmente em working tree como `M` (não commitado)
e ajustar:

```diff
-**Usuário**: "Quero me cadastrar: João Silva, 45 anos, masculino, com hipertensão"
+**Usuário**: "Quero me cadastrar: <NOME>, <IDADE> anos, <SEXO>, com <CONDICAO>"
 → `{"intent": "checkup", "confianca": 0.96}`

-**Usuário**: "Pode criar um perfil novo? Sou Pedro Lima, 60 anos, com fibrilação atrial."
+**Usuário**: "Pode criar um perfil novo? Sou <NOME>, <IDADE> anos, com <CONDICAO>."
 → `{"intent": "checkup", "confianca": 0.95}`
```

Adicionar aviso após os exemplos:
"Importante: os marcadores <NOME>, <IDADE>, etc. são placeholders.
Os dados reais virão do usuário em runtime. Você NUNCA deve preencher
esses placeholders com valores inventados — sua tarefa é apenas
classificar a intenção da mensagem, não criar dados."

Validação:
- Refazer experimento da Fase 1 (3 sessões com "Crie paciente fictício").
- Esperado: zero menções a "João Silva" ou "Pedro Lima" em qualquer rodada.
- Os outros atributos arquetípicos (idade, condições) podem persistir —
  tratados na Fase 4.
- Pytest verde (não tocamos código de teste).

Critério de parada:
- Se "João Silva" ainda aparece em alguma rodada: PARAR, mostrar trecho,
  verificar se há OUTRO arquivo com nome literal. Pode haver outro lugar
  ainda não sanitizado.

Commit:
```
fix(supervisor): substitui nomes literais por placeholders em exemplos

[corpo conforme PATCH original]
```

================================================================
FASE 3 — ESTABILIZAÇÃO DO SUPERVISOR (45-60min)
================================================================

Objetivo: reduzir taxa de fallback indevido de ~33% para <5%.

3 camadas:

3.1 Retry com backoff (até 3 tentativas antes do fallback)
3.2 Extração robusta de JSON (aceita preâmbulo/pós-âmbulo do LLM)
3.3 Validação Pydantic da saída (intent ∈ {checkup,suporte,prescricao,triagem})
3.4 Testes determinísticos novos (8 testes, arquivo tests/test_supervisor_robusto.py)

Localizar arquivo do supervisor (provavelmente src/agents/supervisor.py):
```bash
grep -rn "def.*classific\|json.loads\|json.JSONDecodeError" src/ --include="*.py" | head
```

Implementar as 3 camadas conforme estrutura detalhada em
PATCH_5.7_FASE_3.md (vou colar abaixo se você pedir).

Validação 3.4:
- `pytest tests/test_supervisor_robusto.py -v` → 8/8 verdes.
- Pytest completo: BASELINE + 8 novos = todos verdes.
- Smoke manual Cenário A 5x → 5/5 com intent=checkup (antes: ~2/3).

Critério de parada:
- Algum teste novo falha: PARAR, mostrar trace.
- Pytest legado quebra: reverter alterações, PARAR.
- Smoke Cenário A ainda dá fallback em >1/5: PARAR, investigar.

Commit:
```
fix(supervisor): retry + extração robusta + validação Pydantic
[corpo conforme plano]
```

================================================================
FASE 4 — GUARDAS CONTRA INVENÇÃO E AÇÕES FORA DE ESCOPO (30min)
================================================================

Objetivo: 2 fixes em system prompts diferentes (triagem + checkup).

4.1 Triagem (bug #2):
Localizar system prompt do triagem (src/agents/triagem.py ou similar).
Adicionar bloco "Limitações de escopo do triagem" com:
- Lista explícita do que NÃO pode fazer (criar perfil, confirmar sem
  contexto, listar histórico, prescrever).
- Frases-modelo de recusa cordial direcionando ao agent correto.
- Regra: "Sim/confirmo" sem contexto prévio → pedir clarificação,
  NÃO inventar criação.

4.2 Checkup (bug #3):
Localizar system prompt do checkup (onde estão Regras 1-3 do PATCH_5.5
e reforço do PATCH_5.6). Adicionar Regra 4:
"Recusar pedidos vagos de cadastro. NUNCA inventar nome/idade/condições.
Pedir dados reais ao usuário com explicação cordial."

Incluir exemplos ✅ (resposta correta de recusa cordial) e ❌ (resposta
proibida: "Claro! Criando João Silva 58 anos HAS...").

Validação manual:
- "Sim, pode criar" isolado → triagem recusa, zero alucinação de criação.
- "Crie paciente fictício" → checkup recusa, NÃO chama tool.
- Conferir registry: zero pacientes fictícios criados.

Critério de parada:
- Triagem ainda inventa "perfil criado": PARAR. Reforçar regra com
  versão imperativa (mesma técnica do PATCH_5.6 §6).
- Checkup ainda chama criar_perfil_paciente em pedido vago: PARAR.
  Reforçar Regra 4.

Commit:
```
fix(agents): guarda contra invenção de dados e ações fora de escopo
[corpo conforme plano]
```

================================================================
FASE 5 — VALIDAÇÃO END-TO-END (20min)
================================================================

Objetivo: confirmar que os 3 bugs sumiram, sem regressões.

Smoke tests:
1. Cenário A (cadastro 2-step com dados reais) 3x → 3/3 sucesso.
2. Cenário D (pedido vago) 3x → 3/3 recusa, zero criações.
3. "Sim, pode criar" isolado 3x → 3/3 recusa contextual.
4. Cenário C revisitado (BENEF-001 condições) 2x → 2/2 "Seu prontuário
   registra" (PATCH_5.6 não regrediu).

Pytest completo:
- BASELINE (49) + PATCH_5.5 Bonus (4) + Fase 3 novos (8) = 61 testes.
- Esperado: 61/61 verdes.

Audit do registry:
```bash
python -c "
from shared.patient_registry import list_patients
ficticios = [p for p in list_patients() if any(t in p['nome'].lower() for t in ['fictic', 'teste', 'joão silva'])]
print('Fictícios criados:', ficticios)
"
# Esperado: lista vazia.
```

Critério de parada:
- Qualquer cenário falha: PARAR, identificar fase responsável, reverter.
- Pytest quebra: PARAR.
- Registry tem fictícios: PARAR. Limpar manualmente E investigar como
  foram criados (alguma regra falhou).

Commit:
```
test: validação end-to-end pós-fixes dos bugs #1, #2, #3
[corpo conforme plano]
```

================================================================
APÓS FASE 5 — MERGE NO MAIN
================================================================

```bash
git checkout main
git merge --no-ff feature/fix-bugs-passo-7 -m "merge: corrige bugs do smoke test do Passo 7

Resolve bugs #1 (supervisor JSON), #2 (triagem alucina criação),
#3 (checkup inventa dados). Todos pré-existentes do Sprint 2.

Smoke test Passo 7 agora 100% verde."
```

================================================================
PRIMEIRA AÇÃO:
================================================================

1. Confirmar que está na branch correta:
   - Se em main → criar `feature/fix-bugs-passo-7`.
   - Se já em feature branch → confirmar nome com usuário.
2. Mostrar `git status` (esperado: working tree com o fix do supervisor
   como `M`).
3. Mostrar `git log --oneline -5` (últimos commits).
4. Confirmar com usuário: "Estado correto pra começar Fase 1? (sim/não)"
5. Aguardar "sim" antes de iniciar Fase 1.

Não pule nenhum desses 5 itens iniciais.
```

---

## Como usar este prompt

1. Salve este arquivo na raiz do repo `blua-cardio` (ao lado do `PLANO_MERGE.md`).
2. Abra o Claude Code Desktop apontando pra `blua-cardio/`.
3. Cole o bloco de prompt acima como primeira mensagem.
4. Responda as perguntas dele conforme o plano avança.
5. Em cada fase: leia o diff proposto, valide, e libere a próxima só após validação passar.

## Observações

- **O prompt usa "branch `feature/fix-bugs-passo-7`"** porque envolve correção de bugs reais. Não trabalhar direto em `main` neste caso — quero proteção pra reverter facilmente se algo der ruim.
- **Cada fase tem critério de parada claro.** Se travar, traz o output aqui que destravamos.
- **A Fase 1 é só investigação.** Se o experimento mostrar resultado inesperado (3/3 idênticos, por exemplo), o plano muda — me chama antes de continuar.
- **Fases 2-5 são todas aditivas a system prompts ou adicionam código de robustez.** Nenhuma remove funcionalidade existente.

Bora.
