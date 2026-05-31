# Checklist Smoke Browser — Fase I.3

Validação manual visual da integração `ArrhythmiaMonitor` concluída na
branch `integracao-arrhythmiamonitor`.

## Pré-requisitos

- Estar no diretório raiz do projeto.
- Branch ativa: `integracao-arrhythmiamonitor` (confirmar com `git branch --show-current`).
- App rodando localmente:

```bash
python dashboard/app.py
```

- Aguardar ~10-15 s pro RAG aquecer. Logs esperados:
  - `[graph] Grafo BluaDiagnostics Sprint 2 compilado com sucesso.`
  - `[graph] Modelos RAG aquecidos em ~12s. Primeira mensagem agora vai fluir.`
  - `[dash_app] Grafo pronto.`
  - `Dash is running on http://127.0.0.1:8050/`

- Abrir `http://localhost:8050` no browser.

## Itens a validar (15 total)

### Navegação básica (4)

1. [ ] **Home renderiza.** `http://localhost:8050/` carrega a página home upstream sem traceback.
2. [ ] **Topbar mostra 7 links.** Em ordem: HOME, MONITOR, ANALISE, GABRIEL, MEU PERFIL, CHAT, PACIENTES.
3. [ ] **Topbar mostra dropdown de perfil.** Dentro da seção telemetria (direita), com "Gabriel" selecionado como default. Tem label "PERFIL" antes do dropdown.
4. [ ] **Console DevTools (F12) sem erros vermelhos.** Warnings amarelos do Dash são aceitáveis.

### Página /chat (chatbot)  (4)

5. [ ] **`/chat` renderiza** com input de mensagem + área de conversa + painéis técnicos.
6. [ ] **Enviar mensagem "oi"** — chatbot responde sem traceback. Resposta pode demorar ~5-10 s (chamada DashScope).
7. [ ] **Painéis técnicos populam** após resposta: Confidence, Trajetória, RAG (chunks + scores), Tools chamadas, Safety flags.
8. [ ] **Estado preservado entre navegações.** Sair do `/chat` pra outra página (ex.: `/monitor`) e voltar pro `/chat` — conversa anterior continua na área de chat (`dcc.Store(session-data)` global).

### Páginas de prontuário (3)

9. [ ] **`/gabriel` renderiza prontuário completo.** Mostra Gabriel Oliveira, 38a, condições (FA paroxística + HAS + taquicardia supra), Dr. Gregory House, medicações (Apixabana + Metoprolol + Losartana). 628 linhas do upstream com dados hardcoded.
10. [ ] **`/meu-perfil` renderiza placeholder.** Mostra "Filipe Meireles", ID: MEU_PERFIL, Idade: —, Sexo: —, listas vazias (nenhuma condição/medicação/alergia), link "Editar via chatbot".
11. [ ] **`/pacientes` mostra 2 cards.** Card Gabriel + Card Meu Perfil. Cada um com nome, ID, idade, link "Ver prontuário".

### Dropdown como atalho de navegação (2)

12. [ ] **Trocar dropdown pra "Meu Perfil"** — página muda pra `/meu-perfil` automaticamente.
13. [ ] **Trocar dropdown pra "Gabriel"** — página muda pra `/gabriel` automaticamente.

### Páginas de telemetria (não afetadas pelo dropdown — C13 revisado) (2)

14. [ ] **`/monitor` renderiza.** Controles aparecem (Iniciar/Parar/Zerar, dropdown de origem, sliders). Gráficos podem estar **vazios** se Azure Blob não estiver configurado — **isso é OK**. Errors no console (5xx, traceback no log do app) NÃO são.
15. [ ] **`/analise` renderiza.** Tabela/gráficos de análise histórica. Idem `/monitor`: vazio aceito sem Blob, erros não.

## Notas

- **Itens 14 e 15** (`/monitor`, `/analise`): se Azure Blob Storage não estiver configurado em `.env` (`AZURE_STORAGE_CONNECTION_STRING`), `load_blob()` retorna DataFrame vazio. Gráficos vazios e mensagens tipo "Carregando dados do Blob Storage..." são esperados. **Isso não é falha.**
- **Item 12/13** (dropdown): callback navega via `Output("hud-url", "pathname", allow_duplicate=True)`. Se a página não mudar ao trocar o dropdown, verificar se `dcc.Store(perfil-ativo)` foi registrado (DevTools → Application → Session Storage).
- **Confidence/Trajetória/RAG no `/chat`** (item 7): a primeira mensagem demora porque RAG aquece. Mensagens subsequentes são mais rápidas.

## Reportar

Para cada item ✗:
- Descrição do que deveria acontecer
- O que aconteceu de fato
- Screenshot ou trecho de console DevTools/log do app

## Após o checklist

Quando todos os 15 itens ✓ (ou itens 14/15 ✓ com ressalva de Blob):
- Reportar "I3 verde, pode commitar"
- Vai disparar **I4 — commit final consolidado**

Se algum item ✗:
- Pausa pra diagnóstico antes do commit I4
- Dependendo do bug, pode disparar rollback de algum commit recente

## Histórico

Gerado em fim da Fase I.3 da integração ArrhythmiaMonitor.
Validação manual obrigatória — Claude Code (CLI) não consegue executar.
