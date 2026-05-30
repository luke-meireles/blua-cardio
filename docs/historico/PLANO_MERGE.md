# PLANO_MERGE.md

**Projeto:** novo repositório `blua-cardio` (nome de trabalho — pode ser alterado), baseado em código do `BluaDiagnostics` e do `cardiac_dashboard_dash`, mas tratado como **projeto novo com identidade própria**.
**Branch principal:** `main` (sem branch feature — cada passo do plano vira um commit atômico direto em `main`)
**Versão do plano:** 1.1
**Data:** 2026-05-27

---

## Sumário

Vamos integrar o dashboard cardíaco ao chatbot em **8 passos atômicos**. Cada passo é independente, tem comando(s) de validação, e gera um commit próprio. O passo 8 é opcional e pode ficar para um sprint seguinte.

| # | Objetivo | Tempo | Risco |
|---|----------|-------|-------|
| 0 | Inicialização do projeto novo (scaffolding) | 15min | médio (muito file copy) |
| 1 | Bridge layer `shared/` | 5min | baixo |
| 2 | Renomear paciente MARIA → GABRIEL | 10min | médio (toca em dados + testes) |
| 3 | Upgrade `analisar_ritmo_cardiaco` com live mode | 5min | médio (substitui arquivo de produção) |
| 4 | Adicionar tools `criar_perfil` + `telemetria` | 5min | baixo |
| 5 | Registrar tools nos agents do LangGraph | 15min | alto (requer leitura do código do agent) |
| 6 | Atualizar dependências (`pandas`) | 3min | nenhum |
| 7 | Smoke test end-to-end manual | 15min | — |
| 8 | (opcional) Unificar Dash apps em `unified_app.py` | 60min | alto (refatoração) |

**Regra de ouro:** validação falhou → para tudo, reporta, espera instrução. Nada de "vou consertando enquanto avanço".

---

## Passo 0 — Inicialização do projeto novo (scaffolding)

### 0.1 Objetivo
Montar a estrutura inicial do projeto novo `blua-cardio`, partindo de um diretório vazio com `git init`. Copiar o código de base do `BluaDiagnostics` (chatbot LangGraph) e os dados do `cardiac_dashboard_dash`, validar baseline pytest verde, e fazer commit inicial.

### 0.2 Pré-requisitos (responsabilidade do USUÁRIO antes de chamar este passo)
- Diretório `blua-cardio/` criado e com `git init` executado.
- Pastas `PLANO_MERGE.md`, `PROMPT_INICIAL.md`, `blua_merge_files/` já posicionadas na raiz do novo repo.
- Os dois projetos originais extraídos em algum lugar acessível da máquina (zips descompactados).
- Python 3.10+ disponível.

### 0.3 Ações

**0.3.1 — Perguntar ao usuário os paths origem:**
```
Antes de copiar nada, preciso confirmar dois paths:

a) Onde está o BluaDiagnostics extraído?
   (ex.: ~/projetos/BluaDiagnostics_Sprint-main)

b) Onde está o cardiac_dashboard_dash extraído?
   (ex.: ~/projetos/cardiac_dashboard_dash)
```
Guardar as respostas como `$BLUA_SRC` e `$DASH_SRC`. Confirmar com `ls "$BLUA_SRC"` e `ls "$DASH_SRC"` antes de prosseguir.

**0.3.2 — Copiar foundation do chatbot (BluaDiagnostics):**
```bash
# Substituir $BLUA_SRC pelo path real informado
cp -r "$BLUA_SRC/src"        ./src
cp -r "$BLUA_SRC/app"        ./app
cp -r "$BLUA_SRC/data"       ./data
cp -r "$BLUA_SRC/tests"      ./tests
cp    "$BLUA_SRC/pyproject.toml" ./pyproject.toml
cp    "$BLUA_SRC/.gitignore"     ./.gitignore 2>/dev/null || touch .gitignore

# RAG ChromaDB se existir
[ -d "$BLUA_SRC/chroma_db" ] && cp -r "$BLUA_SRC/chroma_db" ./chroma_db

# Mover README antigo pra referência (sem sobrescrever — criaremos um novo)
[ -f "$BLUA_SRC/README.md" ] && cp "$BLUA_SRC/README.md" ./README_blua_original.md

# Conferir
ls -la
```

**0.3.3 — Atualizar identidade no `pyproject.toml`:**

Editar `pyproject.toml`: trocar o campo `name` (e quaisquer outras strings de identificação) de `"BluaDiagnostics"` (ou equivalente) para `"blua-cardio"`. Mostrar diff ao usuário.

**0.3.4 — Copiar dados do dashboard:**
```bash
# Dado de referência (200 batimentos do paciente Gabriel) — obrigatório
cp "$DASH_SRC/data/gabriel_data.csv" ./data/gabriel_data.csv

# CSV ao vivo do ESP32 — copiar se já existir; senão será criado quando o ESP32 rodar
[ -f "$DASH_SRC/data/cardiac_data.csv" ] && \
    cp "$DASH_SRC/data/cardiac_data.csv" ./data/cardiac_data.csv

ls -la data/
```

**0.3.5 — Reservar código do dashboard para integração futura (Passo 8):**
```bash
mkdir -p dashboard_legacy
cp -r "$DASH_SRC/pages"  ./dashboard_legacy/pages
cp    "$DASH_SRC/app.py" ./dashboard_legacy/app.py
# Componentes/assets, se existirem
[ -d "$DASH_SRC/components" ] && cp -r "$DASH_SRC/components" ./dashboard_legacy/components
[ -d "$DASH_SRC/assets" ]     && cp -r "$DASH_SRC/assets"     ./dashboard_legacy/assets

echo "Conteúdo de dashboard_legacy/ será integrado no Passo 8 (opcional)." \
    > ./dashboard_legacy/README.md
```

**0.3.6 — README do projeto novo:**

Criar `./README.md` com este conteúdo (ajustar nome se o usuário escolher outro):

```markdown
# blua-cardio

Plataforma cardiovascular integrada: chatbot multi-agente (LangGraph, pt-BR)
+ dashboard de telemetria PPG/BPM ao vivo de ESP32 + MAX30100.

Projeto novo nascido da união de duas bases anteriores:
- BluaDiagnostics (chatbot)
- cardiac_dashboard_dash (dashboard)

## Status
Em construção. Plano de integração em `PLANO_MERGE.md`.

## Stack
- Python 3.10+
- LangGraph + Qwen (via DashScope/Ollama)
- Dash (UI)
- ChromaDB (RAG)
- pandas (telemetria)

## Como rodar (após Passo 5 do PLANO_MERGE.md)
Ver `PLANO_MERGE.md` → Passo 7 (smoke tests).
```

**0.3.7 — Criar ambiente virtual e instalar deps:**
```bash
python -m venv .venv
# Linux/Mac:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -e ".[dev]" 2>&1 | tail -5
# ou: pip install -r requirements.txt -r requirements-dev.txt
```

**0.3.8 — Baseline do pytest:**
```bash
pytest --tb=short 2>&1 | tail -5
# Esperado: 49 testes passando (vindos do BluaDiagnostics).
# Gravar este número como BASELINE — referência para os próximos passos.
```

**0.3.9 — Commit inicial:**
```bash
git add -A
git status   # mostrar pro usuário ANTES de commitar
```

Mostrar `git status` ao usuário e pedir confirmação antes do `git commit`:

```bash
git commit -m "chore: scaffolding inicial do blua-cardio

Projeto novo derivado de BluaDiagnostics + cardiac_dashboard_dash.

- Foundation do chatbot copiada de BluaDiagnostics_Sprint-main
- gabriel_data.csv (200 beats de referência) importado do dashboard
- dashboard_legacy/ reservado para integração futura (Passo 8)
- blua_merge_files/ com bridge layer (shared/) e tools novas
- PLANO_MERGE.md com plano de 8 passos
- Identidade no pyproject.toml atualizada para blua-cardio

Baseline: 49 testes pytest passando."
```

### 0.4 Validação

```bash
# 0.4.1 — Git limpo e com commit inicial
git log --oneline
# Esperado: 1 commit (o chore: scaffolding inicial).
git status
# Esperado: "nothing to commit, working tree clean".

# 0.4.2 — Estrutura de pastas
ls -la
# Esperado ver:
#   .git/  .gitignore  .venv/
#   PLANO_MERGE.md  PROMPT_INICIAL.md  README.md  README_blua_original.md
#   app/  blua_merge_files/  chroma_db/  dashboard_legacy/  data/
#   pyproject.toml  src/  tests/

# 0.4.3 — Pytest baseline verde
pytest --tb=short 2>&1 | tail -5
# Esperado: 49 testes passando.

# 0.4.4 — Dados do dashboard chegaram
ls -la data/
# Esperado ver: gabriel_data.csv (obrigatório), mocks/, cardiac_data.csv (opcional)

# 0.4.5 — Identidade nova no pyproject
grep '^name' pyproject.toml
# Esperado: name = "blua-cardio" (ou nome escolhido)
```

### 0.5 Critério de parada
- Pytest baseline já vermelho: o problema é do BluaDiagnostics original ou da cópia de arquivos. **PARAR**, reportar, investigar antes de avançar.
- Algum dos paths origem (`$BLUA_SRC` ou `$DASH_SRC`) não existe ou está vazio: **PARAR**, perguntar ao usuário novamente.
- `pyproject.toml` não tem campo `name` óbvio: **PARAR**, mostrar o arquivo ao usuário e perguntar onde editar.

---

## Passo 1 — Bridge layer (`shared/`)

### 1.1 Objetivo
Criar a camada de ponte entre chatbot e dashboard. Esta é a única forma como os dois lados se enxergam.

### 1.2 Ações

```bash
# Criar diretório
mkdir -p shared

# Copiar os 4 arquivos da pasta de merge
cp blua_merge_files/shared/__init__.py        shared/
cp blua_merge_files/shared/paths.py            shared/
cp blua_merge_files/shared/patient_registry.py shared/
cp blua_merge_files/shared/telemetry_store.py  shared/

# Confirmar
ls -la shared/
```

### 1.3 Validação

```bash
# 1.3.1 — imports e listagem de pacientes
python -c "from shared import list_patients; print('Pacientes:', len(list_patients()))"
# Esperado: 'Pacientes: 7' (ou número correspondente aos mocks atuais)

# 1.3.2 — paths resolvem
python -c "from shared.paths import PROFILES_JSON, TELEMETRY_CSV, GABRIEL_CSV; print('PROFILES:', PROFILES_JSON.exists()); print('TELEMETRY:', TELEMETRY_CSV.exists() or '(sem CSV ainda)'); print('GABRIEL:', GABRIEL_CSV.exists())"
# Esperado: PROFILES True. GABRIEL True se o CSV do dashboard estiver presente.
# TELEMETRY pode ser False se o ESP32 ainda não rodou — tudo bem.

# 1.3.3 — pytest legado intacto
pytest --tb=short 2>&1 | tail -3
# Esperado: BASELINE passando, zero novos testes (shared não tem testes ainda).
```

### 1.4 Commit
```
feat(shared): adiciona bridge layer entre chatbot e dashboard

- shared/patient_registry: cadastro de pacientes com RLock e cache invalidation
- shared/telemetry_store: leitura de PPG/BPM do CSV do dashboard com aliases
- shared/paths: paths canônicos compartilhados, BLUA_ROOT env override
- shared/__init__: re-exports da API pública
```

### 1.5 Critério de parada
- `ImportError` em `from shared import list_patients`: verificar se `shared/__init__.py` tem `from .patient_registry import list_patients` corretamente.
- `PROFILES_JSON.exists()` retorna False: o path em `shared/paths.py` não está apontando para o `data/mocks/perfis_clinicos.json` real. **PARAR**, ajustar `PROFILES_JSON` em `shared/paths.py` para o path correto do projeto, e re-rodar.

---

## Passo 2 — Renomear MARIA → GABRIEL

### 2.1 Objetivo
Renomear a paciente mockada `MARIA` para `GABRIEL`, alinhando com o paciente de referência que o dashboard já usa (`gabriel_data.csv` com 200 batimentos).

### 2.2 Estratégia
Renomear é mais arriscado que adicionar. Antes de qualquer edit, mapeamos TODAS as ocorrências.

### 2.3 Ações

**2.3.1 — Inventário completo:**

```bash
# Buscar todas as referências (case-insensitive)
grep -rn -i "BENEF-MARIA\|MARIA" \
  --include="*.py" \
  --include="*.json" \
  --include="*.md" \
  --include="*.yaml" \
  --include="*.yml" \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=blua_merge_files \
  --exclude-dir=__pycache__ \
  --exclude-dir=.venv \
  2>/dev/null
```

**MOSTRAR essa lista ao usuário antes de qualquer edição.** Se aparecer MARIA num arquivo .py de produção (não-teste, não-mock, não-doc), pedir confirmação extra.

**2.3.2 — Editar `data/mocks/perfis_clinicos.json`:**

Localizar a entrada cuja chave seja `"MARIA"` ou `"BENEF-MARIA"`. Aplicar este diff conceitual:

```diff
-  "MARIA": {
-    "id": "MARIA",
-    "nome": "Maria <sobrenome>",
-    "sexo": "F",
+  "GABRIEL": {
+    "id": "GABRIEL",
+    "nome": "Gabriel",
+    "sexo": "M",
     "idade": 34,
     "condicoes_ativas": ["Hipertensão arterial sistêmica"],
     "medicamentos": [...],     # manter como estava
     "alergias": [...],          # manter como estava
     "historico_clinico": "..."  # manter como estava
   }
```

**Importante:**
- A chave do dicionário também muda (`"MARIA"` → `"GABRIEL"`).
- O campo `id` interno também muda.
- `sexo` muda para `"M"` (Gabriel é nome masculino).
- Demais campos (idade, condições, medicamentos, alergias, histórico) **permanecem iguais** — o caso clínico continua o mesmo, só o nome e sexo mudam.

**Mostrar o diff ao usuário antes de salvar.**



**2.3.3 — Editar `shared/telemetry_store.py` (várias ocorrências):**

Há **pelo menos 4 referências** a `BENEF-MARIA` neste arquivo. Confirmar com:
```bash
grep -n "BENEF-MARIA" shared/telemetry_store.py
```

Aplicar substituição global do **valor da chave** `"BENEF-MARIA"` por `"GABRIEL"`:

- **Linha ~26-29 (dict `_ALIAS`):**
  ```diff
   _ALIAS: dict[str, list[str]] = {
  -    "BENEF-MARIA": ["BENEF-MARIA", "Gabriel", "live", "live-sim"],
  +    "GABRIEL": ["GABRIEL", "Gabriel", "live", "live-sim"],
       # ...demais aliases mantidos
   }
  ```

- **Linha ~78 (hardcoded check no fallback para `gabriel_data.csv`):**
  ```diff
  -    if fallback_to_gabriel and paciente_id == "BENEF-MARIA":
  +    if fallback_to_gabriel and paciente_id == "GABRIEL":
           gab = _read_csv_safe(GABRIEL_CSV)
  ```

- **Comentários e docstrings:** substituir todas as menções a "BENEF-MARIA" por "GABRIEL" no texto explicativo (ex.: "BENEF-MARIA é a paciente canônica do enunciado Sprint 2" → "GABRIEL é o paciente canônico do enunciado Sprint 2"). Trocar pronomes/concordância: "a paciente canônica" → "o paciente canônico", "BENEF-MARIA, e ele" → "GABRIEL, e ele".

**Conferência final do arquivo após edição:**
```bash
grep -n "MARIA\|maria" shared/telemetry_store.py
# Esperado: sem nenhum resultado (rename completo).
```

**2.3.4 — Atualizar testes:**

```bash
# Localizar referências nos testes
grep -rn "MARIA\|BENEF-MARIA" tests/ 2>/dev/null
```

Para cada match:
- Substituir `"MARIA"` por `"GABRIEL"` na string.
- Substituir `"BENEF-MARIA"` por `"GABRIEL"`.
- Se um teste valida explicitamente `nome == "Maria"` ou `sexo == "F"`: ajustar para `"Gabriel"` e `"M"`.

**Mostrar o diff de cada arquivo de teste ao usuário antes de salvar.**

**2.3.5 — Atualizar docs (se aplicável):**

```bash
grep -rn "MARIA\|BENEF-MARIA" *.md docs/ 2>/dev/null
```

README, CHANGELOG, qualquer .md que mencione a paciente MARIA: ajustar para Gabriel.

### 2.4 Validação

```bash
# 2.4.1 — Perfil acessível pelo novo ID
python -c "
from shared.patient_registry import get_patient
p = get_patient('GABRIEL')
print('Nome:', p['nome'])
print('Sexo:', p['sexo'])
print('Idade:', p['idade'])
assert p['nome'] == 'Gabriel', 'Nome não foi atualizado'
assert p['sexo'] == 'M', 'Sexo não foi atualizado'
print('OK')
"
# Esperado: Nome: Gabriel | Sexo: M | Idade: 34 | OK

# 2.4.2 — Alias do dashboard funcionando
python -c "
from shared.telemetry_store import latest_beat
b = latest_beat('GABRIEL')
if b is None:
    print('Sem dados de telemetria (esperado se ESP32 não rodou e gabriel_data.csv não está em data/)')
else:
    print('BPM:', b['BPM'], '| fonte OK')
"
# Esperado: BPM numérico (do gabriel_data.csv fallback) OU mensagem de "sem dados".

# 2.4.3 — MARIA não acessível
python -c "
from shared.patient_registry import patient_exists
assert patient_exists('GABRIEL'), 'GABRIEL deveria existir'
assert not patient_exists('MARIA'), 'MARIA deveria ter sido renomeado'
assert not patient_exists('BENEF-MARIA'), 'BENEF-MARIA deveria ter sido renomeado'
print('OK — MARIA totalmente substituído por GABRIEL')
"

# 2.4.4 — Pytest verde
pytest --tb=short 2>&1 | tail -5
# Esperado: BASELINE passando.
```

### 2.5 Commit
```
refactor(data): renomeia paciente MARIA para GABRIEL

- Alinha com o paciente de referência do dashboard (gabriel_data.csv, 200 beats)
- Atualiza perfis_clinicos.json: chave, id, nome, sexo (F→M)
- Atualiza _ALIAS em shared/telemetry_store.py
- Atualiza testes que referenciavam MARIA
- Atualiza docs

Caso clínico (idade 34, hipertensão, etc.) preservado intacto.
```

### 2.6 Critério de parada
- Se o grep do passo 2.3.1 encontrar MARIA em código de produção (não-teste, não-mock JSON, não-doc): **PARAR**, mostrar o trecho exato ao usuário, pedir decisão.
- Se pytest falhar após o rename: rodar `pytest --tb=long` completo, identificar quais testes quebraram, mostrar ao usuário antes de tentar consertar.

---

## Passo 3 — Upgrade `analisar_ritmo_cardiaco` com live mode

### 3.1 Objetivo
Substituir `src/tools/ritmo.py` pela versão upgrade que aceita `paciente_id` opcional para ler telemetria ao vivo, **mantendo backwards compatibility total** com a assinatura legada.

### 3.2 Ações

```bash
# Backup defensivo
cp src/tools/ritmo.py src/tools/ritmo.py.bak

# Substituir
cp blua_merge_files/src/tools/ritmo.py src/tools/ritmo.py

# Conferir diff (espera-se grande, mas só na ritmo.py)
git diff src/tools/ritmo.py | head -40
```

**Mostrar diff completo ao usuário antes de avançar para validação.**

### 3.3 Validação

```bash
# 3.3.1 — CRÍTICO: backwards compat — signature legada continua funcionando
python -c "
from src.tools.ritmo import analisar_ritmo_cardiaco
r = analisar_ritmo_cardiaco(
    timestamp_s=0, IBI_ms=800, BPM=75,
    media_IBI=800, desvio_medio=50, batimentos_anormais=0
)
print('Legacy mode classificacao:', r['classificacao'])
assert 'classificacao' in r
print('OK — modo legado funcionando')
"

# 3.3.2 — Live mode com GABRIEL
python -c "
from src.tools.ritmo import analisar_ritmo_cardiaco
r = analisar_ritmo_cardiaco(paciente_id='GABRIEL')
print('Live mode classificacao:', r['classificacao'])
print('Fonte:', r.get('fonte'))
print('Observacao:', r.get('observacao', '')[:200])
"
# Esperado: classificacao em {regular, atencao, irregular}, fonte='dashboard_csv_live'.

# 3.3.3 — Live mode com paciente sem dados
python -c "
from src.tools.ritmo import analisar_ritmo_cardiaco
r = analisar_ritmo_cardiaco(paciente_id='BENEF-003')
print('Sem dados:', r.get('telemetria_disponivel'), '|', r.get('sugestao', '')[:80])
"
# Esperado: telemetria_disponivel=False, sugestao mencionando o dashboard.

# 3.3.4 — CRÍTICO: pytest completo
pytest --tb=long 2>&1 | tail -15
# Esperado: BASELINE passando. NENHUM teste novo falhando.
```

### 3.4 Commit
```
feat(tools): adiciona live mode em analisar_ritmo_cardiaco

- Novo parâmetro opcional paciente_id ativa leitura via shared/telemetry_store
- Signature legada (timestamp_s, IBI_ms, BPM, media_IBI, desvio_medio,
  batimentos_anormais) continua funcionando — backwards compat preservada
- Observação clínica enriquecida com idade, sexo e condições do paciente
- Fallback gracioso quando paciente não tem telemetria disponível
```

### 3.5 Critério de parada
- Se **qualquer** teste do pytest legado falhar: reverter (`cp src/tools/ritmo.py.bak src/tools/ritmo.py`), reportar trace completo do pytest, **PARAR**.

### 3.6 Limpeza após sucesso
```bash
rm src/tools/ritmo.py.bak
```

---

## Passo 4 — Adicionar tools `criar_perfil` e `telemetria`

### 4.1 Objetivo
Adicionar duas novas ferramentas ao chatbot:
- `criar_perfil_paciente`: cria perfil novo via chat (fluxo 2-step com confirmação).
- `consultar_telemetria_dashboard`: retorna sumário de BPM/IBI sem dar veredito clínico.

### 4.2 Ações

```bash
# Copiar arquivos novos
cp blua_merge_files/src/tools/criar_perfil.py src/tools/
cp blua_merge_files/src/tools/telemetria.py   src/tools/

# Atualizar __init__.py: comparar com a versão entregue
diff src/tools/__init__.py blua_merge_files/src/tools/__init__.py
```

**Para o `__init__.py`:** NÃO substituir cegamente. Comparar e adicionar **apenas** as linhas relativas a `criar_perfil_paciente` e `consultar_telemetria_dashboard` ao `__init__.py` atual. Se o atual tiver uma lista `__all__` ou `TOOLS = [...]`, adicionar os dois nomes nela.

**Mostrar o diff proposto do `__init__.py` ao usuário antes de salvar.**

### 4.3 Validação

```bash
# 4.3.1 — Imports
python -c "
from src.tools.criar_perfil import criar_perfil_paciente
from src.tools.telemetria import consultar_telemetria_dashboard
print('OK — tools importáveis')
"

# 4.3.2 — Preview de criação (sem efeito colateral)
python -c "
from src.tools.criar_perfil import criar_perfil_paciente
r = criar_perfil_paciente(
    nome='João Teste', idade=45, sexo='M',
    condicoes=['HAS'], confirmacao=False
)
print('Etapa:', r['etapa'])
print('Preview do paciente:', r['paciente']['nome'], '|', r['paciente']['condicoes_ativas'])
assert r['etapa'] == 'preview'
assert r['paciente']['condicoes_ativas'] == ['Hipertensão arterial sistêmica']
print('OK — normalização HAS funcionando')
"
# Esperado: condições normalizadas; o paciente NÃO foi salvo no JSON ainda.

# 4.3.3 — Telemetria
python -c "
from src.tools.telemetria import consultar_telemetria_dashboard
r = consultar_telemetria_dashboard(paciente_id='GABRIEL')
print('Telemetria disponível:', r.get('telemetria_disponivel'))
if r.get('sumario'):
    print('BPM médio:', r['sumario'].get('bpm_medio'))
"

# 4.3.4 — Pytest
pytest --tb=short 2>&1 | tail -3
# Esperado: BASELINE passando.

# 4.3.5 — Imports via __init__
python -c "
from src.tools import criar_perfil_paciente, consultar_telemetria_dashboard
print('OK — exports via __init__')
"
```

### 4.4 Commit
```
feat(tools): adiciona criar_perfil_paciente e consultar_telemetria_dashboard

- criar_perfil_paciente: fluxo 2-step (preview + confirmacao=True) para
  defender contra alucinação do LLM
- consultar_telemetria_dashboard: sumário de BPM/IBI sem dar veredito clínico
- Normalização de aliases de condições (HAS, FA, IC, DAC, DM, TEP, AVE)
- Auto-geração de IDs BENEF-NEW-NNN
- Atualiza src/tools/__init__.py para exportar as novas tools
```

### 4.5 Critério de parada
- Atualização do `__init__.py` quebra imports existentes em outros módulos: reverter o `__init__.py`, mostrar erro, **PARAR**.

---

## Passo 5 — Registrar tools nos agents do LangGraph

### 5.1 Objetivo
Fazer com que o(s) agent(s) saibam que as novas tools existem e quando usá-las.

### 5.2 Estratégia
Esta é a parte mais delicada porque depende da estrutura específica dos agents do projeto. **Investigar antes de editar.**

### 5.3 Ações

**5.3.1 — Localizar onde tools são registradas:**

```bash
# Pista 1: onde analisar_ritmo_cardiaco aparece (além da definição)
grep -rn "analisar_ritmo_cardiaco" src/ --include="*.py"

# Pista 2: padrões comuns de registro
grep -rn "tools=\[\|ToolNode\|bind_tools\|@tool" src/ --include="*.py"
```

**Esperado:** encontrar 2-4 arquivos:
- `src/tools/ritmo.py` (definição) — ignorar.
- Algum em `src/agents/*.py` ou `src/graph/*.py` (registro) — este é o alvo.

**MOSTRAR o resultado do grep ao usuário** antes de editar.

**5.3.2 — Adicionar imports no arquivo do agent:**

No arquivo identificado, adicionar (no topo, junto aos outros imports de tools):

```python
from src.tools.criar_perfil import criar_perfil_paciente
from src.tools.telemetria import consultar_telemetria_dashboard
```

**5.3.3 — Adicionar à lista de tools:**

Localizar a lista (ex.: `tools = [analisar_ritmo_cardiaco, ...]` ou `TOOLS_CLINICAS = [...]`). Adicionar:

```python
tools = [
    analisar_ritmo_cardiaco,
    # ... tools existentes ...
    criar_perfil_paciente,
    consultar_telemetria_dashboard,
]
```

**5.3.4 — Atualizar o system prompt do agent:**

Localizar o system prompt do agent que usa essas tools (provavelmente o "agent sênior" ou "agent clínico"). Adicionar instruções claras:

```
Você ganhou novas capacidades:

1. **Criar paciente novo**: use a tool `criar_perfil_paciente`.
   SEMPRE chame primeiro com `confirmacao=False` para mostrar preview ao
   usuário. Só chame com `confirmacao=True` APÓS confirmação explícita
   ("sim", "pode criar", "confirmo") do usuário no chat. Nunca crie um
   perfil sem essa confirmação de 2 passos.

2. **Consultar telemetria ao vivo**: use `consultar_telemetria_dashboard`
   quando o usuário quiser saber sobre BPM/ritmo atual sem pedir diagnóstico
   clínico (ex.: "qual meu BPM agora?", "quantos batimentos por minuto?").

3. **Diagnóstico de ritmo de paciente cadastrado**: use
   `analisar_ritmo_cardiaco` passando APENAS `paciente_id="<ID>"`
   (modo live). Os parâmetros antigos (IBI_ms, BPM, etc.) só são usados
   em testes — em produção sempre prefira o modo live.

4. **Paciente Gabriel**: o paciente com ID `GABRIEL` é o paciente de
   referência do dashboard. Ele tem dados de telemetria sempre disponíveis.
```

**5.3.5 — Mostrar o diff completo do arquivo do agent ao usuário ANTES de salvar.** Esta edição é a mais arriscada do plano inteiro.

### 5.4 Validação

```bash
# 5.4.1 — Graph constrói sem erro
python -c "
# Substituir pelo entrypoint correto do projeto
from src.graph import build_graph
g = build_graph()
print('Graph OK, nodes:', list(g.nodes.keys())[:5])
"
# Se o entrypoint for diferente: pedir ao usuário o comando correto.

# 5.4.2 — Pytest passa
pytest --tb=short 2>&1 | tail -3

# 5.4.3 — Smoke teste manual
# Subir o chatbot (ex: python -m app.dash_app) e testar via UI:
# Pergunta 1: "Quero cadastrar um paciente: João Silva, 50 anos, hipertensão"
# Esperado: agent chama criar_perfil_paciente(confirmacao=False), pede confirmação.
#
# Pergunta 2: "Sim, pode criar"
# Esperado: agent chama criar_perfil_paciente(confirmacao=True), retorna ID novo.
```

### 5.5 Commit
```
feat(agents): registra tools criar_perfil e telemetria no agent clínico

- Importa as duas novas tools
- Adiciona à lista de tools do agent
- Atualiza system prompt: fluxo 2-step de criar_perfil, live mode preferido
  para ritmo, contexto sobre paciente GABRIEL
```

### 5.6 Critério de parada
- Se o grep do 5.3.1 não localizar nenhum arquivo de registro: **PARAR**, mostrar resultado vazio, pedir ao usuário que aponte o arquivo manualmente.
- Se o system prompt tiver estrutura específica (tabela markdown, JSON estruturado, lista numerada formal): respeitar a estrutura existente, não reescrever do zero. Adaptar o trecho novo ao formato.
- Smoke teste manual da 5.4.3 falha (agent não chama as tools): **PARAR**, revisar se as tools foram realmente bindadas ao LLM e se o system prompt está sendo carregado.

---

## Passo 6 — Atualizar dependências

### 6.1 Objetivo
Garantir que `pandas` esteja nas deps (usado por `shared/telemetry_store.py`).

### 6.2 Ações

```bash
# Conferir se pandas já existe
grep -i "pandas" pyproject.toml requirements.txt 2>/dev/null
```

**Se já existe:** pular este passo, ir direto pro 7.

**Se não existe:** adicionar.

Em `pyproject.toml`, na seção `[project] dependencies`:
```toml
dependencies = [
    # ... existentes ...
    "pandas>=2.0",
]
```

Ou em `requirements.txt`:
```
pandas>=2.0
```

Depois:
```bash
pip install -e . 2>&1 | tail -3
# ou pip install -r requirements.txt
```

### 6.3 Validação

```bash
python -c "import pandas; print('pandas', pandas.__version__)"
# Esperado: 2.x

pytest --tb=short 2>&1 | tail -3
```

### 6.4 Commit
```
chore(deps): adiciona pandas como dependência

Necessário para shared/telemetry_store.py ler o CSV do dashboard.
```

---

## Passo 7 — Smoke test end-to-end manual

### 7.1 Objetivo
Validar manualmente que o fluxo do usuário final funciona ponta a ponta com tudo conectado.

### 7.2 Cenários

**Cenário A — Criar paciente novo via chat**
1. Subir o chatbot (entrypoint do projeto).
2. Mensagem: *"Quero cadastrar um paciente novo: Pedro Lima, 60 anos, masculino, com fibrilação atrial e hipertensão"*
3. Esperado:
   - Agent chama `criar_perfil_paciente(nome='Pedro Lima', idade=60, sexo='M', condicoes=['fibrilação atrial', 'hipertensão'], confirmacao=False)`.
   - Retorna preview e pede confirmação.
4. Mensagem: *"Sim, pode criar"*
5. Esperado:
   - Agent chama com `confirmacao=True`.
   - Retorna ID novo (provavelmente `BENEF-NEW-001`).
6. Verificar no JSON:
   ```bash
   python -c "from shared.patient_registry import list_patients; print([p['id'] for p in list_patients() if p['id'].startswith('BENEF-NEW')])"
   ```

**Cenário B — Telemetria ao vivo de GABRIEL**
1. Garantir que `data/cardiac_data.csv` tem linhas para "Gabriel" (do ESP32 rodando OU copie algumas linhas do `gabriel_data.csv` para o `cardiac_data.csv`).
2. Selecionar paciente GABRIEL na UI.
3. Mensagem: *"Como está meu ritmo cardíaco agora?"*
4. Esperado: agent chama `analisar_ritmo_cardiaco(paciente_id='GABRIEL')`, retorna classificação + observação mencionando idade 34, sexo M, hipertensão.

**Cenário C — Backwards compat com paciente legado**
1. Selecionar paciente BENEF-001.
2. Mensagem: *"Quais são minhas condições?"*
3. Esperado: agent acessa perfil normalmente, sem regressão.

**Cenário D — Defesa contra criação acidental**
1. Mensagem: *"Crie um paciente fictício para teste"*
2. Esperado: agent recusa OU chama com `confirmacao=False` e espera confirmação explícita. Nunca cria sem confirmação.

### 7.3 Validação
Os 4 cenários passam manualmente. Documentar o resultado de cada um.

### 7.4 Commit
Opcional. Se quiser registrar:
```
docs: documenta smoke tests manuais da merge

Cenários A-D passando: criar paciente, telemetria live, backwards compat,
defesa contra alucinação.
```

---

**Status:** ✅ Concluído (2026-05-28).

Smoke 5/5 cenários verdes:
- Cenário A (cadastro 2-step real): 3/3
- Cenário B (telemetria live GABRIEL): 2/2
- Cenário C (backwards compat BENEF-001): 2/2
- Cenário D (pedido vago): 1/1 spot-check
- "Sim isolado": 1/1 spot-check

Pytest: 67/67 verdes.

Detalhes em `SMOKE_PASSO_7_RESULTADOS.md`.

Durante a execução do smoke, foram descobertos 3 bugs arquiteturais
pré-existentes do BluaDiagnostics Sprint 2 (não introduzidos pela
merge). Todos corrigidos via feature branch
`feature/fix-bugs-passo-7`, com 4 fases de execução documentadas
em `PLANO_FASES_2_A_5.md`. Ver merge commit `c9c6cad` no `git log`
para detalhes completos.

2 bugs pré-existentes documentados como issues separadas, fora do
escopo desta merge:
- BENEF-CV-002 alergias com formato inconsistente.
- safety.py heurística "você tem" sem contexto.

Ver `ISSUES.md` na raiz do repo.

---

## Passo 8 (OPCIONAL) — Unificar Dash apps

Refatoração: substituir `app/dash_app.py` (chatbot) e o `app.py` do dashboard por `blua_merge_files/app/unified_app.py`, mover as páginas do dashboard para `pages/` com `dash.register_page`.

Esse passo é grande e pode ficar para sprint seguinte. Detalhes na seção 4-5 do `MERGE_GUIDE.md`.

**Recomendação:** ficar com os dois servidores rodando em separado (chatbot na 8050, dashboard na 8051) até o final do sprint atual. Unificar só depois que cenários A-D estiverem 100% estáveis.

---

## Pós-merge — Próximos passos sugeridos

1. **Atualizar README** descrevendo a nova arquitetura unificada (chatbot ⇄ shared/ ⇄ dashboard).
2. **Adicionar `tests/test_integration_merge.py`** cobrindo: criar_perfil + live ritmo + cache invalidation.
3. **Considerar as ideias da seção 9 do `MERGE_GUIDE.md`** ("perfect harmony"):
   - Push dashboard → chatbot (notificação quando 3s irregular).
   - Pre-safety enriched com telemetria (bypass do LLM para red flags ao vivo).
   - RAG patient-aware (boost de chunks que casam com `condicoes_ativas`).

---

## Riscos conhecidos e mitigações

| Risco | Mitigação atual | TODO |
|-------|----------------|------|
| Race em `perfis_clinicos.json` com múltiplos workers gunicorn | RLock cobre 1 worker, atomic rename garante consistência | Para multi-worker, adicionar `fcntl.flock` |
| Cache LRU stale após `criar_perfil` | `invalidate_caches()` chamado em `create_patient()` | — |
| ESP32 escreve `"live"` mas chatbot espera `"GABRIEL"` | `_ALIAS` em `shared/telemetry_store.py` mapeia | — |
| LLM aluciona criação de paciente | Fluxo 2-step com `confirmacao=True` | Considerar usar HITL formal do LangGraph para acabar de blindar |
| Renomeação de MARIA quebra teste hardcoded | Passo 2.4 (grep + ajuste manual) | — |
| Smoke test do Passo 5 falha porque LLM não chama a tool nova | Iterar no system prompt; verificar se a tool foi bindada de fato no `bind_tools()` | — |

---

## Glossário

- **PPG**: Photoplethysmogram, sinal óptico de fluxo sanguíneo medido pelo MAX30100.
- **IBI**: Inter-Beat Interval, intervalo entre batimentos em ms.
- **BPM**: Batimentos Por Minuto.
- **HITL**: Human-In-The-Loop, padrão do LangGraph para pausar o grafo aguardando confirmação humana.
- **HAS**: Hipertensão Arterial Sistêmica.
- **FA**: Fibrilação Atrial.

---

**Fim do plano.** Boa merge.
