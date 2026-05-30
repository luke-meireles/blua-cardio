# BluaDiagnostics — Care Plus

> Assistente cardiovascular digital · LangGraph multi-agente · RAG · LGPD-ready
> **Sprint 2** — Sistema completo evoluindo a PoC da Sprint 1

[![Sprint](https://img.shields.io/badge/Sprint-2-blue)](docs/relatorio_final.md)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## O que é

BluaDiagnostics é um sub-app do **Blua** (plataforma da operadora Care Plus) que automatiza dois fluxos clínicos cardiovasculares:

1. **Check-up cardiovascular conversacional** — coleta sinais vitais, analisa wearable, agenda teleconsulta
2. **Rascunho de prescrição pós-teleconsulta com revisão médica humana (HITL síncrono)**

Especialização cardiovascular **estrita** — pedidos fora do escopo são polidamente recusados e redirecionados.

---

## Arquitetura

**10 nós LangGraph** orquestrados por supervisor estatal:

```
Usuário → Pre-Safety → Supervisor
            ↓             ↓
   ┌────────┬─────────┬─────────┬──────────┬──────────┐
   ↓        ↓         ↓         ↓          ↓          ↓
Checkup  Triagem   Suporte  Prescrição  Escalada  ForaEscopo
           +Rerank    +RAG    +HITL     +SAMU
   └────────┴─────────┴─────────┴──────────┴──────────┘
                        ↓
                Safety dupla camada
                        ↓
            Saída (audit + truncagem)
                        ↓
                     Usuário
```

5 agentes especializados (checkup, triagem, suporte, prescrição, escalada humana) + pre-safety determinístico + safety dupla camada + roteador de fora-de-escopo. Total: **10 nós** mais `START`/`END`.

Ver `docs/relatorio_final.md` para diagrama Mermaid completo e justificativa de cada decisão.

---

## Modos de execução

O BluaDiagnostics é **bi-modal** — alterna entre DashScope cloud e Ollama on-prem via uma linha do `.env`:

| Modo | Quando | Custo | Privacidade |
|---|---|---|---|
| **DashScope** (cloud, default) | Demos rápidas, evals, ambiente de teste | ~$0.001/turno | Externa (residência APAC) |
| **Ollama** (on-prem) | Produção LGPD-ready, isolamento total | $0 | 100% local |

```bash
LLM_BACKEND=dashscope    # ou: ollama
```

A troca afeta apenas o `_obter_cliente()` no `qwen_client.py` — todos os agentes, RAG, safety e UI permanecem idênticos.

---

## Quickstart

```bash
# 1. Clonar e instalar
git clone <repo>
cd BluaDiagnostics-Sprint
pip install -r requirements.txt

# 2. Configurar
cp .env.example .env
# Editar .env: DASHSCOPE_API_KEY=sk-xxx
# (UTF-8 sem BOM — colab_setup.py remove BOM automaticamente se houver)

# 3. Popular ChromaDB (uma vez, ~132 chunks de 12 documentos)
bash scripts/index_kb.sh

# 4. Iniciar interface Dash (principal)
python app/dash_app.py
# Abre em http://localhost:8050

# Alternativa: Streamlit (fallback)
streamlit run app/streamlit_app.py

# 5. Rodar evals (gera sprint2_results.json + gráficos)
python -m evals.run_evals_sprint2

# 6. Rodar testes
pytest tests/ -v
# Esperado: 49 passed, 1 warning
```

---

## Sprint 2 — O que mudou

### Funcionalidades

| Área | Sprint 1 | Sprint 2 |
|---|---|---|
| **Interface** | CLI + Notebook | **Dash** + Streamlit fallback |
| **Agentes** | 4 | **5** (+ Prescrição) |
| **Nós LangGraph** | 7 | **10** (+ pre_safety, prescricao, escalada_humana) |
| **Supervisor** | Classificador estático | **Estatal** (força triagem se RED_FLAG persistir entre turnos) |
| **Pre-safety** | — | **3 camadas**: regex óbvio + lookbehind + score-based, com LLM-as-validator em padrões ambíguos |
| **Safety** | Heurística regex | **Dupla camada** (heurística + LLM auditor) |
| **RAG** | Similarity search | **MMR + Auto-RAG + Reranker + filtros por categoria + cache LRU** |
| **Memória** | Acumula indefinidamente | **Summarize-and-replace** após 6 turnos |
| **Confidence scoring** | — | **Numérico** baseado em RAG + intent + tools |
| **HITL** | — | **Síncrono** via `interrupt_after=["prescricao"]` no LangGraph |
| **Observabilidade** | Audit log local | **+ LangSmith** integrado (3 env vars) |
| **Tools** | 6 | **7** (+ `sugerir_rascunho_prescricao`) |
| **Evals** | 22 casos | **35 casos** (32 originais + 3 cobrindo perfis CV variados) |
| **Testes** | — | **4 arquivos pytest** (49 testes) |

### Apresentações atípicas

Knowledge base expandida com 12 documentos cardiovasculares, incluindo:

- `cardiologia_apresentacoes_atipicas.md` (SCA atípica em mulheres, diabéticos, idosos)
- `cardiologia_estratificacao_risco.md` (HEART, TIMI simplificados, FRCV)
- `cardiologia_gravidez_pre_eclampsia.md` (cardiomiopatia periparto)
- `cardiologia_jovens_atletas.md` (CMH, síncope, pré-excitação)
- `mapa_especialidades.md` (granularidade fina dentro do escopo CV)

Casos de eval cobrindo: dor torácica clássica em FRCV, SCA atípica em mulher diabética idosa, dissecção aórtica, TEP em jovem com anticoncepcional, síncope em FA, crise hipertensiva diferenciada, prescrição com CFM 2.314/22.

---

## Pre-Safety em 3 camadas

Filtro determinístico ANTES do supervisor LLM. Combinação que minimiza falsos positivos e negativos:

| Camada | Mecanismo | Latência | Cobre |
|---|---|---|---|
| **1a — Regex óbvio** | Padrões claros de jailbreak/OOS (`ignore X instruções`, `DAN`, `developer mode`, `diabetes pura`, etc.) | ~16ms | ~85% dos casos |
| **1b — LLM-as-validator** | Padrões ambíguos (`simule`, `finja`, `imagine`) → Qwen classifica binário `sim/nao` | ~500ms | Jailbreaks sofisticados; só ~5% das mensagens |
| **2a — Lookahead amplo** | Gatilho OOS bloqueia se nenhuma CV-keyword aparece DEPOIS na mesma mensagem | regex | "diabetes com dor no peito" passa, "diabetes pura" bloqueia |
| **2b — Lookbehind variável** | Libera se CV-keyword apareceu ANTES do gatilho OOS | função | "dor no peito mesmo tomando anticoncepcional" passa |
| **2c — Score-based** | Soma pesos OOS vs CV; bloqueia se balanço > 0 com gatilho regex, ≥ 2 sem | aritmética | Múltiplos OOS sem CV (`diabetes + gastrite + gengivite`) |

Vocabulário CV: 50+ keywords amplas + 9 siglas curtas com word-boundary (IC, FA, AVE, TEP, IAM, ECG, AAS, BNP, TVP) para evitar substring match em palavras comuns.

LLM-as-validator desativável via `PRE_SAFETY_LLM_VALIDATOR=0` para testes determinísticos.

---

## Estrutura

```
src/
├── prompts.py                # loader único de prompts .md
├── graph.py                  # LangGraph 10 nós + interrupt_after HITL
├── agents/
│   ├── router.py             # supervisor estatal
│   ├── pre_safety.py         # 3 camadas: regex + lookbehind + score + LLM-validator
│   ├── checkup.py            # FLUXO OBRIGATÓRIO de tools + few-shot
│   ├── triagem.py            # Reranker ATIVO + FLUXO OBRIGATÓRIO
│   ├── suporte.py            # interações medicamentosas + FLUXO OBRIGATÓRIO
│   ├── prescricao.py         # 5º especialista — pausa no interrupt_after
│   ├── escalada_humana.py    # SAMU/FAST determinístico
│   └── safety.py             # dupla camada (heurística + LLM auditor)
├── rag/
│   ├── indexer.py            # ChromaDB + metadado categoria
│   ├── retriever.py          # MMR + Auto-RAG + filtros + cache LRU
│   └── reranker.py           # cross-encoder ATIVO no Triagem
├── tools/
│   ├── prescricao.py         # tag inviolável + validação CFM 2.314/22
│   └── ... (6 tools da Sprint 1: historico, agendamento, interacoes,
│             ritmo, wearable, estratificador_cardiovascular)
├── llm/
│   ├── qwen_client.py        # roteia DashScope ↔ Ollama por backend
│   └── ollama_client.py      # subclasse OO de QwenClient
└── utils/
    └── memoria.py            # summarize-and-replace após 6 turnos

app/
├── dash_app.py               # interface principal + callback HITL
├── streamlit_app.py          # fallback
└── assets/
    ├── style.css             # design system HUD
    ├── blua_custom.css       # customizações Blua
    └── alert.wav             # som red flag

prompts/                      # 6 prompts em Markdown + CHANGELOG
evals/                        # 35 casos + runner + resultados + figuras
tests/                        # 4 arquivos pytest (49 testes)
docs/                         # relatório técnico + 3 gráficos PNG
knowledge_base/               # 12 documentos cardiovasculares
data/mocks/                   # 4 mocks JSON (7 perfis: BENEF-001..003 + 3 CV + MARIA)
scripts/                      # index_kb.sh
ollama/                       # Modelfile + README on-prem (Configuração B)
```

---

## Beneficiários mockados

7 perfis fictícios cobrindo o espectro clínico CV:

| ID | Nome | Idade | Sexo | Perfil clínico |
|---|---|---|---|---|
| `BENEF-MARIA` | Maria Silva Fictícia | 34 | F | HAS controlada com Losartana (paciente canônica do enunciado) |
| `BENEF-001` | João Carlos Fictício | 58 | M | HAS + arritmia sinusal + histórico de TSV |
| `BENEF-002` | Maria Aparecida Fictícia | 67 | F | IC com FE reduzida + FA paroxística + HAS (anticoagulada) |
| `BENEF-003` | Roberto Silva Fictício | 42 | M | HAS estágio 1 recém-diagnosticada |
| `BENEF-CV-001` | Helena Pereira Fictícia | 70 | F | IC com FE 35% + DM + DAC com stent (polipatológica) |
| `BENEF-CV-002` | Roberto Costa Fictício | 53 | M | FA paroxística + apixabana (DOAC, sem INR) |
| `BENEF-CV-003` | Ana Carolina Lima Fictícia | 57 | F | Angina microvascular pós-menopausa |

---

## Observabilidade

Para ativar LangSmith (3 env vars, free tier 5k traces/mês):

```bash
# .env
LANGSMITH_API_KEY=ls__xxx
LANGSMITH_PROJECT=BluaDiagnostics-Sprint2
```

LangGraph instrumenta automaticamente. Traces aninhados visíveis:
`pre_safety → supervisor → rag_retrieve → triagem → tools → safety`.

Para narrativa LGPD em produção, considerar **LangFuse self-hosted** no mesmo perímetro do Ollama.

---

## Demonstração

Vídeo (5 min): **[link YouTube unlisted]**

Roteiro:
- 0:00–0:30 — Arquitetura
- 0:30–1:30 — Happy path Maria (paciente canônica do enunciado)
- 1:30–2:15 — Red flag → escalada SAMU automática
- 2:15–3:00 — Prescrição com HITL síncrono (rascunho gerado → médico aprova/rejeita → grafo retoma)
- 3:00–3:30 — Jailbreak duplo (regex óbvio + LLM-as-validator em padrão ambíguo)
- 3:30–4:00 — Traces LangSmith
- 4:00–4:45 — **Troca para Ollama on-prem ao vivo** (narrativa LGPD)
- 4:45–5:00 — Métricas finais

---

## Equipe

| Nome | RM |
|---|---|
| Lucas Gabriel Alvarenga e Meireles | 567305 |
| Gabriel Augusto da Silva | 567057 |
| Leonardo Kenji Kubo Barboza | 567518 |
| Lucas Koiti Uyeno de Souza | 568128 |
| Lucas Morio Ikeda | 567616 |

---

## Limitações e Roadmap

O modelo de ML real de detecção de arritmias do grupo (de outra disciplina) **não está integrado** nesta entrega — fica como roadmap. A tool `analisar_ritmo_cardiaco` atual usa regra determinística mockada.

O backend Ollama on-prem é funcional mas exige `ollama serve` + `ollama pull qwen:9b` em máquina local — não é testável no Colab gratuito (que é o ambiente da demo). A troca de modo é demonstrável em vídeo de máquina local.

A camada `LLM-as-validator` do pre-safety adiciona ~500ms em mensagens com padrão ambíguo de jailbreak (~5% do tráfego). Latência aceitável dado o ganho de cobertura sobre jailbreaks sofisticados.

Ver `docs/relatorio_final.md` seções 5 e 6 para limitações e roadmap completos.

---

## Disclaimer

⚕️ Este sistema é um trabalho acadêmico e **não substitui avaliação médica**. Em emergências, ligue **192 (SAMU)**.

Mocks de pacientes são fictícios — não há dados reais de pessoas no repositório.
