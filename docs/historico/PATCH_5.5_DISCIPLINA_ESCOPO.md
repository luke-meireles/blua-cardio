# PATCH_5.5_DISCIPLINA_ESCOPO.md

**Pré-requisito:** Passo 5 do `PLANO_MERGE.md` concluído (tools registradas nos agents, `tools_spec.json` atualizado, system prompts inicialmente ajustados). Pytest verde.

**Versão:** 1.0
**Tempo estimado:** 25-40min
**Risco:** baixo (mudanças aditivas, não removem nenhuma funcionalidade)

---

## Por que este patch existe

Auditoria de escopo identificou 4 pontos onde o sistema chega perto de — sem cruzar — a fronteira de "substituir médico / dar diagnóstico". As correções aqui blindam o sistema contra leituras indevidas das suas saídas.

Nada aqui é bloqueante pra funcionalidade. **É blindagem contra mau uso** (alguém compartilhar print fora de contexto, agent prescrição usar lista de medicação não-verificada como se fosse prontuário, LLM gerar texto que soa como diagnóstico).

---

## Sumário das 5 correções

| # | Correção | Arquivo | Tempo |
|---|----------|---------|-------|
| 1 | Disclaimer PPG quando classificação não-regular | `src/tools/ritmo.py` | 5min |
| 2 | Renomear comentário "diagnóstico curto" → "observação curta" | `src/tools/ritmo.py` | 1min |
| 3 | Marcar medicações/alergias como auto-declaradas | `src/tools/criar_perfil.py` | 10min |
| 4 | Disclaimer no preview de criar_perfil | `src/tools/criar_perfil.py` | 3min |
| 5 | Reforçar system prompt do checkup (3 regras) | `src/agents/checkup.py` (e/ou prompt externo) | 10min |

**Bonus opcional 6:** teste pytest de regressão de escopo. ~10min.

---

## Correção 1 — Disclaimer PPG na observação

### 1.1 Objetivo
Garantir que toda saída de `analisar_ritmo_cardiaco` com classificação não-`regular` carregue um disclaimer explícito: PPG não é ECG, isso é estimativa óptica, avaliação médica continua necessária.

### 1.2 Arquivo
`src/tools/ritmo.py`, função `_gerar_observacao` (~linha 140-195).

### 1.3 Diff

Localizar o final da função `_gerar_observacao`, logo antes do `return " ".join(partes)`. A função atualmente termina assim:

```python
    # Linha 4 — recomendação
    if classificacao == "irregular":
        partes.append(
            "Recomenda-se avaliação médica. "
            "Se houver dor torácica, dispneia ou síncope: SAMU 192."
        )
    elif classificacao == "atencao":
        partes.append("Monitoramento contínuo recomendado.")

    return " ".join(partes)
```

Aplicar:

```diff
     # Linha 4 — recomendação
     if classificacao == "irregular":
         partes.append(
             "Recomenda-se avaliação médica. "
             "Se houver dor torácica, dispneia ou síncope: SAMU 192."
         )
     elif classificacao == "atencao":
         partes.append("Monitoramento contínuo recomendado.")

+    # Linha 5 — disclaimer (sempre que não for ritmo regular)
+    if classificacao != "regular":
+        partes.append(
+            "Estimativa baseada em PPG (sensor óptico), não substitui ECG "
+            "nem avaliação clínica presencial."
+        )
+
     return " ".join(partes)
```

### 1.4 Validação
```bash
python -c "
from src.tools.ritmo import analisar_ritmo_cardiaco

# Caso irregular — deve ter disclaimer
r = analisar_ritmo_cardiaco(
    timestamp_s=0, IBI_ms=800, BPM=75,
    media_IBI=800, desvio_medio=200, batimentos_anormais=4
)
obs = r.get('observacao', '')
print('Caso irregular:')
print('  classificacao:', r['classificacao'])
print('  tem disclaimer PPG?', 'PPG' in obs and 'não substitui' in obs)
assert 'PPG' in obs and 'não substitui' in obs, 'Disclaimer faltando em caso irregular'

# Caso regular — disclaimer não precisa aparecer (mas tudo bem se aparecer)
r = analisar_ritmo_cardiaco(
    timestamp_s=0, IBI_ms=800, BPM=75,
    media_IBI=800, desvio_medio=20, batimentos_anormais=0
)
print('Caso regular:')
print('  classificacao:', r['classificacao'])
print('  observacao:', r.get('observacao', '')[:100])
print('OK')
"
```

### 1.5 Critério de parada
- Disclaimer não aparece nas saídas `irregular`/`atencao`: revisar identação do bloco `if` adicionado.
- Algum teste pytest existente quebra porque conferia substring exata da observação: aceitar atualizar o teste, **mas só após confirmar comigo** que ele não estava validando algo importante.

---

## Correção 2 — Renomear comentário interno

### 2.1 Objetivo
Higiene de código. O comentário atual sugere que o autor pensa naquilo como "diagnóstico", o que não é a intenção do sistema.

### 2.2 Arquivo
`src/tools/ritmo.py`, ~linha 157.

### 2.3 Diff

```diff
-    # Linha 1 — diagnóstico curto
+    # Linha 1 — observação curta da variabilidade
     if classificacao == "irregular":
         partes.append(
             f"Variabilidade ALTA: {irr_pct}% dos batimentos na janela "
```

### 2.4 Validação
```bash
grep -n "diagnóstico\|diagnostico" src/tools/ritmo.py
# Esperado: nenhum resultado em comentários (pode aparecer em docstring/descrição em contexto correto)
```

---

## Correção 3 — Marcar medicações/alergias como auto-declaradas

### 3.1 Objetivo
Quando o paciente cadastra medicações via chatbot, gravar essa informação como **auto-declarada e não-verificada**, distinguindo de medicações inseridas via prontuário formal. Isso permite que o agent `prescricao` (que usa `verificar_interacoes_medicamentosas`) saiba quando está operando com dado não-validado e adicione aviso correspondente.

### 3.2 Arquivo
`src/tools/criar_perfil.py`, função `criar_perfil_paciente` (etapas 1 e 2).

### 3.3 Diff

**Mudança 3.A — Etapa 1 (preview):**

Localizar o bloco `if not confirmacao:` e ajustar a estrutura `dados`:

```diff
     # ---- Etapa 1: preview ----
     if not confirmacao:
         return {
             "preview": True,
-            "mensagem": "Confirme os dados antes de criar o perfil:",
+            "mensagem": (
+                "Confirme os dados antes de criar o perfil. "
+                "ATENÇÃO: medicações e alergias serão registradas como "
+                "AUTO-DECLARAÇÃO do paciente (não-verificadas contra "
+                "prontuário médico). Confirme se a lista está exata."
+            ),
             "dados": {
                 "nome": nome.strip(),
                 "idade": idade,
                 "sexo": sexo,
                 "condicoes": [c["nome"] for c in cond_norm],
-                "medicacoes": [m["nome"] for m in med_norm],
-                "alergias": alergias or [],
+                "medicacoes_auto_declaradas": [m["nome"] for m in med_norm],
+                "alergias_auto_declaradas": alergias or [],
             },
             "proxima_acao": (
                 "Após confirmação do usuário, chame esta tool de novo com "
                 "confirmacao=True (mesmos demais argumentos)."
             ),
         }
```

**Mudança 3.B — Etapa 2 (gravação):**

Ajustar a chamada a `create_patient` pra passar a flag:

```diff
     # ---- Etapa 2: gravação ----
     try:
         novo = create_patient(
             nome=nome,
             idade=idade,
             sexo=sexo,
             condicoes=cond_norm,
-            medicacoes=med_norm,
-            alergias=alergias or [],
+            medicacoes=[
+                {**m, "fonte": "auto-declarado-chatbot", "verificado": False}
+                for m in med_norm
+            ],
+            alergias=[
+                {"nome": a, "fonte": "auto-declarado-chatbot", "verificado": False}
+                for a in (alergias or [])
+            ],
         )
     except ValueError as exc:
         return {"erro": str(exc)}
```

**Mudança 3.C — Mensagem de sucesso (Etapa 2):**

```diff
     return {
         "sucesso": True,
         "paciente_id": novo["id"],
         "mensagem": (
             f"Perfil criado para {novo['nome']} (ID {novo['id']}). "
-            f"Disponível agora no CardioMonitor para iniciar sessão de PPG."
+            f"Disponível agora no CardioMonitor. "
+            f"Lembrete: medicações e alergias foram registradas como "
+            f"auto-declaração e devem ser confirmadas com profissional "
+            f"de saúde antes de qualquer uso clínico."
         ),
         "proximos_passos": [
             "Selecione o paciente no dropdown do /monitor",
             "Inicie sessão de simulação ou conecte o ESP32",
             "Os batimentos capturados ficarão automaticamente vinculados "
             f"ao ID {novo['id']}",
+            "Validar medicações auto-declaradas com prescritor responsável",
         ],
         "perfil": novo,
     }
```

### 3.4 Validação

```bash
python -c "
from src.tools.criar_perfil import criar_perfil_paciente

# Preview
r = criar_perfil_paciente(
    nome='Teste Disclaimer', idade=50, sexo='masculino',
    condicoes=['HAS'],
    medicacoes=['Losartana 50mg'],
    alergias=['penicilina'],
    confirmacao=False,
)
assert r['preview']
assert 'AUTO-DECLARAÇÃO' in r['mensagem'], 'Disclaimer faltando no preview'
assert 'medicacoes_auto_declaradas' in r['dados'], 'Chave não-renomeada'
assert 'alergias_auto_declaradas' in r['dados']
print('OK — preview com disclaimer')
print('Mensagem:', r['mensagem'][:120])
"
```

E depois (caso o registry aceite o formato dict-com-fonte):
```bash
python -c "
from src.tools.criar_perfil import criar_perfil_paciente
from shared.patient_registry import get_patient

r = criar_perfil_paciente(
    nome='Teste Gravacao', idade=50, sexo='masculino',
    condicoes=['HAS'], medicacoes=['Losartana 50mg'],
    alergias=['penicilina'], confirmacao=True,
)
if 'erro' in r:
    print('ERRO na gravação:', r['erro'])
    print('Provavelmente o registry não aceita medicações como dict com chaves extras.')
    print('Ver seção 3.5 deste patch.')
else:
    pid = r['paciente_id']
    p = get_patient(pid)
    print('Gravado. ID:', pid)
    print('Medicações:', p.get('medicacoes'))
    # Deve ter fonte e verificado
    if p.get('medicacoes'):
        m0 = p['medicacoes'][0]
        if isinstance(m0, dict):
            assert m0.get('verificado') is False
            assert m0.get('fonte') == 'auto-declarado-chatbot'
            print('OK — flags auto-declarado presentes')
        else:
            print('AVISO — registry achatou para string, ver seção 3.5')
"
```

### 3.5 Critério de parada e ajuste possível

Se a validação retornar erro do registry tipo "ValueError: medicacoes deve ser lista de strings": o `shared/patient_registry.py` atual provavelmente espera `list[str]`, não `list[dict]`. Duas opções:

**Opção 3.5.A (mais limpa, recomendada):** atualizar `shared/patient_registry.py` pra aceitar ambos os formatos (string simples = não-verificada implícita; dict = explícito). Mostrar diff ao usuário antes.

**Opção 3.5.B (mais rápida):** manter `medicacoes: list[str]` no registry e criar um arquivo paralelo `data/mocks/medicacoes_meta.json` com metadados (fonte, verificado) indexado por ID de paciente. Mais código mas não toca o registry.

Recomendação: **3.5.A**, é apenas 5 linhas no registry pra aceitar os dois formatos. Posso te ajudar a redigir esse diff quando chegar lá.

### 3.6 Commit
```
feat(criar_perfil): marca medicações/alergias como auto-declaradas

- Preview do criar_perfil_paciente avisa explicitamente que dados não
  são verificados contra prontuário
- Chaves renomeadas para *_auto_declaradas no retorno
- Gravação inclui campos 'fonte' e 'verificado' em cada item
- Mensagem de sucesso lembra de validar com prescritor

Justificativa: agent prescricao pode futuramente consultar 'verificado'
e adicionar disclaimer próprio quando interagir com medicações não-verificadas.
```

---

## Correção 4 — Disclaimer adicional no preview

Já coberto pela Correção 3, mudança 3.A. Ignorar este número e considerar feito junto com a 3.

---

## Correção 5 — Reforçar system prompt do checkup

### 5.1 Objetivo
Adicionar 3 regras explícitas ao system prompt do agent checkup pra disciplinar a linguagem de saída e o escopo de cadastro.

### 5.2 Onde editar

O Passo 5 já mexeu no system prompt do checkup pra adicionar as novas tools. Esta correção **acrescenta** ao trecho já existente. Localizar:
```bash
grep -rn "system_prompt\|SYSTEM_PROMPT" src/agents/checkup.py
```

E identificar o arquivo de prompt (pode ser string Python no próprio arquivo ou arquivo `.md`/`.txt` separado em pasta tipo `prompts/checkup.md`).

### 5.3 Texto a adicionar

Adicionar uma seção nova ao final do system prompt do checkup (depois de qualquer trecho que adicionamos no Passo 5):

```
## Disciplina de escopo e linguagem clínica

Estas 3 regras são INVIOLÁVEIS:

**Regra 1 — Não use linguagem de diagnóstico.** Ao reportar resultado de
`analisar_ritmo_cardiaco`, NUNCA escreva frases como "você tem arritmia",
"você está com fibrilação atrial", "seu diagnóstico é...", "isso é
taquicardia". A tool retorna classificação de SINAL (regular/atenção/
irregular), não diagnóstico médico. Use SEMPRE linguagem descritiva da
medição:
  - ✅ "A leitura mostrou variabilidade alta no padrão de batimentos."
  - ✅ "Os dados de PPG sugerem que vale uma avaliação médica."
  - ✅ "O sinal indica irregularidade que merece atenção."
  - ❌ "Você está com arritmia."
  - ❌ "Seu diagnóstico é fibrilação atrial."

**Regra 2 — Escopo apenas cardiovascular.** Ao usar `criar_perfil_paciente`,
só registrar condições cardiovasculares ou comorbidades diretamente
relacionadas (hipertensão, fibrilação atrial, insuficiência cardíaca,
DAC, diabetes mellitus, TEP, AVE prévio). Se o usuário mencionar
condições fora do escopo (asma, depressão, problemas ortopédicos, etc.),
explicar com cordialidade que o sistema é focado em cardiovascular e
NÃO registrar esses dados no perfil. Para essas condições, orientar
busca de profissional da especialidade adequada.

**Regra 3 — Disclaimer obrigatório em classificações não-regulares.**
Sempre que `analisar_ritmo_cardiaco` retornar classificação 'atencao'
ou 'irregular', incluir explicitamente na resposta ao usuário (mesmo
que a tool já tenha incluído na observação):
  - Que PPG é estimativa por sensor óptico, não substitui ECG.
  - Que avaliação médica presencial é necessária pra qualquer decisão.
  - Em caso de dor torácica, dispneia ou síncope: SAMU 192.

Nunca tomar decisões em nome do usuário. Nunca sugerir início, parada
ou alteração de medicação — isso é exclusividade do médico prescritor.
```

### 5.4 Validação manual (smoke)

Subir o chatbot e testar:

**Cenário 5.A — Disciplina de linguagem:**
1. Selecionar paciente GABRIEL (que tem condição irregular nos dados).
2. *"Como está meu ritmo agora?"*
3. **Verificar:** resposta NÃO contém "você tem arritmia", "seu diagnóstico", "fibrilação atrial" como afirmação direta sobre o usuário.
4. **Verificar:** resposta MENCIONA PPG, ECG, ou avaliação médica.

**Cenário 5.B — Escopo cardiovascular:**
1. *"Quero cadastrar João, 40 anos, masculino, com depressão e enxaqueca."*
2. **Verificar:** agent explica que sistema é cardiovascular e propõe cadastrar SEM depressão/enxaqueca, ou recusa cordialmente direcionando pra outro profissional.

**Cenário 5.C — Linguagem em caso atenção:**
1. Simular cenário borderline (paciente com poucos irregulares).
2. **Verificar:** resposta contém disclaimer PPG.

### 5.5 Commit
```
feat(checkup): reforça system prompt com 3 regras de disciplina clínica

- Regra 1: linguagem descritiva, não diagnóstica
- Regra 2: escopo cardiovascular only (cadastro)
- Regra 3: disclaimer PPG + rota SAMU em classificações não-regulares
```

### 5.6 Critério de parada
- Se cenário 5.A falhar: o LLM não está respeitando o prompt. Considerar reforçar com exemplos few-shot no prompt (incluir 2-3 pares pergunta→resposta esperada).
- Se cenário 5.B falhar: idem.

---

## Bonus opcional — Teste de regressão de escopo

### B.1 Objetivo
Teste pytest que valida que o sistema não responde a perguntas fora do escopo cardiovascular. Defende contra regressão futura.

### B.2 Arquivo novo
`tests/test_escopo_cardiovascular.py`

### B.3 Conteúdo sugerido

```python
"""
Testes de regressão de escopo.

Garante que o sistema:
1. Mantém recorte cardiovascular.
2. Não usa linguagem diagnóstica.
3. Inclui disclaimers obrigatórios em saídas não-regulares.

Estes testes não validam respostas do LLM (que são não-determinísticas).
Validam apenas saídas determinísticas das tools.
"""
import pytest
from src.tools.ritmo import analisar_ritmo_cardiaco


def test_disclaimer_ppg_em_classificacao_irregular():
    """Toda saída irregular deve mencionar PPG e que não substitui ECG."""
    r = analisar_ritmo_cardiaco(
        timestamp_s=0, IBI_ms=800, BPM=75,
        media_IBI=800, desvio_medio=200, batimentos_anormais=4,
    )
    obs = r.get("observacao", "")
    assert r["classificacao"] == "irregular"
    assert "PPG" in obs, "Disclaimer PPG ausente em caso irregular"
    assert "não substitui" in obs or "não substitui ECG" in obs, \
        "Disclaimer 'não substitui ECG' ausente"


def test_observacao_nao_usa_linguagem_diagnostica():
    """
    Observação gerada não deve afirmar diagnósticos específicos.
    A tool descreve sinal, não diagnostica doença.
    """
    r = analisar_ritmo_cardiaco(
        timestamp_s=0, IBI_ms=800, BPM=75,
        media_IBI=800, desvio_medio=200, batimentos_anormais=4,
    )
    obs = r.get("observacao", "").lower()

    # Frases diagnósticas proibidas
    proibidas = [
        "você tem arritmia",
        "diagnóstico de",
        "você está com fibrilação",
        "você tem fibrilação",
        "confirma fibrilação",
    ]
    for frase in proibidas:
        assert frase not in obs, f"Linguagem diagnóstica detectada: {frase!r}"


def test_classificacao_regular_nao_alarma():
    """Caso regular não deve mencionar SAMU nem urgência."""
    r = analisar_ritmo_cardiaco(
        timestamp_s=0, IBI_ms=800, BPM=75,
        media_IBI=800, desvio_medio=20, batimentos_anormais=0,
    )
    obs = r.get("observacao", "")
    assert r["classificacao"] == "regular"
    assert "SAMU" not in obs, "SAMU mencionado em caso regular (false alarm)"
    assert "192" not in obs


def test_rota_emergencia_em_irregular():
    """Caso irregular deve apontar rota de emergência."""
    r = analisar_ritmo_cardiaco(
        timestamp_s=0, IBI_ms=800, BPM=75,
        media_IBI=800, desvio_medio=200, batimentos_anormais=4,
    )
    obs = r.get("observacao", "")
    assert "SAMU 192" in obs or "192" in obs, \
        "Rota de emergência (SAMU 192) ausente em irregular"
    assert "dor torácica" in obs.lower() or \
           "dispneia" in obs.lower() or \
           "síncope" in obs.lower(), \
        "Sintomas-gatilho de emergência ausentes"
```

### B.4 Validação
```bash
pytest tests/test_escopo_cardiovascular.py -v
# Esperado: 4 testes passando.
```

### B.5 Commit
```
test: adiciona regressão de escopo (disciplina clínica)

4 testes determinísticos sobre saída de analisar_ritmo_cardiaco:
- Disclaimer PPG presente em irregular
- Sem linguagem diagnóstica
- Sem falso alarme em regular
- Rota de emergência presente em irregular
```

---

## Ordem de aplicação recomendada

1. Correção 1 (disclaimer PPG) → validar 1.4 → commit
2. Correção 2 (renomear comentário) → grep 2.4 → commit
3. Correção 3 (medicações auto-declaradas) → validar 3.4 → commit
4. Correção 5 (system prompt) → smoke 5.4 → commit
5. Bonus (testes de regressão) → pytest B.4 → commit

Cada um vira um commit separado. Total: 4-5 commits curtos.

---

## Validação final do patch inteiro

Depois de aplicar tudo:
```bash
# 1. Pytest verde (incluindo os novos testes do bonus)
pytest --tb=short 2>&1 | tail -5

# 2. Grep por sinais de problema
grep -rn "diagnóstico\|diagnostico" src/tools/ src/agents/ --include="*.py"
# Esperado: aparições apenas em strings/docstrings com contexto legítimo
# (ex.: docstring explicando "este NÃO é diagnóstico").

# 3. Smoke do Cenário 5.A do patch
# (manual no chat)
```

Quando os 3 verdes, o patch fechou.

---

## Notas

- **Correção 4 foi fundida na 3** porque eram da mesma área. A numeração 1-2-3-5 sem 4 é proposital pra não te confundir caso encontre referência cruzada.
- **As correções são todas aditivas** — nenhuma remove código existente. Se algo der ruim, é fácil reverter commit por commit.
- **Não tocar em `tools_spec.json` aqui.** As mudanças de spec já foram feitas no Passo 5. Este patch é só ritmo.py + criar_perfil.py + agents/checkup.py (system prompt) + tests novo.
- **A correção 3 pode pedir um ajuste em `shared/patient_registry.py`** caso o registry hoje aceite apenas `list[str]` em medicações. Ver seção 3.5 e me chama antes de editar o registry.

Boa execução.
