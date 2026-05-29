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
