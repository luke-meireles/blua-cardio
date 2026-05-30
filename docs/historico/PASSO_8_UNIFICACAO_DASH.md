# PASSO_8_UNIFICACAO_DASH.md

**Pré-requisito absoluto:** Passos 0 a 7 do `PLANO_MERGE.md` concluídos, validados, e commitados em `main` (com push para o remoto, se houver). Pytest baseline verde. Smoke tests A-D do Passo 7 passando.

**Versão:** 1.0 · **Data prevista de execução:** após sprint atual estabilizado.
**Tempo estimado:** 60-90min.
**Risco:** alto (refatoração estrutural de UI + callbacks).

---

## Sumário

Vamos unificar dois servidores Dash (chatbot na 8050 + dashboard na 8051) em **um único servidor Flask na porta 8050**, usando o padrão `use_pages=True` do Dash. O resultado:

```
http://localhost:8050/         → / (página inicial: chat)
http://localhost:8050/chat     → chatbot (página)
http://localhost:8050/monitor  → live PPG monitor
http://localhost:8050/analise  → análise histórica
http://localhost:8050/pacientes → lista de pacientes do registry
```

O `app/unified_app.py` que entreguei em `blua_merge_files/app/` já está pronto e testado — mas ele assume que as páginas estão no padrão `dash.register_page()`. Este plano cobre a conversão.

| # | Sub-passo | Tempo | Risco |
|---|-----------|-------|-------|
| 8.1 | Pré-flight: confirmar baseline antes de tocar em qualquer coisa | 5min | nenhum |
| 8.2 | Criar branch dedicado para o Passo 8 | 2min | nenhum |
| 8.3 | Inventário: mapear callbacks, IDs e assets dos dois apps | 10min | médio (passo de leitura) |
| 8.4 | Adotar `pages/` do dashboard | 10min | médio |
| 8.5 | Converter chatbot em `pages/chat.py` | 20min | alto |
| 8.6 | Criar `pages/pacientes.py` (página nova, lista do registry) | 10min | baixo |
| 8.7 | Posicionar `app/unified_app.py` como entrypoint único | 5min | médio |
| 8.8 | Consolidar assets/CSS (resolver conflitos) | 10min | médio |
| 8.9 | Smoke tests do app unificado | 15min | — |
| 8.10 | Aposentar entrypoints antigos | 3min | baixo |
| 8.11 | Merge no main e cleanup | 5min | nenhum |

**Regra de ouro:** se a unificação quebrar qualquer um dos cenários A-D do Passo 7, **rolar back e voltar a rodar nos dois servidores separados**. O `unified_app.py` é polimento de UX — funcionalidade já está entregue pelos Passos 1-7.

---

## Sub-passo 8.1 — Pré-flight

### 8.1.1 Objetivo
Validar que estamos em estado limpo antes da refatoração. Se baseline já está vermelho, o problema é anterior e precisa ser resolvido primeiro.

### 8.1.2 Ações
```bash
# Conferir branch e estado
git status
git branch --show-current
# Esperado: working tree clean, em main.

# Conferir último commit (deve ser o do Passo 7)
git log --oneline -5

# Pytest verde
pytest --tb=short 2>&1 | tail -5
# Esperado: BASELINE (49 + qualquer teste novo dos Passos 1-7) passando.

# Os dois apps atuais sobem? (subir cada um numa aba do terminal e abrir no navegador)
# Aba 1: python app/dash_app.py        → deve abrir chatbot em 8050
# Aba 2: python dashboard_legacy/app.py → deve abrir dashboard em 8051 (ou outra porta)
```

### 8.1.3 Validação
- Pytest verde.
- Chatbot acessível e respondendo a uma mensagem simples.
- Dashboard acessível, exibindo BPM (ou indicando "sem dados" gracefully).

### 8.1.4 Critério de parada
- Qualquer um dos dois apps não sobe → o problema é dos Passos anteriores. **PARAR**, voltar pro `PLANO_MERGE.md`, não iniciar Passo 8.

---

## Sub-passo 8.2 — Branch dedicado

### 8.2.1 Objetivo
Isolar a refatoração numa branch própria. Se der ruim, basta deletar a branch sem afetar `main`.

### 8.2.2 Ações
```bash
git checkout -b feature/unificacao-dash
git status
# Esperado: "On branch feature/unificacao-dash, working tree clean"
```

### 8.2.3 Validação
- Branch criada. `git branch --show-current` retorna `feature/unificacao-dash`.

### 8.2.4 Commit
Nenhum ainda. Próximos sub-passos geram commits granulares dentro desta branch.

---

## Sub-passo 8.3 — Inventário (sem editar nada ainda)

### 8.3.1 Objetivo
Antes de mover/converter arquivo, **mapear tudo**: callbacks, IDs de componentes, assets CSS, paths de URL. Conflitos pegos agora custam 5min; pegos depois custam 1h.

### 8.3.2 Ações

**8.3.2.1 — Callbacks do chatbot:**
```bash
grep -n "@app.callback\|@callback" app/dash_app.py
grep -n "Input(\|Output(\|State(" app/dash_app.py | head -30
```
**MOSTRAR resultado ao usuário.** Listar todos os IDs que aparecem em `Input(...)`, `Output(...)`, `State(...)`. Esses IDs vão precisar sobreviver na página convertida.

**8.3.2.2 — Callbacks do dashboard:**
```bash
grep -rn "@app.callback\|@callback" dashboard_legacy/ --include="*.py"
grep -rn "Input(\|Output(\|State(" dashboard_legacy/ --include="*.py" | head -50
```

**8.3.2.3 — Verificar se as páginas do dashboard JÁ usam `register_page`:**
```bash
grep -rn "register_page\|dash.register_page" dashboard_legacy/pages/ 2>/dev/null
```
- Se já usam → ótimo, sub-passo 8.4 é só mover.
- Se não usam → vai precisar adicionar a chamada `dash.register_page(...)` no topo de cada arquivo.

**8.3.2.4 — Assets / CSS:**
```bash
ls -la dashboard_legacy/assets/ 2>/dev/null
ls -la app/assets/ 2>/dev/null
ls -la assets/ 2>/dev/null
```
**Conferir conflitos de nome:** se ambos os projetos têm um `style.css` ou `custom.css`, vão se sobrescrever depois da unificação. Anotar quais arquivos colidem.

**8.3.2.5 — Conflitos de ID:**
Comparar a lista de IDs do chatbot (8.3.2.1) com a do dashboard (8.3.2.2). **Qualquer ID que aparece nos dois é um conflito** — vai precisar renomear num dos lados.

Anotar a lista de conflitos para resolver no sub-passo 8.5.

### 8.3.3 Validação
- Documento (mental ou em arquivo `INVENTARIO_8.md` temporário) com:
  - Lista de IDs do chatbot.
  - Lista de IDs do dashboard.
  - Lista de conflitos.
  - Lista de assets CSS conflitantes.
  - Confirmação se páginas do dashboard usam `register_page` ou não.

### 8.3.4 Critério de parada
- Se aparecer mais de 5 conflitos de ID: **PARAR**, mostrar a lista ao usuário, decidir estratégia (prefixar todos os IDs do chat com `chat-` ou todos os do dashboard com `dash-`).

---

## Sub-passo 8.4 — Adotar `pages/` do dashboard

### 8.4.1 Objetivo
Mover páginas do `dashboard_legacy/pages/` para `pages/` na raiz do projeto, garantindo que cada uma chama `dash.register_page()`.

### 8.4.2 Ações

**8.4.2.1 — Criar pasta e mover:**
```bash
mkdir -p pages
cp dashboard_legacy/pages/*.py pages/
ls -la pages/
# Esperado: home.py, monitor.py, analise.py, gabriel.py (ou nomes equivalentes).
```

**8.4.2.2 — Garantir `register_page` no topo de cada página:**

Para cada arquivo `pages/*.py`, conferir se já tem no topo:
```python
import dash
dash.register_page(__name__, path='/monitor', name='Monitor', order=2)
```

Se não tem, adicionar. Mapping sugerido:

| Arquivo | path | name | order |
|---------|------|------|-------|
| `pages/home.py` | (deletar — substituído por chat) | — | — |
| `pages/monitor.py` | `/monitor` | Monitor | 2 |
| `pages/analise.py` | `/analise` | Análise | 3 |
| `pages/gabriel.py` | `/gabriel` | Gabriel | 4 |

**Decisão importante:** o `home.py` do dashboard provavelmente vai conflitar com `/` que ficará pro chat. **Recomendação:** deletar `pages/home.py` e usar `chat.py` (próximo sub-passo) como home com `path='/'`.

**8.4.2.3 — Renomear IDs conflitantes (se o inventário 8.3 acusou):**

Para cada conflito identificado, escolher um lado e prefixar. Recomendo prefixar do lado do dashboard (`monitor-bpm` em vez de `bpm`), porque o chatbot tem mais callbacks acoplados ao código original.

**8.4.2.4 — Imports relativos:**

Páginas que importavam `from utils.storage import ...` ou similar precisam continuar funcionando. Conferir:
```bash
grep -n "^from \|^import " pages/*.py
```
Se algum import quebrar com a nova localização, ajustar. Geralmente `from utils.X` continua funcionando se `utils/` for movido para a raiz junto.

```bash
# Mover utils/ do dashboard se ainda não foi
[ -d "dashboard_legacy/utils" ] && cp -r dashboard_legacy/utils ./utils
```

### 8.4.3 Validação

```bash
# 8.4.3.1 — Páginas importam sem erro
python -c "
import sys
sys.path.insert(0, '.')
import dash
app = dash.Dash(__name__, use_pages=True, pages_folder='pages')
print('Páginas registradas:')
for p in dash.page_registry.values():
    print(f\"  {p['relative_path']} → {p['module']}\")
"
# Esperado: lista com monitor, analise, gabriel.
```

### 8.4.4 Commit
```
refactor(pages): move páginas do dashboard para pages/ com register_page

- pages/monitor.py, pages/analise.py, pages/gabriel.py
- dashboard_legacy/pages/ removido (conteúdo migrado)
- IDs prefixados com 'monitor-' para evitar conflito com chat
```

### 8.4.5 Critério de parada
- Erro de import ao registrar páginas: rastrear o módulo que falha, conferir se foi movido pra `pages/` ou se depende de algum import legado.

---

## Sub-passo 8.5 — Converter chatbot em `pages/chat.py`

### 8.5.1 Objetivo
O arquivo mais delicado. Pegar o `app/dash_app.py` original (que cria seu próprio `Dash(...)`) e transformá-lo numa **página** que entrega `layout` e registra `callback`s decorados.

### 8.5.2 Estratégia

Hoje o `app/dash_app.py` tem estrutura tipo:
```python
app = Dash(__name__, ...)
app.layout = html.Div([...])

@app.callback(Output(...), Input(...))
def handler(...): ...

if __name__ == "__main__":
    app.run(...)
```

Vamos transformar em:
```python
import dash
from dash import html, dcc, callback, Input, Output

dash.register_page(__name__, path='/chat', name='Chat', order=1)

layout = html.Div([...])  # tudo que estava em app.layout

@callback(Output(...), Input(...))   # @callback global, não @app.callback
def handler(...): ...
```

A diferença crítica: **`@app.callback` vira `@callback`** (decorator global do módulo `dash`). Isso porque no modo `use_pages=True` os callbacks são registrados no `Dash` central pelo `unified_app.py`, não na página.

### 8.5.3 Ações

**8.5.3.1 — Copiar como template:**
```bash
cp app/dash_app.py pages/chat.py
```

**8.5.3.2 — Editar `pages/chat.py` — 5 mudanças cirúrgicas:**

**Mudança 1:** No topo, adicionar registro de página.
```diff
+ import dash
+ dash.register_page(__name__, path='/chat', name='Chat', order=1)

  from dash import Dash, html, dcc, callback, Input, Output, State
- # ...
```

**Mudança 2:** Trocar `from dash import Dash, ...` para remover `Dash` e adicionar `callback`:
```diff
- from dash import Dash, html, dcc, Input, Output, State
+ from dash import html, dcc, callback, Input, Output, State
```

**Mudança 3:** Apagar a criação do `app = Dash(...)`:
```diff
- app = Dash(__name__, external_stylesheets=[...])
- server = app.server
- app.title = "Blua Diagnostics"
```

**Mudança 4:** Renomear `app.layout = ...` para variável módulo `layout = ...`:
```diff
- app.layout = html.Div([...])
+ layout = html.Div([...])
```

**Mudança 5:** Trocar todos os `@app.callback` por `@callback`:
```diff
- @app.callback(
+ @callback(
      Output("..."),
      Input("..."),
  )
  def handler(...):
      ...
```

**Mudança 6:** Remover o bloco `if __name__ == "__main__"`:
```diff
- if __name__ == "__main__":
-     app.run(debug=False, host="0.0.0.0", port=8050)
```

**8.5.3.3 — Resolver conflitos de ID identificados no 8.3.2.5:**

Se algum ID do chat colide com algum do dashboard, prefixar do lado do chat (ex.: `chat-input`, `chat-history`, `chat-send-btn`) em **dois lugares simultaneamente**: no `layout` E em todos os `Input/Output/State` dos callbacks.

**8.5.3.4 — Conferir que `chat.py` não cria página `/` por engano:**
- `path='/chat'` no `register_page`.
- Se quiser o chat na raiz `/` também, mudar para `path='/'` e `path_template=None` (escolher: ou `/chat` ou `/`, não os dois).

**Recomendação:** `path='/chat'`. A página `/` raiz vai redirecionar pro chat (configurável no `unified_app.py`).

**MOSTRAR DIFF COMPLETO ao usuário antes de salvar.** Esta é a maior mudança do Passo 8.

### 8.5.4 Validação

```bash
# 8.5.4.1 — Import sem erro
python -c "
import sys
sys.path.insert(0, '.')
from pages import chat
print('layout existe?', hasattr(chat, 'layout'))
print('módulo:', chat.__name__)
"

# 8.5.4.2 — Página registrada
python -c "
import sys; sys.path.insert(0, '.')
import dash
app = dash.Dash(__name__, use_pages=True, pages_folder='pages')
chat_page = [p for p in dash.page_registry.values() if p['module'] == 'pages.chat']
assert chat_page, 'chat.py não foi registrado'
print('Chat registrado em:', chat_page[0]['relative_path'])
"
# Esperado: Chat registrado em: /chat
```

### 8.5.5 Commit
```
refactor(chat): converte app/dash_app.py em pages/chat.py

- Adiciona dash.register_page(path='/chat')
- Substitui @app.callback por @callback global
- Remove instância Dash() local (movida para app/unified_app.py)
- IDs prefixados com 'chat-' para evitar conflito com dashboard
```

### 8.5.6 Critério de parada
- Algum callback do chat depende de `app.server` ou de instância específica do Dash: **PARAR**, mostrar o callback, decidir como adaptar (geralmente dá pra usar `dash.get_app()` se for caso extremo, mas evitar).
- Se um callback do chat precisa rodar **antes** de qualquer página carregar (ex.: bootstrap LangSmith): mover essa lógica pro `app/unified_app.py` (que já tem o bloco de bootstrap).

---

## Sub-passo 8.6 — Página nova `pages/pacientes.py`

### 8.6.1 Objetivo
Página simples que lista os pacientes do `shared.patient_registry`. Útil pra demo e pra debug. **Opcional dentro do Passo 8** — pode pular se quiser ir direto pro 8.7.

### 8.6.2 Ações

Criar `pages/pacientes.py`:
```python
"""Lista geral de pacientes do registry."""
import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

from shared.patient_registry import list_patients

dash.register_page(__name__, path='/pacientes', name='Pacientes', order=5)

def _patient_row(p: dict) -> dbc.ListGroupItem:
    return dbc.ListGroupItem([
        html.Strong(p['nome']),
        html.Span(f" · {p['id']} · {p['idade']}a · {p['sexo']}",
                  className='text-muted'),
        html.Div(
            ', '.join(p.get('condicoes_ativas', [])) or 'sem condições ativas',
            className='small'
        ),
    ])

layout = html.Div(className='hud-page-content', children=[
    html.H2('Pacientes cadastrados'),
    html.P('Lista lida em tempo real de data/mocks/perfis_clinicos.json'),
    dcc.Interval(id='pacientes-refresh', interval=10_000),
    dbc.ListGroup(id='pacientes-list'),
])

@callback(
    Output('pacientes-list', 'children'),
    Input('pacientes-refresh', 'n_intervals'),
)
def atualizar_lista(_n):
    return [_patient_row(p) for p in list_patients()]
```

### 8.6.3 Validação
```bash
python -c "
import sys; sys.path.insert(0, '.')
from pages import pacientes
assert hasattr(pacientes, 'layout')
print('OK — pacientes.py importa e tem layout')
"
```

### 8.6.4 Commit
```
feat(pages): adiciona pages/pacientes.py — lista do registry

Página em /pacientes lê do shared.patient_registry com refresh a cada 10s.
Útil para conferir efeito de criar_perfil_paciente em tempo real.
```

---

## Sub-passo 8.7 — Posicionar `unified_app.py` como entrypoint

### 8.7.1 Objetivo
Substituir o `app/dash_app.py` original (já convertido em página) pelo `app/unified_app.py` como ponto de entrada do servidor.

### 8.7.2 Ações

**8.7.2.1 — Copiar entrypoint do pacote:**
```bash
cp blua_merge_files/app/unified_app.py app/unified_app.py
```

**8.7.2.2 — Conferir imports do `unified_app.py`:**

O arquivo importa:
- `shared.paths` → existe desde Passo 1 ✓
- `utils.storage` → veio do dashboard (8.4.2.4) ✓
- `colab_setup` → opcional, best-effort ✓

Se `utils/storage.py` não tiver função `ensure_csv` ou constante `DEFAULT_CSV`, ajustar `unified_app.py` linha:
```python
from utils.storage import ensure_csv, DEFAULT_CSV
```
para apontar pro nome correto. Se não tiver função equivalente, comentar essa linha (e o `ensure_csv(DEFAULT_CSV)` logo abaixo).

**8.7.2.3 — Decidir destino do `/` raiz:**

O `unified_app.py` não força nenhuma página em `/`. Para que `/` aponte pro chat, basta o `pages/chat.py` ter `path='/'` (em vez de `/chat`). Alternativa: criar `pages/_root.py` simples que redireciona:
```python
import dash
from dash import dcc
dash.register_page(__name__, path='/', name='Início', order=0)
layout = dcc.Location(href='/chat', id='root-redirect')
```

Recomendação: **mudar `pages/chat.py` para `path='/'`** — mais simples, sem redirect.

### 8.7.3 Validação

```bash
# 8.7.3.1 — Subir o servidor unificado
python app/unified_app.py &
SERVER_PID=$!
sleep 5

# 8.7.3.2 — Conferir que está vivo
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8050/
# Esperado: 200

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8050/monitor
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8050/analise
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8050/chat
# Esperado: 200 em todas

# 8.7.3.3 — Parar servidor
kill $SERVER_PID
```

### 8.7.4 Commit
```
feat(app): adiciona app/unified_app.py como entrypoint único

Servidor Dash único na 8050 com use_pages=True, hospedando chat (/),
monitor, analise, gabriel, pacientes.
```

### 8.7.5 Critério de parada
- Servidor não sobe: ler stack trace, identificar import quebrado.
- Servidor sobe mas alguma rota retorna 404: a página não foi registrada — conferir `register_page` no arquivo correspondente.
- Servidor sobe mas alguma rota retorna 500: erro no `layout` ou em algum callback inicial — abrir browser DevTools, ler console do navegador + log do servidor.

---

## Sub-passo 8.8 — Consolidar assets/CSS

### 8.8.1 Objetivo
Garantir que ambos os designs (chat + dashboard) renderizam sem se atropelar visualmente.

### 8.8.2 Ações

**8.8.2.1 — Estrutura final de assets:**
```bash
mkdir -p assets
# Mover assets do chat (se existirem)
[ -d "app/assets" ] && cp -r app/assets/* assets/
# Mover assets do dashboard (se existirem)
[ -d "dashboard_legacy/assets" ] && cp -r dashboard_legacy/assets/* assets/
ls -la assets/
```

**Atenção:** Dash carrega TUDO de `assets/` automaticamente. Se houver dois `style.css`, um vai sobrescrever o outro — e o resultado depende da ordem alfabética. Convenção: prefixar.

**8.8.2.2 — Resolver conflitos de nome:**
```bash
# Renomear pra evitar colisão
[ -f "assets/style.css" ] && mv assets/style.css assets/chat-style.css
# (se houver outro do dashboard com mesmo nome, conferir antes de mover)
```

**8.8.2.3 — Scopear CSS:**

Se ambos definem regras globais (`body`, `.container`, etc.), a ordem alfabética vai gerar resultados imprevisíveis. Adicionar prefixos de classe:
- CSS do chat: scopear com `.hud-page--chat .alguma-classe`
- CSS do dashboard: scopear com `.hud-page--monitor .alguma-classe`

E adicionar a classe correspondente no `layout` de cada página:
```python
# pages/chat.py
layout = html.Div(className='hud-page--chat', children=[...])

# pages/monitor.py
layout = html.Div(className='hud-page--monitor', children=[...])
```

**8.8.2.4 — Conferir tema do dbc:**

O `unified_app.py` usa `external_stylesheets=[dbc.themes.BOOTSTRAP]`. Se algum dos apps originais usava outro tema (`CYBORG`, `DARKLY`, etc.), decidir qual prevalece e ajustar.

### 8.8.3 Validação

Subir o servidor unificado, navegar entre todas as páginas no browser. Conferir visualmente:
- Topbar consistente.
- Cores do chat não sangram pro dashboard e vice-versa.
- Botões, inputs, e cards renderizam dentro do esperado.

### 8.8.4 Commit
```
style(assets): consolida CSS em assets/ com scoping por página

- Prefixos hud-page--chat e hud-page--monitor evitam colisão de regras
- style.css do chat renomeado para chat-style.css
- Tema Bootstrap padrão; temas customizados antigos comentados
```

---

## Sub-passo 8.9 — Smoke tests do app unificado

### 8.9.1 Objetivo
Validar que TODOS os 4 cenários A-D do Passo 7 continuam funcionando após a unificação. Nada novo, mesmos cenários, ambiente novo.

### 8.9.2 Ações

Subir o servidor unificado:
```bash
python app/unified_app.py
```

Abrir `http://localhost:8050` no navegador e rodar:

**Cenário A — Criar paciente novo**
1. Navegar para `/chat` (ou `/` se essa for a home).
2. Mensagem: *"Quero cadastrar Pedro Lima, 60 anos, masculino, fibrilação atrial"*
3. Esperado: preview com confirmação.
4. *"Sim, pode criar"* → ID novo retornado.
5. Navegar para `/pacientes` → Pedro Lima aparece na lista (refresh em até 10s).

**Cenário B — Telemetria live do GABRIEL**
1. Garantir `data/cardiac_data.csv` tem linhas pra Gabriel.
2. No chat, selecionar GABRIEL como paciente ativo.
3. *"Como está meu ritmo cardíaco agora?"*
4. Esperado: classificação live + contexto clínico.
5. Em paralelo, abrir `/monitor` em outra aba → BPM ao vivo do mesmo dado.

**Cenário C — Backwards compat**
1. Selecionar paciente legado (BENEF-001).
2. *"Quais são minhas condições?"* → resposta normal.

**Cenário D — Defesa contra criação acidental**
1. *"Crie um paciente fictício pra teste"*
2. Esperado: recusa OU preview com pedido de confirmação.

**Cenário E (novo, exclusivo do Passo 8) — Navegação fluida**
1. Estar no `/chat` no meio de uma conversa.
2. Clicar em "MONITOR" na topbar.
3. Esperado: muda pra `/monitor` sem reload (URL muda mas a aba não pisca branca).
4. Voltar pro `/chat` → conversa preservada (estado do `dcc.Store` mantido).

### 8.9.3 Validação
- A, B, C, D passando exatamente como passaram no Passo 7.
- E passando (navegação SPA fluida).
- Console do browser (DevTools → Console) sem erros vermelhos.

### 8.9.4 Critério de parada
- A, B, C ou D quebra → bug introduzido pela unificação. **PARAR**. Opções:
  - Identificar o callback/ID responsável e corrigir (se for óbvio).
  - Se não for óbvio em 15min: **reverter** o branch (sub-passo 8.11 com cleanup) e ficar com dois servidores separados.

---

## Sub-passo 8.10 — Aposentar entrypoints antigos

### 8.10.1 Objetivo
Após cenários A-E verdes, remover os entrypoints duplicados pra evitar confusão de quem clonar o repo depois.

### 8.10.2 Ações

```bash
# O dash_app.py original já é o chat.py agora — apagar original
git rm app/dash_app.py

# O dashboard_legacy/ inteiro pode sair (conteúdo já migrado)
git rm -r dashboard_legacy/

# Atualizar README.md: substituir instrução de "rodar dois servidores"
# por instrução única:
#
#   python app/unified_app.py
#
# E descrever os 5 paths disponíveis (/, /chat, /monitor, /analise, /pacientes)
```

**MOSTRAR o diff do README ao usuário antes de salvar.**

### 8.10.3 Validação
```bash
git status   # mostrar tudo que será removido
# Conferir que não removemos nada que ainda seja usado por imports vivos
grep -rn "dash_app\|dashboard_legacy" --include="*.py" .
# Esperado: nenhum resultado.
```

### 8.10.4 Commit
```
chore: remove entrypoints legados pós-unificação

- app/dash_app.py removido (substituído por pages/chat.py)
- dashboard_legacy/ removido (conteúdo migrado para pages/ + utils/)
- README atualizado com instrução única de execução
```

---

## Sub-passo 8.11 — Merge no main e cleanup

### 8.11.1 Objetivo
Trazer a refatoração para `main`.

### 8.11.2 Ações
```bash
# Conferir histórico de commits da branch
git log --oneline main..feature/unificacao-dash
# Esperado: ~8 commits (8.4 a 8.10).

# Voltar pro main e fazer merge
git checkout main
git merge --no-ff feature/unificacao-dash -m "merge: unificação dos apps Dash em servidor único

Passo 8 do plano de merge. Resultado:
- Um servidor Flask na porta 8050
- Páginas: / (chat), /monitor, /analise, /gabriel, /pacientes
- Navegação SPA fluida entre chatbot e dashboard
- Cenários A-E do smoke test verdes
"

# Push (se houver remoto)
git push origin main

# Deletar branch local (opcional, após merge)
git branch -d feature/unificacao-dash
```

### 8.11.3 Validação
```bash
git log --oneline -10
# Esperado ver o commit de merge no topo.

# Pytest na main pós-merge
pytest --tb=short 2>&1 | tail -5
```

### 8.11.4 Commit
Já feito (merge commit).

---

## Plano de rollback (se 8.9 falhar e for irrecuperável em curto prazo)

```bash
git checkout main
git branch -D feature/unificacao-dash
# Pronto — main intacto, dois servidores rodam normal pelos Passos 1-7.
```

Você não perde nada: os arquivos `blua_merge_files/app/unified_app.py`, `pages/`, etc. seguem na pasta de templates. Pode tentar novamente em outro sprint.

---

## Checklist final do Passo 8

- [ ] Pré-flight 8.1 verde
- [ ] Branch `feature/unificacao-dash` criada
- [ ] Inventário 8.3 documentado, conflitos resolvidos
- [ ] `pages/monitor.py`, `pages/analise.py`, `pages/gabriel.py` registradas
- [ ] `pages/chat.py` registrada e funcional
- [ ] `pages/pacientes.py` registrada (se feito)
- [ ] `app/unified_app.py` rodando em 8050
- [ ] CSS scopeado, sem conflitos visuais
- [ ] Cenários A, B, C, D, E todos passando
- [ ] `app/dash_app.py` e `dashboard_legacy/` removidos
- [ ] README atualizado
- [ ] Merge para `main` com mensagem descritiva
- [ ] Push para remoto

Quando todos os checks estiverem ✓, Sprint 3 fechado de verdade.

---

## Notas de honestidade

- O `unified_app.py` foi testado em isolado, mas a conversão do `dash_app.py` em `pages/chat.py` (sub-passo 8.5) **não foi testada de ponta a ponta** porque depende da estrutura específica do `dash_app.py` que está no seu repo. As 6 mudanças cirúrgicas listadas em 8.5.3.2 cobrem o padrão típico, mas se o `dash_app.py` tiver algo exótico (ex.: usar `dash.no_update`, `ClientsideFunction`, `Patch()`, multipage hack manual, etc.), pode aparecer surpresa. Por isso o gate forte do 8.9.
- O tempo estimado (60-90min) é otimista. Se o inventário 8.3 acusar mais de 5 conflitos de ID ou se o CSS dos dois projetos colidir em regras globais, pode dobrar.
- **Não há vergonha em rolar back.** Se o Passo 8 não fechar em 2 horas de trabalho, voltar pra dois servidores e seguir vida é uma escolha legítima. A integração funcional (Passos 1-7) é o que entrega valor; a unificação é polimento.
