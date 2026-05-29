# Notas para Integração Futura do `ArrhythmiaMonitor` (no blua-cardio)

Documento de referência para a próxima fase do projeto, quando o
**conteúdo do `ArrhythmiaMonitor` (hardware ESP32, API ML, dashboard
atualizado, Azure Blob) for trazido para dentro do `blua-cardio`**
(https://github.com/GabrielAugustoT800/ArrhythmiaMonitor).

**Direção da integração:** o trabalho continua acontecendo dentro do
repositório local `blua-cardio`. O conteúdo do `ArrhythmiaMonitor`
upstream é copiado/adaptado para cá — não há fusão de repositórios.
O push final do projeto consolidado para um remoto (potencialmente
como branch do `ArrhythmiaMonitor`) é etapa separada feita pelo
usuário sozinho, fora do escopo de assistência.

**Status:** este documento descreve o estado em 2026-05-28. Atualizar
se o `ArrhythmiaMonitor` mudar significativamente antes da integração.

---

## 1. Visão geral do `ArrhythmiaMonitor`

Sistema cardíaco em 3 camadas:
- **Hardware:** ESP32 + MAX30100 capturando PPG.
- **API ML:** FastAPI com Random Forest treinado, deployable no Azure.
- **Dashboard:** Dash multi-pages (already `use_pages=True`).
- **Pasta `agent/` vazia:** placeholder no `ArrhythmiaMonitor` upstream
  — sinaliza que a equipe deles previa um chatbot. Será descartada
  quando trouxermos o conteúdo deles pra cá (chatbot já vive em `src/`
  aqui no `blua-cardio`).

### Arquivos relevantes para a integração

| Arquivo no `ArrhythmiaMonitor` | Relevância |
|--------------------------------|------------|
| `dashboard/app.py` | Entrypoint Dash multi-pages do `ArrhythmiaMonitor`. Referência para evoluir `app/unified_app.py` daqui (mesclar topbar HUD, ajustes de navegação, etc.). |
| `dashboard/pages/{home,monitor,analysis,gabriel}.py` | Páginas já com `dash.register_page`. |
| `dashboard/utils/storage.py` | Função `load_blob(tail=50)` que o chatbot deve usar. |
| `dashboard/utils/theme.py` | Tokens HUD: PRIMARY_BLUE, ACCENT_CYAN, etc. |
| `dashboard/utils/analysis.py` | `BeatRecord`, `classify_status`, thresholds. |
| `api.py` (raiz) | Endpoint `POST /prever` que substitui regra heurística do `analisar_ritmo_cardiaco`. |
| `predicao.py` (raiz) | Pipeline ML com `prever_salvar()`. |
| `modelo_predicao.pkl` (raiz) | Random Forest treinado. |
| `agent/` (vazio) | Placeholder do upstream — não vai ser usado (chatbot já vive em `src/` daqui). |

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

Quando chegar a hora de trazer o conteúdo do `ArrhythmiaMonitor` para dentro do `blua-cardio`:

### 3.1 Trazer hardware, API ML e dashboard pra dentro do `blua-cardio`

O conteúdo relevante do `ArrhythmiaMonitor` é copiado/adaptado para
pastas novas dentro do `blua-cardio`. Estrutura final esperada:
```
blua-cardio/
├── src/                 # chatbot LangGraph (já existe — intocado)
├── prompts/             # já existe — intocado
├── knowledge_base/      # já existe — intocado
├── chroma_db/           # já existe — intocado
├── tests/               # já existe — intocado
├── pages/               # já existe (Passo 8) — recebe ajustes do dashboard upstream
├── app/unified_app.py   # já existe (Passo 8) — recebe ajustes de topbar/tema
├── shared/              # já existe — intocado
├── utils/               # já existe — recebe utilitários do dashboard upstream
├── data/                # já existe — recebe novos mocks/datasets se necessário
├── firmware/            # NOVO — vem de ArrhythmiaMonitor (esp32 firmware .ino)
├── api_ml/              # NOVO — vem de ArrhythmiaMonitor/{api.py, predicao.py, modelo_predicao.pkl}
└── ...
```

Nomes finais das pastas novas (`firmware/`, `api_ml/`, etc.) decididos
na hora da integração — esse esqueleto é orientativo, não normativo.
A pasta `agent/` do upstream é descartada (chatbot já está em `src/`).

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

**Já decidido (registrado aqui pra evitar revisitação):**
- **Repositório de trabalho:** `blua-cardio` (local). O conteúdo do
  `ArrhythmiaMonitor` é trazido pra cá. Push final do projeto
  consolidado para um remoto (possivelmente como branch do
  `ArrhythmiaMonitor`) é etapa separada feita pelo usuário sozinho,
  fora do escopo da assistência.

**Quando chegar à fase de integração, decidir:**

1. **Memória de chat:** manter LangGraph MemorySaver (server-side) ou migrar pra `dcc.Store(storage_type="session")` (client-side, conforme especificação)?
2. **Persistência de perfis:** o registry interno (`perfis_clinicos.json`) continua local ou migra pro Azure Blob também?
3. **CHA₂DS₂-VA do Gabriel:** já é campo no `perfis_clinicos.json` (após R1) ou só display no `pages/gabriel.py`?

Decisões a tomar no início da próxima fase, não agora.

---

## 5. Decisões adiadas para implementação pós-integração

Funcionalidades discutidas durante o Passo 8 (unificação Dash) que
foram intencionalmente adiadas. Razão geral: implementar antes pode
ser trabalho perdido, já que a arquitetura final (com Azure + ML +
decisão sobre paciente único vs múltiplos) ainda não está
consolidada. Estas decisões serão revisitadas quando o conteúdo do
`ArrhythmiaMonitor` for trazido para o `blua-cardio`.

### 5.1 Seletor global de paciente como contexto da sessão

**Ideia:** componente dropdown presente em todas as páginas que
seleciona "qual paciente é o contexto da sessão". Ao mudar:
- Conteúdo de `/gabriel` (que vira `/paciente`) atualiza pra refletir
  prontuário do paciente selecionado.
- Dados de `/monitor` filtram pelo paciente.
- Análise de `/analise` filtra pelo paciente.
- Contexto do chatbot em `/` passa a ser o paciente selecionado
  (substitui o seletor atual da página chat).

**Estado atual no `blua-cardio`:** sistema tem `/gabriel` hardcoded
como página dedicada ao Gabriel. `pages/gabriel.py` tem
`PACIENTE_INFO = {...}` literal. Não há mecanismo de seleção fora
do chat.

**Implicações arquiteturais:**
- `pages/gabriel.py` precisa virar paciente-agnóstico (provavelmente
  renomear pra `pages/paciente.py`).
- `dcc.Store(id="paciente-ativo")` no layout global do entrypoint.
- Callbacks de cada página passam a ouvir mudanças do Store.
- Telemetria precisa de campo `patient` consistente — hoje o
  `cardiac_data.csv` tem `patient="live"` para todos os registros.
  Decisão pendente: telemetria por paciente fica no Azure Blob
  (separado por blob name) ou no CSV local com campo `patient`
  preenchido corretamente?
- `/pacientes` evolui de "lista do registry" para "seletor visual
  de paciente" (cards clicáveis que ativam o paciente como
  contexto).

**Decisão arquitetural pendente para a próxima fase:**
- Sistema final tem 1 paciente por instância (cada usuário vê só
  seu próprio prontuário) ou múltiplos pacientes selecionáveis?
- Se 1 paciente: seletor global desnecessário, `/pacientes`
  provavelmente some, `/gabriel` permanece como página principal
  do paciente único.
- Se múltiplos: implementar seletor global conforme descrito.

**Custo estimado de implementação (se for o caminho):**
- Versão mínima (só `/gabriel` reagindo ao Store): 1-2h.
- Versão completa (todas as páginas reagindo): 4-6h, possivelmente
  com mudanças no schema dos CSVs.

**Discussão original:** sessão de 2026-05-28 durante sub-passo 8.6
da unificação Dash em `blua-cardio`.

---

## 6. Atalhos já preparados

| Atalho | Patch que aplicou |
|--------|-------------------|
| Perfil de Gabriel alinhado com `pages/gabriel.py` | R1 |
| Telemetria com path configurável via env var | R2 |
| Agendamentos persistidos em formato compatível | R3 |
| Este documento | R4 |

---

*Documento interno — atualizar antes de iniciar a integração futura.*
