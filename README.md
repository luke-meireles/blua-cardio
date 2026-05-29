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

## Como rodar

```bash
python app/unified_app.py
```

Acessa em `http://localhost:8050`:

| Rota | Conteúdo |
|------|----------|
| `/` | Chat (chatbot LangGraph + RAG) |
| `/monitor` | Telemetria PPG ao vivo (ESP32 + MAX30100) |
| `/analise` | Análise histórica do CSV de telemetria |
| `/gabriel` | Prontuário do paciente Gabriel (referência) |
| `/pacientes` | Lista do registry de beneficiários |

Para produção:

```bash
gunicorn -w 1 -b 0.0.0.0:8050 app.unified_app:server
```

Servidor único Flask hospeda chat + dashboard via `use_pages=True`.

## Configuração via variáveis de ambiente

| Variável | Default | Uso |
|----------|---------|-----|
| `DASHSCOPE_API_KEY` | — (**obrigatória**) | Chave da API DashScope/Qwen. Sem ela, o chatbot não inicializa. Ver `.env.example`. |
| `BLUA_TELEMETRY_CSV` | `data/cardiac_data.csv` (opcional) | Path do CSV de telemetria ao vivo do dashboard. Defina para apontar pra outro arquivo (ex.: ambiente de teste, integração futura com Azure Blob mount). |
| `BLUA_GABRIEL_CSV` | `data/gabriel_data.csv` (opcional) | Path do CSV de referência do paciente Gabriel (200 batimentos). |
| `BLUA_ROOT` | pasta do projeto (opcional) | Raiz do projeto pra resolução de paths. Útil em testes e deployments com volumes montados. |
