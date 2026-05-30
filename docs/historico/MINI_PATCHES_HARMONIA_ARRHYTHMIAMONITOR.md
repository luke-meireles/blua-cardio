# MINI_PATCHES_HARMONIA_ARRHYTHMIAMONITOR.md

**Pré-requisito:** Passos 0-7 do `PLANO_MERGE.md` concluídos. Branch atual: `main` (working tree clean após `feature/fix-bugs-passo-7` mergeada).

**Versão:** 1.0
**Data:** 2026-05-28
**Tempo total estimado:** 30-50min (todos os 4 patches juntos).
**Risco geral:** baixo a médio (alguns testes podem precisar ajuste por causa de R1).

---

## Objetivo

Preparar terreno pra futura integração com o repositório `ArrhythmiaMonitor` (que conterá o sistema completo após o merge atual). Cada patch é **opcional e independente** — você pode aplicar 1, 2, 3 ou todos os 4. Não há dependência entre eles.

**Importante:** estes patches NÃO juntam os repos. Apenas **alinham detalhes** no projeto atual pra que a junção futura seja mais suave. Nenhum patch quebra funcionalidade existente.

---

## Sumário dos 4 patches

| # | Patch | Tempo | Risco | Toca testes? |
|---|-------|-------|-------|--------------|
| R1 | Alinhar perfil de Gabriel com `ArrhythmiaMonitor/dashboard/pages/gabriel.py` | 10-15min | Médio | Sim (provável) |
| R2 | Tornar `consultar_telemetria_dashboard` agnóstico de fonte (env var) | 10-15min | Baixo | Pouco provável |
| R3 | Persistir agendamentos em JSON local (formato compatível com `consultas_gabriel.json` futuro) | 15-20min | Baixo | Possível |
| R4 | Documentar gap visual e referência ao tema do `ArrhythmiaMonitor` | 5min | Nenhum | Não |

**Recomendação de ordem:** R4 → R2 → R3 → R1 (do mais barato/seguro pro mais arriscado).

---

## R1 — Alinhar perfil de Gabriel com `ArrhythmiaMonitor`

### R1.1 Objetivo

Atualizar o paciente `GABRIEL` no `data/mocks/perfis_clinicos.json` pra refletir os dados que aparecem em `ArrhythmiaMonitor/dashboard/pages/gabriel.py`. Quando o chatbot for plugado naquele repositório, o paciente "Gabriel" será a mesma pessoa em ambos os lados — sem inconsistência entre prontuário do chatbot e ficha do dashboard.

### R1.2 Estado atual vs alvo

| Campo | Estado atual (pós-Passo 2) | Alvo (ArrhythmiaMonitor) |
|-------|----------------------------|--------------------------|
| `id` | `GABRIEL` | `GABRIEL` (mantém) |
| `nome` | `Gabriel` (ou similar curto) | `Gabriel Oliveira` |
| `idade` | 34 | 38 |
| `sexo` | `masculino` | `masculino` (mantém) |
| `condicoes_ativas` | 1 condição (HAS) | 3 condições (FA paroxística, HAS, taquicardia supraventricular) |
| `score_risco_cardiovascular` | baixo (ou não definido) | moderado |
| `cha2ds2_va` (campo novo) | ausente | 2 |

### R1.3 Arquivo

`data/mocks/perfis_clinicos.json`

### R1.4 Edit proposto

Localizar a entrada com `"id": "GABRIEL"` (que veio do rename MARIA→GABRIEL do Passo 2). Substituir por:

```json
{
  "id": "GABRIEL",
  "nome": "Gabriel Oliveira",
  "idade": 38,
  "sexo": "masculino",
  "plano": "Care Plus Premium",
  "score_risco_cardiovascular": "moderado",
  "cha2ds2_va": 2,
  "condicoes_ativas": [
    {
      "cid": "I48.0",
      "nome": "Fibrilação atrial paroxística",
      "desde": "2021-04-15",
      "status": "em controle"
    },
    {
      "cid": "I10",
      "nome": "Hipertensão arterial sistêmica",
      "desde": "2018-06-15",
      "status": "controlada"
    },
    {
      "cid": "I47.1",
      "nome": "Taquicardia supraventricular recorrente",
      "desde": "2023-06-15",
      "status": "histórico — episódios paroxísticos"
    }
  ],
  "medicacoes_ativas": [
    {
      "nome": "Apixabana",
      "dose": "5mg",
      "frequencia": "2x ao dia",
      "indicacao": "Anticoagulação para FA paroxística",
      "inicio": "2021-04-20"
    },
    {
      "nome": "Metoprolol succinato",
      "dose": "50mg",
      "frequencia": "1x ao dia",
      "indicacao": "Controle de FC em FA",
      "inicio": "2021-04-20"
    },
    {
      "nome": "Losartana Potássica",
      "dose": "50mg",
      "frequencia": "1x ao dia",
      "indicacao": "Hipertensão arterial",
      "inicio": "2018-06-15"
    }
  ],
  "alergias": [],
  "sinais_vitais_ultimo_registro": {
    "data": "2026-04-22",
    "pressao_arterial": "128x82 mmHg",
    "frequencia_cardiaca": "74 bpm",
    "saturacao_oxigenio": "98%",
    "peso_kg": 78,
    "altura_cm": 178,
    "imc": 24.6
  },
  "consultas": {
    "ultima": {
      "data": "2026-04-22",
      "especialidade": "Cardiologia",
      "medico": "Dr. Gregory House — CRM 12345/SP",
      "observacoes": "FA paroxística em controle. Sem novos episódios documentados nos últimos 60 dias. Anticoagulação mantida.",
      "plataforma": "Teleconsulta Blua"
    },
    "proxima": {
      "data": "2026-09-22",
      "especialidade": "Cardiologia",
      "status": "agendada"
    }
  },
  "exames_recentes": [
    {
      "data": "2026-04-10",
      "tipo": "Holter 24h",
      "resultado": "Ritmo sinusal predominante. Episódios isolados de FA paroxística autolimitados.",
      "laudo": "FA paroxística — manter anticoagulação"
    },
    {
      "data": "2026-03-15",
      "tipo": "Ecocardiograma transtorácico",
      "resultado": "Fração de ejeção 60%. Átrio esquerdo levemente aumentado.",
      "laudo": "Compatível com FA"
    }
  ]
}
```

### R1.5 Validação

**R1.5.1 — JSON parseia:**
```bash
python -c "
import json
with open('data/mocks/perfis_clinicos.json') as f:
    data = json.load(f)
gabriel = [p for p in data['beneficiarios'] if p['id'] == 'GABRIEL'][0]
print('Nome:', gabriel['nome'])
print('Idade:', gabriel['idade'])
print('CHA2DS2-VA:', gabriel.get('cha2ds2_va'))
print('Condições:', [c['nome'] for c in gabriel['condicoes_ativas']])
assert gabriel['nome'] == 'Gabriel Oliveira'
assert gabriel['idade'] == 38
assert gabriel['cha2ds2_va'] == 2
print('OK')
"
```

**R1.5.2 — Bridge layer continua funcionando:**
```bash
python -c "
from shared.patient_registry import get_patient
p = get_patient('GABRIEL')
print('Nome:', p['nome'])
print('Condições:', [c['nome'] for c in p['condicoes_ativas']])
"
```

**R1.5.3 — Pytest:** 
```bash
pytest --tb=short 2>&1 | tail -10
```

### R1.6 Critério de parada

- **Pytest falha:** muito provável. Os 49 testes do baseline podem ter asserções tipo `assert paciente['idade'] == 34` ou `assert len(condicoes_ativas) == 1`. **Comportamento esperado** — significa que os testes ancoravam no estado antigo. Atualizar os testes pra refletir o novo estado é parte do patch.
  - **Antes de atualizar testes**, mostrar quais asserções falharam e confirmar com usuário. Pode haver teste validando comportamento clínico real (não dado mock), e aí o teste tem razão.

- **JSON corrompido:** algum erro de sintaxe na substituição. Reverter via `git checkout HEAD -- data/mocks/perfis_clinicos.json` e tentar de novo.

### R1.7 Riscos específicos

| Risco | Mitigação |
|-------|-----------|
| Smoke do Cenário B usa GABRIEL com hipertensão na observação | OK — hipertensão continua presente. Mas o disclaimer PPG pode citar "hipertensão" + "FA" agora, mudando o texto. Validar smoke após o patch. |
| Testes legados validam `idade == 34` | Atualizar pra `idade == 38`. Comportamento esperado. |
| Smoke do Cenário C usa BENEF-001, não GABRIEL | Não afetado por este patch. |

### R1.8 Commit
```
data(perfil): alinha GABRIEL com prontuário do ArrhythmiaMonitor

Atualiza Gabriel Oliveira pra refletir dados que aparecem em
ArrhythmiaMonitor/dashboard/pages/gabriel.py (futura integração):

- Nome: "Gabriel Oliveira" (era "Gabriel")
- Idade: 38 (era 34)
- Condições: FA paroxística (CID I48.0), HAS, taqui supraventricular
  (era apenas HAS)
- Medicações: Apixabana, Metoprolol, Losartana
- CHA2DS2-VA: 2 (campo novo)
- Médico: Dr. Gregory House (consistente com mockado do dashboard)

Quando integrar com ArrhythmiaMonitor (próxima fase do projeto),
Gabriel será a mesma pessoa nos dois lados — sem inconsistência
entre prontuário do chatbot e ficha do dashboard.

Testes ajustados onde validavam estado anterior do GABRIEL.
```

---

## R2 — Telemetria agnóstica de fonte

### R2.1 Objetivo

Fazer `consultar_telemetria_dashboard` ler o path do CSV via variável de ambiente, com default no caminho atual. Assim, na fase futura, mudar pra Azure Blob requer apenas trocar a env var (ou substituir o reader internamente) — zero refatoração de chamadores.

### R2.2 Estratégia

Hoje `shared/telemetry_store.py` tem path hardcoded:
```python
TELEMETRY_CSV = PROJECT_ROOT / "data" / "cardiac_data.csv"
```

Vamos trocar por:
```python
TELEMETRY_CSV = Path(os.environ.get("BLUA_TELEMETRY_CSV", str(PROJECT_ROOT / "data" / "cardiac_data.csv")))
```

Default continua sendo o path atual. Quem quiser sobrescrever (ex.: testes, integração futura), define `BLUA_TELEMETRY_CSV=...` antes de rodar.

### R2.3 Edit em `shared/paths.py`

Localizar a linha onde `TELEMETRY_CSV` é definido:

```diff
+import os
 from pathlib import Path

 PROJECT_ROOT = Path(__file__).resolve().parents[1]
 DATA_DIR = PROJECT_ROOT / "data"
 PROFILES_JSON = DATA_DIR / "mocks" / "perfis_clinicos.json"
-TELEMETRY_CSV = DATA_DIR / "cardiac_data.csv"
+TELEMETRY_CSV = Path(
+    os.environ.get(
+        "BLUA_TELEMETRY_CSV",
+        str(DATA_DIR / "cardiac_data.csv"),
+    )
+)
 GABRIEL_CSV = DATA_DIR / "gabriel_data.csv"
```

Aplicar análogo a `GABRIEL_CSV` se quiser permitir override também (opcional):

```diff
-GABRIEL_CSV = DATA_DIR / "gabriel_data.csv"
+GABRIEL_CSV = Path(
+    os.environ.get(
+        "BLUA_GABRIEL_CSV",
+        str(DATA_DIR / "gabriel_data.csv"),
+    )
+)
```

### R2.4 Documentar no README

Adicionar seção `## Configuração via variáveis de ambiente` ao `README.md`:

```markdown
## Configuração via variáveis de ambiente

| Variável | Default | Uso |
|----------|---------|-----|
| `BLUA_TELEMETRY_CSV` | `data/cardiac_data.csv` | Path do CSV de telemetria ao vivo do dashboard. Defina para apontar pra outro arquivo (ex.: ambiente de teste, integração futura com Azure Blob mount). |
| `BLUA_GABRIEL_CSV` | `data/gabriel_data.csv` | Path do CSV de referência do paciente Gabriel (200 batimentos). |
| `BLUA_ROOT` (já existente) | `pasta do projeto` | Raiz do projeto pra resolução de paths. |
```

### R2.5 Validação

**R2.5.1 — Default funciona (sem env var):**
```bash
python -c "
from shared.paths import TELEMETRY_CSV
print('Default:', TELEMETRY_CSV)
print('Existe?', TELEMETRY_CSV.exists())
"
```

**R2.5.2 — Override via env var:**
```bash
BLUA_TELEMETRY_CSV=/tmp/teste.csv python -c "
from shared.paths import TELEMETRY_CSV
print('Override:', TELEMETRY_CSV)
assert str(TELEMETRY_CSV) == '/tmp/teste.csv'
print('OK')
"
```

**R2.5.3 — Pytest:**
```bash
pytest --tb=short 2>&1 | tail -5
```

### R2.6 Critério de parada
- Testes que importam `TELEMETRY_CSV` esperando tipo específico (não-Path): muito improvável, mas se aparecer, ajustar.
- Algum lugar que faz `PROJECT_ROOT / "data" / "cardiac_data.csv"` direto (sem usar `TELEMETRY_CSV`): grepar e refatorar pra usar a constante.

```bash
grep -rn "cardiac_data.csv\|gabriel_data.csv" --include="*.py" . | grep -v "shared/paths.py"
```

### R2.7 Commit
```
refactor(paths): permite override de paths de telemetria via env var

- TELEMETRY_CSV agora respeita BLUA_TELEMETRY_CSV (default mantido)
- GABRIEL_CSV agora respeita BLUA_GABRIEL_CSV (default mantido)
- README atualizado com tabela de variáveis de ambiente

Prepara terreno pra integração futura com Azure Blob: basta apontar
a env var pra um mount ou substituir o reader internamente, sem
refatorar chamadores.

Zero impacto no comportamento default. Pytest verde.
```

---

## R3 — Persistir agendamentos em JSON

### R3.1 Objetivo

A especificação do `ArrhythmiaMonitor` README prevê que o agente escreva consultas agendadas em `consultas_gabriel.json` no Azure Blob, formato:
```json
{
  "data": "DD/MM/AAAA",
  "tipo": "Consulta agendada via agente",
  "medico": "Dr. Gregory House",
  "resumo": "Motivo informado pelo usuário",
  "status": "agendada"
}
```

Hoje, `agendar_teleconsulta` retorna confirmação ao usuário mas não persiste em arquivo. Vamos adicionar **persistência local** seguindo o formato esperado. Na integração futura, basta trocar `open()` por `blob.upload_blob()`.

### R3.2 Estrutura proposta

Criar pasta `data/consultas/` (gitignored ou versionada com `.gitkeep` — decisão tua). Cada paciente tem um arquivo: `data/consultas/<paciente_id>.json` (ex.: `consultas_GABRIEL.json`, `consultas_BENEF-001.json`).

Formato do arquivo: array de objetos:
```json
[
  {
    "data": "15/06/2026",
    "tipo": "Consulta agendada via agente",
    "medico": "Dr. Gregory House",
    "resumo": "Avaliação de fadiga e palpitações ocasionais",
    "status": "agendada",
    "criado_em": "2026-05-28T14:30:00",
    "criado_por": "agendar_teleconsulta_v1"
  }
]
```

### R3.3 Edit em `src/tools/teleconsulta.py` (ou equivalente)

Localizar a tool atual:
```bash
grep -rn "def agendar_teleconsulta" src/ --include="*.py"
```

Adicionar lógica de persistência ao final da função (antes do `return`):

```python
import json
from datetime import datetime
from pathlib import Path

from shared.paths import DATA_DIR


def _registrar_consulta_localmente(
    paciente_id: str,
    data: str,
    motivo: str,
    medico: str = "Dr. Gregory House",
) -> Path:
    """
    Registra a consulta agendada em data/consultas/<paciente_id>.json.

    Formato compatível com a especificação futura de consultas_gabriel.json
    do repositório ArrhythmiaMonitor (Azure Blob).
    """
    consultas_dir = DATA_DIR / "consultas"
    consultas_dir.mkdir(parents=True, exist_ok=True)

    arquivo = consultas_dir / f"consultas_{paciente_id}.json"

    # Carrega existentes (ou lista vazia)
    if arquivo.exists():
        with arquivo.open(encoding="utf-8") as f:
            consultas = json.load(f)
    else:
        consultas = []

    # Anexa nova
    consultas.append({
        "data": data,
        "tipo": "Consulta agendada via agente",
        "medico": medico,
        "resumo": motivo,
        "status": "agendada",
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "criado_por": "agendar_teleconsulta_v1",
    })

    # Salva (atomic write)
    tmp = arquivo.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(consultas, f, ensure_ascii=False, indent=2)
    tmp.replace(arquivo)

    return arquivo
```

Integrar no `agendar_teleconsulta` existente:

```diff
 def agendar_teleconsulta(paciente_id: str, data: str, motivo: str) -> dict:
     # ... validações existentes ...

+    # Persistir localmente em formato compatível com ArrhythmiaMonitor
+    try:
+        arquivo_registro = _registrar_consulta_localmente(
+            paciente_id=paciente_id,
+            data=data,
+            motivo=motivo,
+        )
+        log.info(f"Consulta registrada em {arquivo_registro}")
+    except Exception as exc:
+        # Falha de persistência NÃO bloqueia a resposta ao usuário
+        log.warning(f"Falha ao persistir consulta: {exc}")
+        arquivo_registro = None
+
     return {
         "sucesso": True,
         "data": data,
         "motivo": motivo,
         "medico": "Dr. Gregory House",
+        "registro_local": str(arquivo_registro) if arquivo_registro else None,
         # ... outros campos existentes ...
     }
```

### R3.4 Adicionar `.gitignore` (opcional)

Se quiser que os agendamentos não sejam versionados (recomendado — dado dinâmico, não código):

```diff
 # .gitignore
+
+# Agendamentos persistidos pelo agendar_teleconsulta
+data/consultas/
```

Senão, criar `data/consultas/.gitkeep` pra versionar a pasta vazia.

### R3.5 Validação

**R3.5.1 — Agendar consulta cria arquivo:**
```bash
python -c "
from src.tools.teleconsulta import agendar_teleconsulta  # ajustar path
import json

resultado = agendar_teleconsulta(
    paciente_id='GABRIEL',
    data='15/06/2026',
    motivo='Avaliação de palpitações',
)
print('Resultado:', resultado.get('sucesso'))
print('Registro:', resultado.get('registro_local'))

# Conferir arquivo
from pathlib import Path
arquivo = Path('data/consultas/consultas_GABRIEL.json')
assert arquivo.exists(), 'Arquivo não foi criado'

with arquivo.open() as f:
    consultas = json.load(f)
print('Consultas registradas:', len(consultas))
print('Última:', consultas[-1])
"
```

**R3.5.2 — Append funciona (segunda consulta vira segunda entrada):**
```bash
python -c "
from src.tools.teleconsulta import agendar_teleconsulta
agendar_teleconsulta('GABRIEL', '20/07/2026', 'Retorno')

import json
from pathlib import Path
with open('data/consultas/consultas_GABRIEL.json') as f:
    c = json.load(f)
assert len(c) == 2, f'Esperado 2 consultas, vieram {len(c)}'
print('Append OK, total:', len(c))
"
```

**R3.5.3 — Limpar antes de commitar:**
```bash
# Remover consultas criadas durante teste
rm -rf data/consultas/
```

**R3.5.4 — Pytest:**
```bash
pytest --tb=short 2>&1 | tail -5
```

### R3.6 Critério de parada
- Testes existentes de `agendar_teleconsulta` quebram porque retorno tem campo novo (`registro_local`): atualizar testes pra aceitar o novo campo. Aditivo, não deve ser difícil.
- Diretório `data/consultas/` não consegue ser criado (permissões): improvável, mas se acontecer, garantir que `DATA_DIR` está acessível.

### R3.7 Commit
```
feat(teleconsulta): persiste agendamentos em JSON local

- Nova função _registrar_consulta_localmente em src/tools/teleconsulta.py
- Cada paciente tem data/consultas/consultas_<paciente_id>.json
- Formato compatível com especificação futura de consultas_gabriel.json
  no Azure Blob (repositório ArrhythmiaMonitor)
- Falha de persistência não bloqueia resposta ao usuário (best-effort)
- .gitignore atualizado pra ignorar data/consultas/ (dado dinâmico)

Quando integrar com Azure Blob na próxima fase, basta substituir
open() por blob.upload_blob() — formato JSON já compatível.

Zero alteração no comportamento de resposta ao usuário (apenas
campo novo opcional 'registro_local' no retorno da tool).
```

---

## R4 — Documentar gap visual e referência ao tema do `ArrhythmiaMonitor`

### R4.1 Objetivo

Criar arquivo `docs/INTEGRACAO_ARRHYTHMIAMONITOR.md` descrevendo as **diferenças visuais e estruturais** entre o estado atual do projeto e o `ArrhythmiaMonitor`, pra servir de mapa quando você for fazer a integração futura.

### R4.2 Arquivo novo

Criar `docs/INTEGRACAO_ARRHYTHMIAMONITOR.md`:

```markdown
# Notas para Integração Futura com `ArrhythmiaMonitor`

Documento de referência para a próxima fase do projeto, quando o
chatbot do `blua-cardio` (estado atual) for integrado ao repositório
`ArrhythmiaMonitor` (https://github.com/GabrielAugustoT800/ArrhythmiaMonitor).

**Status:** este documento descreve o estado em 2026-05-28. Atualizar
se o `ArrhythmiaMonitor` mudar significativamente antes da integração.

---

## 1. Visão geral do `ArrhythmiaMonitor`

Sistema cardíaco em 3 camadas:
- **Hardware:** ESP32 + MAX30100 capturando PPG.
- **API ML:** FastAPI com Random Forest treinado, deployable no Azure.
- **Dashboard:** Dash multi-pages (already `use_pages=True`).
- **Pasta `agent/` vazia:** placeholder para o chatbot deste projeto.

### Arquivos relevantes para a integração

| Arquivo no `ArrhythmiaMonitor` | Relevância |
|--------------------------------|------------|
| `dashboard/app.py` | Entrypoint Dash multi-pages. Substitui nosso `unified_app.py`. |
| `dashboard/pages/{home,monitor,analysis,gabriel}.py` | Páginas já com `dash.register_page`. |
| `dashboard/utils/storage.py` | Função `load_blob(tail=50)` que o chatbot deve usar. |
| `dashboard/utils/theme.py` | Tokens HUD: PRIMARY_BLUE, ACCENT_CYAN, etc. |
| `dashboard/utils/analysis.py` | `BeatRecord`, `classify_status`, thresholds. |
| `api.py` (raiz) | Endpoint `POST /prever` que substitui regra heurística do `analisar_ritmo_cardiaco`. |
| `predicao.py` (raiz) | Pipeline ML com `prever_salvar()`. |
| `modelo_predicao.pkl` (raiz) | Random Forest treinado. |
| `agent/` (vazio) | Onde o chatbot vai entrar. |

---

## 2. Pontos de divergência entre estado atual e `ArrhythmiaMonitor`

### 2.1 Estrutura de pastas

| Aspecto | blua-cardio atual | ArrhythmiaMonitor |
|---------|-------------------|-------------------|
| Entrypoint dashboard | `app/dash_app.py` | `dashboard/app.py` |
| Páginas | `dashboard_legacy/pages/*.py` | `dashboard/pages/*.py` (já registradas) |
| Storage | `shared/telemetry_store.py` (CSV local) | `dashboard/utils/storage.py` (CSV + Azure Blob) |
| Tema visual | Indefinido / herdado | `utils/theme.py` com HUD próprio |
| ML | Regra heurística em `src/tools/ritmo.py` | API FastAPI + Random Forest |

### 2.2 Dados persistentes

| Dado | blua-cardio atual | ArrhythmiaMonitor |
|------|-------------------|-------------------|
| Telemetria ao vivo | `data/cardiac_data.csv` | Azure Blob `dataset/dataset_ppg.csv` |
| Pacientes (perfis clínicos) | `data/mocks/perfis_clinicos.json` (registry interno) | Não tem ainda — fica como responsabilidade do chatbot |
| Agendamentos | (após R3 deste patch) `data/consultas/consultas_<id>.json` | `consultas_gabriel.json` no Blob |
| Histórico de eventos | Não persiste | Blob (Azure) |

### 2.3 Stack técnica

| Camada | blua-cardio atual | ArrhythmiaMonitor |
|--------|-------------------|-------------------|
| LLM | Qwen via DashScope/Ollama | Qwen (especificado no README) |
| Memória de chat | LangGraph MemorySaver in-memory | `dcc.Store(storage_type="session")` (especificado) |
| RAG | ChromaDB local | (não especificado — provavelmente reaproveita ChromaDB do chatbot) |

---

## 3. Tarefas previstas na integração

Quando chegar a hora de fundir os projetos:

### 3.1 Mover chatbot para `agent/`

Conforme placeholder vazio no `ArrhythmiaMonitor`. Estrutura proposta:
```
ArrhythmiaMonitor/
├── agent/
│   ├── src/             # de src/ do blua-cardio
│   ├── prompts/         # de prompts/ do blua-cardio
│   ├── knowledge_base/  # de knowledge_base/ do blua-cardio
│   ├── chroma_db/       # de chroma_db/ do blua-cardio
│   └── tests/           # de tests/ do blua-cardio
├── dashboard/           # já existe
├── api.py
└── ...
```

### 3.2 Substituir tools por adaptadores Azure

| Tool atual | Adaptação para Azure |
|------------|----------------------|
| `consultar_sinais_vitais_wearable` (mock JSON) | Chamar `dashboard/utils/storage.py:load_blob(tail=50)` |
| `consultar_telemetria_dashboard` (CSV local) | Idem — `load_blob(tail=N)` |
| `analisar_ritmo_cardiaco` (regra heurística) | POST `http://api:8000/prever` com dados PPG |
| `agendar_teleconsulta` (R3 grava local) | Upload do JSON pro Blob `dataset/consultas_<id>.json` |

### 3.3 Adicionar página `/chat` no Dash multi-pages

O chatbot precisa virar uma página (`agent/pages/chat.py`) registrada via `dash.register_page(__name__, path='/chat')`. O detalhamento desta conversão está em `PASSO_8_UNIFICACAO_DASH.md` (mesmo trabalho, contexto diferente).

### 3.4 Reaproveitar tema HUD do `ArrhythmiaMonitor`

O `dashboard/utils/theme.py` define paleta, tipografia e componentes (`hud_panel`, `telemetry_tile`, `status_chip`). O chatbot atual deve adotar esse tema ao virar página — não criar tema concorrente.

---

## 4. Decisões pendentes

Quando chegar à fase de integração, decidir:

1. **Repositório final:** `ArrhythmiaMonitor` absorve `blua-cardio` (recomendado pela estrutura placeholder em `agent/`) ou dois repos separados conversando via API REST?
2. **Memória de chat:** manter LangGraph MemorySaver (server-side) ou migrar pra `dcc.Store(storage_type="session")` (client-side, conforme especificação)?
3. **Persistência de perfis:** o registry interno (`perfis_clinicos.json`) continua no chatbot ou migra pro Blob também?
4. **CHA₂DS₂-VA do Gabriel:** já é campo no `perfis_clinicos.json` (após R1) ou só display no `pages/gabriel.py`?

Decisões a tomar no início da próxima fase, não agora.

---

## 5. Atalhos já preparados

| Atalho | Patch que aplicou |
|--------|-------------------|
| Perfil de Gabriel alinhado com `pages/gabriel.py` | R1 |
| Telemetria com path configurável via env var | R2 |
| Agendamentos persistidos em formato compatível | R3 |
| Este documento | R4 |

---

*Documento interno — atualizar antes de iniciar a integração futura.*
```

### R4.3 Validação

Apenas confirma que o arquivo foi criado e tem conteúdo legível:
```bash
ls -la docs/INTEGRACAO_ARRHYTHMIAMONITOR.md
head -30 docs/INTEGRACAO_ARRHYTHMIAMONITOR.md
```

### R4.4 Commit
```
docs: adiciona notas de integração futura com ArrhythmiaMonitor

Cria docs/INTEGRACAO_ARRHYTHMIAMONITOR.md com:
- Visão geral do repositório ArrhythmiaMonitor
- Mapa de divergências entre estado atual e alvo futuro
- Tarefas previstas na integração
- Decisões pendentes para próxima fase
- Lista de atalhos já preparados pelos patches R1-R3

Serve como documento de referência quando chegar a hora de
integrar o chatbot (atual blua-cardio) com o sistema completo
do ArrhythmiaMonitor (https://github.com/GabrielAugustoT800/ArrhythmiaMonitor).
```

---

## Validação final dos 4 patches juntos

Após aplicar todos:

```bash
# 1. Pytest verde
pytest --tb=short 2>&1 | tail -5

# 2. Smoke test rápido do Cenário B (telemetria GABRIEL)
# Manual no chat: "Como está meu ritmo cardíaco agora?"
# Esperado: classificação contextualizada com NOVA idade (38) e NOVAS condições (FA + HAS)

# 3. Conferir que documentos novos existem
ls -la docs/INTEGRACAO_ARRHYTHMIAMONITOR.md
ls -la README.md  # confirmar seção env vars

# 4. Conferir que estrutura de consultas funcionou
python -c "
from pathlib import Path
print('data/consultas/ existe?', (Path('data') / 'consultas').exists())
"

# 5. Conferir registry
python -c "
from shared.patient_registry import get_patient
g = get_patient('GABRIEL')
print(f\"Nome: {g['nome']}, Idade: {g['idade']}, CHA2DS2-VA: {g.get('cha2ds2_va')}\")
"
```

Esperado:
- Pytest verde.
- Smoke B passa com observação atualizada.
- Documentos presentes.
- Registry com Gabriel Oliveira / 38a / CHA2DS2-VA=2.

---

## Resumo executivo

| Patch | Esforço | Valor pra futuro |
|-------|---------|------------------|
| R1 (perfil Gabriel) | 10-15min + ajuste de testes | Alto — elimina inconsistência crítica |
| R2 (env var) | 10-15min | Médio — facilita integração Azure |
| R3 (persistir consultas) | 15-20min | Médio — infra pronta pro Blob |
| R4 (documentação) | 5min | Alto — bússola pra próxima fase |

**Ordem recomendada:** R4 → R2 → R3 → R1.

**Razão da ordem:** R4 é zero risco e o documento ajuda você a decidir os outros. R2 é pequeno e seguro. R3 é aditivo. R1 é o mais arriscado (mexe em dado central + testes), então por último com cabeça calibrada.

---

## Notas

- **Todos os patches são opcionais.** Pode aplicar 0, 1, 2, 3 ou 4. Nenhum bloqueia o Passo 8.
- **Recomendo aplicar R4 sempre.** Custo 5min, ajuda muito você daqui a alguns dias/semanas.
- **R1 tem risco de quebrar testes.** Se você não quer mexer em testes agora, deixa R1 pra fazer junto com a integração futura.
- **R2 e R3 são puro upside.** Não vejo razão pra não aplicar, exceto cansaço.
- **Nenhum destes patches juntar nada com o `ArrhythmiaMonitor`.** Apenas alinha detalhes pra fácil integração futura.
