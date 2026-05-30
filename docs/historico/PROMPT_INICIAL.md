# Prompt inicial para o Claude Code Desktop

> Cole o bloco abaixo na primeira mensagem da sessão do Claude Code, dentro do diretório raiz do **projeto novo** `blua-cardio` (com `git init` já executado e com `PLANO_MERGE.md` + `blua_merge_files/` já posicionados na raiz).

---

```
Você é um engenheiro de software sênior e vai me ajudar a criar e construir
um projeto NOVO baseado em dois projetos que já tenho:

1) BluaDiagnostics — chatbot multi-agente em LangGraph (pt-BR) para cardiologia,
   com 10 agents, 7 tools, RAG ChromaDB, UI Dash na porta 8050, 49 testes pytest.

2) cardiac_dashboard_dash — dashboard Dash que lê PPG/BPM ao vivo de um ESP32 +
   MAX30100 e grava em data/cardiac_data.csv. Tem também data/gabriel_data.csv
   como referência (200 batimentos do paciente Gabriel).

IMPORTANTE: apesar de aproveitar código dos dois projetos, este é um projeto
NOVO, em repositório novo, com identidade própria. Nome de trabalho:
`blua-cardio` — se você tiver sugestão melhor, pode propor que eu decido.
NÃO é fork nem branch de nenhum dos dois originais.

O plano completo está em PLANO_MERGE.md na raiz deste repositório novo.
Os arquivos prontos para uso estão em blua_merge_files/.

REGRAS OBRIGATÓRIAS (não negociáveis):

1. Trabalhe UM passo de cada vez, na ordem definida no PLANO_MERGE.md.
2. Antes de cada passo, releia a seção correspondente do PLANO_MERGE.md.
3. NÃO avance para o próximo passo enquanto TODOS os comandos de validação
   do passo atual não passarem.
4. Se uma validação falhar: PARE imediatamente, mostre o output completo
   do erro, e espere instrução minha. NÃO tente "consertar e seguir".
5. Os 49 testes do pytest (vindos do BluaDiagnostics) DEVEM continuar passando
   após cada passo. Backwards compatibility é não-negociável.
6. Todo código novo e comentários em português brasileiro (pt-BR), mantendo
   o estilo do projeto base.
7. Trabalhe direto na branch `main` deste repo novo. Cada passo do plano
   vira um commit atômico em main, com mensagem em pt-BR estilo
   Conventional Commits (feat:, refactor:, chore:, test:, etc.).
8. Antes de modificar QUALQUER arquivo, mostre o diff proposto e peça
   minha confirmação explícita.
9. Antes de criar arquivos novos, confirme o path final comigo se houver
   ambiguidade.
10. Para o Passo 0 (scaffolding), você vai precisar dos caminhos dos dois
    projetos originais extraídos na minha máquina — me pergunte antes
    de copiar nada.

PRIMEIRA AÇÃO:
1. Leia PLANO_MERGE.md inteiro.
2. Confirme que a pasta blua_merge_files/ existe e liste seu conteúdo
   (deve ter shared/, src/tools/, app/, MERGE_GUIDE.md).
3. Execute `git status` e me mostre o resultado (esperado: repo recém-
   inicializado, sem commits ainda).
4. Execute `pwd` para confirmar que estamos no diretório certo.
5. Faça um resumo de 1 parágrafo descrevendo os 8 passos do plano e
   destacando que o Passo 0 vai te pedir os paths origem.
6. Aguarde meu "pode seguir" antes de executar o Passo 0.

Não pule nenhum desses 6 itens iniciais. Não comece o Passo 0 sem confirmação.
```

---

## Como usar este prompt

**Passo a passo do setup (responsabilidade SUA, antes do Claude Code começar):**

1. Crie a pasta do projeto novo e inicialize git:
   ```bash
   mkdir blua-cardio
   cd blua-cardio
   git init
   ```

2. Coloque os arquivos do pacote de download nesta pasta:
   - `PLANO_MERGE.md` → na raiz
   - `PROMPT_INICIAL.md` → na raiz
   - `blua_merge_files/` (com tudo dentro) → na raiz

3. Garanta que os dois projetos originais estão extraídos na sua máquina em algum lugar que você lembre o path (ex.: `~/Downloads/BluaDiagnostics_Sprint-main/` e `~/Downloads/cardiac_dashboard_dash/`). O Claude Code vai te pedir esses paths no Passo 0.

4. Abra o Claude Code Desktop apontando para `blua-cardio/`.

5. Cole o bloco do prompt acima como primeira mensagem.

6. Responda às perguntas do Claude Code conforme o plano avança. Em cada passo: leia o diff proposto, libere quando o pytest passar, próximo.
