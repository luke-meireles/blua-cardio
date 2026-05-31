# Pendências pós-integração ArrhythmiaMonitor

Documento criado ao fechar Fase I da integração. Lista o que ficou conhecido mas não-resolvido na integração, com classificação de quando atacar.

**Filosofia de prioridades:** Fase J = "demo polish" (UX + funcionalidade pra demo). Fora de escopo = decisões futuras de Filipe.

---

## Status: Fase J CONCLUÍDA (maio/2026)

7 dos 8 itens implementados em 8 commits. J.4 explicitamente pulado por aceleração — implementação documentada abaixo pode ser feita em sessão futura sem risco de regressão (escopo isolado em chat.py).

| Item | Status | Commit |
|------|--------|--------|
| J.5 dropdown topbar visível | ✓ | 2b733d0 |
| J.7 dropdown /chat unificado (inclui ex-K.1) | ✓ | 6fd65ac |
| J.6 feedback visual perfil ativo | ✓ (resolvido por J.5) | 97960a3 |
| J.3 fallback Blob → CSV local | ✓ | 336038d |
| J.2 CSV saudável MEU_PERFIL | ✓ | bb888e3 |
| J.1 layout hardcoded saudável | ✓ | 0254b2c |
| J.1.b formulário criação + update_patient | ✓ | 31549f7 |
| J.1.b fix-up | ✓ | 33ccc1b |
| J.4 fix conversa /chat reseta | ⏭ PULADO | — |

### Sobre J.4 (pulado)

Bug visual: ao sair do /chat e voltar, área de conversa aparece vazia mesmo com `dcc.Store(session-data)` global. Estado backend preservado, UI não rehidrata.

**Trabalho estimado:** 1-2h em sessão dedicada.
**Risco:** baixo (escopo isolado em dashboard/pages/chat.py + callback em dashboard/app.py).
**Mitigação na demo:** durante apresentação, evitar trocar de página durante uso do /chat. Botão "Nova conversa" pra reset explícito também recomendado nessa sessão.

---

## Fase J — Demo polish (próxima sessão dedicada)

### J.1 — Criação de perfil via UI na página `/meu-perfil`

**Conceito revisado** durante validação I3. MEU_PERFIL não nasce mais como placeholder vazio pra preencher via chatbot. Em vez disso:

- Página `/meu-perfil` ganha **formulário de criação de perfil** com campos: nome, idade, sexo, problema de saúde.
- Submit do formulário persiste no `data/mocks/perfis_clinicos.json` (substituindo a entrada MEU_PERFIL placeholder atual).
- **Após criar perfil**, `meu_perfil_data.csv` (já em `dashboard/data/`, gitignorado até integração) começa a alimentar telemetria do MEU_PERFIL.
- Contraste de demo: Gabriel doente (FA paroxística, dataset com 22% irregularidade) × MEU_PERFIL saudável (BPM 65-76, zero anômalos, 100% regular).

**Trabalho necessário:**
- Refatorar `dashboard/pages/meu_perfil.py` adicionando formulário (Dash `dcc.Input` + `html.Button`).
- Callback que escreve no JSON via `shared.patient_registry` (função nova ou adaptação de existente).
- Validação: idade 0-120, sexo enum, nome obrigatório.

### J.2 — Integrar `meu_perfil_data.csv` saudável

CSV de 200 batimentos saudáveis está em `dashboard/data/meu_perfil_data.csv` (gitignorado até integração). Quando J.1 estiver funcionando, integrar formalmente:

**Trabalho necessário:**
1. Remover entrada de `.gitignore` que ignora `dashboard/data/meu_perfil_data.csv`.
2. `shared/paths.py`: adicionar `MEU_PERFIL_CSV = DASHBOARD_DATA_DIR / "meu_perfil_data.csv"`.
3. `shared/telemetry_store.py`: adicionar entrada em `_ALIAS` (`"MEU_PERFIL": ["MEU_PERFIL"]`) + roteamento de CSV por paciente_id.
4. `data/mocks/perfis_clinicos.json`: ao criar perfil em J.1, `_meta.csv_telemetria` aponta pra `dashboard/data/meu_perfil_data.csv`.
5. Discussão pendente: telemetria do MEU_PERFIL aparece em `/chat` (chatbot lê via tool) ou em `/monitor` (gráfico). Decisão fica pro momento de implementação.

### J.3 — Bypass do Azure Blob com CSV local (Caminho 3)

**Problema:** `/monitor` e `/analise` upstream chamam `load_blob()` sem fallback. Sem Azure Blob configurado, retornam DataFrame vazio. Inutiliza páginas em demo local.

**Solução proposta:** modificar `dashboard/utils/storage.py` pra que `load_blob()` (ou wrapper novo) tenha fallback automático pra CSV local quando Blob indisponível:

```python
def load_telemetria(perfil_ativo=None):
    if blob_available():
        return load_blob()
    # Fallback local
    if perfil_ativo == "GABRIEL":
        return load_csv(GABRIEL_CSV)
    elif perfil_ativo == "MEU_PERFIL":
        return load_csv(MEU_PERFIL_CSV)
    return load_csv(DEFAULT_CSV)
```

**Trade-off:** edita arquivo upstream. Marcar com `# C13 INTEGRATION: fallback local quando Blob indisponível`. Tecnicamente é melhoria (Blob continua funcionando se configurado).

### J.4 — Fix conversa `/chat` reseta visualmente ao navegar (Item 8 do checklist I3)

**Sintoma:** ao sair do `/chat` e voltar, área de conversa aparece vazia. Estado backend pode estar preservado no `dcc.Store(session-data)`, mas UI não rehidrata.

**Hipóteses:**
- Store funciona, mas callback inicial do `chat.py` não lê mensagens do Store ao renderizar a página.
- Conflito entre Store global e estado local do `chat.py`.
- `pages/chat.py` original do `blua-cardio` foi escrito assumindo SPA single-page, sem rehidratação ao re-entrar na rota.

**Trabalho:** debug do callback inicial + integração explícita do Store com display de mensagens. Adicionar botão "Nova conversa" pra reset explícito (Filipe pediu).

### J.5 — Fix dropdown topbar não mostra valor selecionado

**Sintoma:** dropdown PERFIL no topbar aparece visualmente vazio mesmo com `value="GABRIEL"` hardcoded. Capturado em screenshot do smoke I3.

**Hipóteses:**
- CSS de `.hud-topbar__telemetry` quebrando renderização do `<select>` interno do Dash Dropdown.
- `storage_type="session"` do Store dessincronizando com valor renderizado.
- Falta de callback initial pra setar value baseado no Store.

**Trabalho:** inspecionar DevTools, isolar causa, fix CSS ou callback.

### J.6 — Feedback visual claro de qual perfil está ativo

**STATUS: resolvido implicitamente por J.5** (sem código adicional).

A motivação original deste item ("como não dá pra ver o nome, não tem certeza se o perfil é mudado completamente") tinha como causa raiz o bug do dropdown topbar invisível — corrigido em J.5. Agora que o nome do perfil ativo aparece claramente no dropdown PERFIL (topbar), o feedback visual de seleção já é suficiente para a demo. Decisão tomada durante execução do bloco UX (após J.7).

Caso queiramos reforço visual no futuro (header "Perfil ativo: X" por página, toast ao trocar, badge no dropdown), as opções permanecem documentadas abaixo como referência:

- Header de cada página mostrando "Perfil ativo: X" (gabriel.py upstream já tem parcialmente — replicar em meu_perfil.py e pacientes.py).
- Toast/notificação ao trocar dropdown.
- Indicador visual no próprio dropdown (badge, cor, etc).

### J.7 — Unificar dropdown `/chat` com topbar (inclui ex-K.1)

**Problemas combinados:**

1. **Inconsistência visual:** `dashboard/pages/chat.py` linha 84-91 tem `BENEFICIARIOS` hardcoded com 5+ perfis (Gabriel + 4 BENEF-001 a BENEF-CV-003). Topbar mostra só 2 (Gabriel + MEU_PERFIL). Inconsistência visível.

2. **Limitação visual do criar_perfil_paciente** (anteriormente classificado como bug "K.1"): achado empírico durante I3 (teste com perfil "Garfield" BENEF-NEW-001) provou que a tool **SALVA corretamente** no JSON. O problema percebido como "não salva" é que o dropdown hardcoded do `/chat` não atualiza dinamicamente. Perfis criados via chatbot ficam invisíveis no dropdown, dando impressão errônea de falha.

**Trabalho:** substituir lista hardcoded por `list_patients()` dinâmico de `shared.patient_registry`. Ou: filtrar pra mostrar apenas Gabriel + MEU_PERFIL pra alinhar com topbar (BENEFs ficam acessíveis pelo chatbot via tool calls, não via dropdown).

Após J.7, perfis criados via `criar_perfil_paciente` aparecerão no dropdown automaticamente.

---

## Fora de escopo (decisão futura de Filipe)

### Out.1 — Atualização do `README.md` raiz

Mantido upstream literal por enquanto (C12). Filipe atualiza pós-decisão de merge.

### Out.2 — Push pro remoto `ArrhythmiaMonitor`

Branch `integracao-arrhythmiamonitor` no repo local `blua-cardio`. Push pro GitHub do `ArrhythmiaMonitor` é decisão futura.

### Out.3 — Features pendentes do README upstream

3 features citadas no README upstream que não foram implementadas:
- Agendamento de consultas no Blob (chatbot grava localmente via R3 — `data/consultas/`).
- Relatório de registros recentes via `load_blob`.
- Refinamento de RAG pra dúvidas sobre Warfarina/Atenolol/Losartana.

### Out.4 — Setup Azure Blob real

Se J.3 (bypass com CSV local) for suficiente pra demo, Azure real pode ser indefinidamente adiado. Caso queira testar integração completa cloud, ver tutorial em https://learn.microsoft.com/pt-br/azure/storage/blobs/storage-quickstart-blobs-portal ou usar Azurite (emulador local).

---

**Total:** 7 itens Fase J + 4 itens fora de escopo = 11 pendências documentadas.

---

## Notas de cleanup durante fechamento Fase I

Durante I3 (smoke browser manual), Filipe testou a tool `criar_perfil_paciente` criando perfil de teste "Garfield" (BENEF-NEW-001, condição hipertensão). O perfil foi removido do JSON no cleanup pré-commit I4 — era dado de teste descartável, não destinado a permanecer no repo. O teste em si serviu de evidência empírica importante (ver J.7).

`meu_perfil_data.csv` (gerado por Claude em maio/2026) foi movido de raiz pra `dashboard/data/` e está gitignorado temporariamente. Será integrado formalmente em J.2.

**Última atualização:** maio/2026, fechamento Fase J (7 de 8 itens — J.4 pulado por aceleração).
