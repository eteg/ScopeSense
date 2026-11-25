# Ondas de paralelização · Radar de Desvios (25/11/2026)

Como ler: uma **onda** é o conjunto de issues que ficam liberadas quando a onda anterior termina. **Dentro de uma onda, tudo pode rodar ao mesmo tempo.** O número da onda é a profundidade de dependência, não um horário: o prazo de cada issue continua valendo. Calculado a partir das dependências das 43 issues.

> **Sem dono fixo.** Quem estiver livre pega uma issue da menor onda com dependências prontas, se atribui e move o card para 🚧 Em andamento. As colunas "Sugestão" abaixo mostram só a divisão inicial e **não obrigam ninguém**. No GitHub, cada issue tem a label `onda:N` e o card tem o campo **Onda**.

> **Regra do dia:** não espere uma onda inteira acabar. Assim que as dependências **da sua** issue estiverem prontas, comece. E quando faltar pouco, comece com um *mock* (ver seção 3).

## 1. As ondas

### Onda 1 · sem dependência (10 issues, tudo em paralelo)
| Sugestão | Issues (prazo) |
|------|----------------|
| Joe | **J-03** chave Anthropic (11:45) · **J-01** workspace Slack (11:45) · **J-05** confirmar desafio (11:50) · **J-04** Langfuse (11:55) · **J-06** contrato (12:30) · J-11 premissas ROI (13:00) · J-13 roteiro (14:30) · J-15 conversa júri (14:45, P1) |
| Ricardo | **R-01** `models.py`, config e `llm.py` (12:10) |
| Gabriel | **G-01** estrutura do repo (11:55) · *(G-10 parte A, geração dos PDFs, também já pode começar)* |

Ordem sugerida para o Joe dentro da onda, por prazo: J-03, J-01, J-05, J-04, **J-06**, depois J-11, J-13, J-15 (os três últimos têm prazo folgado).

### Onda 2 · depende só da onda 1 (11 issues)
| Sugestão | Issues (prazo) · de quem depende |
|------|----------------------------------|
| Joe | **J-02** app Slack (12:10) ← J-01 · **J-07** personas JSON (12:20) ← J-01 · **J-08** mensagens (13:15) ← J-06 · **J-09** reunião `.vtt` (13:30) ← J-06 · J-14 slides (16:00) ← J-13 · J-17 e-mails (P2) ← J-06 |
| Ricardo | **R-02** grafo base (12:40) ← R-01 · **R-05** roteamento (13:15) ← R-01 |
| Gabriel | **G-02** `FileSource` (12:25) ← R-01 · **G-04** obrigações (13:05) ← J-06 + R-01 · **G-10** PDFs (14:25) ← J-06 + R-01 |

### Onda 3 · depende da onda 2 (7 issues)
| Sugestão | Issues (prazo) · de quem depende |
|------|----------------------------------|
| Ricardo | **R-04** aprovação humana (13:50) ← R-02 · **R-06** Langfuse (14:15) ← J-04 + R-02 |
| Gabriel | **G-03** parser Slack + gabarito base (12:55) ← G-02 + J-07 + J-08 · **G-05** ChromaDB (13:30) ← G-04 · **G-09** parser `.vtt` (13:40) ← G-02 + J-09 · **G-07** DM Block Kit (14:25) ← R-05 + J-02 · G-14 e-mail (P2) |

### Onda 4 · depende da onda 3 (6 issues)
| Sugestão | Issues (prazo) · de quem depende |
|------|----------------------------------|
| Joe | **J-10** gabarito rotulado (14:15) ← G-03 + J-08 + J-09 · **J-12** planilha de ROI (15:30) ← J-11 + R-06 |
| Ricardo | **R-03** classificar com RAG (13:40) ← R-02 + G-05 |
| Gabriel | **G-06** Slack ao vivo (13:55) ← J-02 + G-03 + R-02 · **G-08** botões (14:55) ← G-07 + R-04 · G-11 Streamlit (15:15, P1) ← R-04 |

### Onda 5 · depende da onda 4 (6 issues)
| Sugestão | Issues (prazo) · de quem depende |
|------|----------------------------------|
| Ricardo | **R-07** conferência de documentos (14:45) ← R-03 + G-10 · **R-08** eval (15:15) ← R-03 + J-10 · R-09 anti-injeção (15:00, P1) · R-11 triagem Haiku (P2) |
| Gabriel | G-12 cache da demo (15:30, P1) ← R-03 · G-15 cartão de impacto (P2) |

### Onda 6, 7 e 8 · fechamento (3 issues, em fila)
| Onda | Issue | Sugestão | Depende de |
|------|-------|------|-----------|
| 6 | **R-10** slides técnicos e links do GitHub (16:15) | Ricardo | R-08 + R-06 |
| 7 | **G-13** diagrama e README de evidências (16:20) | Gabriel | R-02 + R-10 |
| 8 | **J-16** dois ensaios cronometrados (16:30) | Joe | todas as P0 |

## 2. Caminho crítico (o que, se atrasar, atrasa o dia)

```
R-01 ─► G-02 ─► G-03 ─► G-06 ─┐
  │                           ├─► G-07 ─► G-08 ─► demo ao vivo
  ├─► G-04 ─► G-05 ─► R-03 ───┤
  └─► R-02 ─► R-04 ───────────┘
J-06 ─► G-04, G-10, J-08 ─► G-03, J-10 ─► R-08 ─► R-10 ─► G-13
```

Os três nós que **mais seguram os outros**: **R-01** (12:10), **J-06** (12:30) e **G-04 → G-05 → R-03** (13:40). Quem estiver livre deve ajudar esses antes de pegar P1 ou P2.

## 3. Como não esperar: comece com um *mock*

Muitas issues da onda N podem começar enquanto a onda N−1 ainda fecha:

| Issue | Pode começar antes de… | Com este mock |
|-------|------------------------|---------------|
| R-03 classificar | G-05 (ChromaDB) | `buscar()` falsa que devolve a cláusula 2.2 fixa |
| G-02 `FileSource` | R-01 | classes `Registro` temporárias, trocadas pelas reais depois |
| G-03 parser Slack | J-08 completo | as ~10 mensagens parciais que o Joe entrega às 12:30 |
| G-05 ChromaDB | G-04 | indexar o **texto bruto** de cada cláusula, sem esperar as obrigações |
| G-06 Slack ao vivo | R-02 | notificador que só imprime; comece pelo teste "ping → pong" |
| G-07 DM Block Kit | R-05 | 4 alertas de exemplo escritos à mão, sem chamar o modelo |
| G-08 botões | R-04 | `retomar()` falsa que só devolve `Decisao` |
| R-04 aprovação | R-02 completo | nós de teste com valores fixos |
| R-07 conferência | G-10 | lista falsa de `DocumentoExtraido` (ASO do João vencido) |
| R-08 eval | J-10 | gabarito parcial; rode já nos 4 desvios conhecidos |
| J-12 planilha ROI | J-11 e R-06 | números de exemplo do plano e custo estimado do modelo |
| J-14 slides | J-13 | esqueleto dos 8 slides com espaços para prints |
| G-13 diagrama | R-10 | `docs/grafo.mmd` já exportado pelo R-02 |

## 4. Sugestão de fila por pessoa (opcional; ninguém tem dono fixo)

**Joe:** J-03 → J-01 → J-05 → J-04 → **J-06** → J-02 → J-07 → **J-08** → J-09 → J-11 → J-10 → J-13 → J-12 → J-14 → J-15 → J-16.

**Ricardo:** **R-01** → R-02 → R-05 → R-04 → **R-03** → R-06 → R-07 → R-08 → R-09 → R-10. *(Enquanto espera o G-05, adiante o prompt do R-03 com `buscar()` falsa.)*

**Gabriel:** **G-01** → G-10 parte A *(enquanto o R-01 não sai)* → G-02 → **G-04** → G-03 → **G-05** → G-09 → G-06 → G-07 → G-08 → G-10 parte B → G-13 → G-11 → G-12.

## 5. Se for usar agentes em paralelo (Claude Code)

Vale delegar o que é **autocontido** e tem "Pronto quando" claro; cada agente em uma **cópia isolada do repositório (worktree)** e mexendo **só nos arquivos da sua issue**, para não haver conflito:

| Onda | Bons candidatos a agente | Fique com você |
|------|--------------------------|----------------|
| 1 | G-01, G-10 parte A, rascunhos de J-06 | R-01 (schema: todo mundo depende) |
| 2 | G-02, G-04, R-05, R-02, rascunhos de J-07, J-08, J-09 | revisar contrato e schema |
| 3 | G-03, G-05, G-09, R-04, R-06 | G-07 (a tela do momento uau) |
| 4 | G-11, G-06 | R-03 (o coração: o prompt exige iteração com o eval) |
| 5 | R-09, G-12 | R-07 e R-08 (decisões de qualidade) |

Cada agente gasta a **cota da conta em que roda**. Vários ao mesmo tempo gastam bem mais que um só; mantenha no máximo 3 a 4 ao mesmo tempo. Revise tudo antes do `push`. Segredos só no `.env`.

## 6. Resumo em uma linha por onda

1. **Onda 1:** abrir as contas e chaves, criar o contrato, o schema e o repositório.
2. **Onda 2:** app Slack, dados, grafo base, `FileSource`, obrigações e PDFs.
3. **Onda 3:** aprovação humana, Langfuse, parsers, ChromaDB e a DM.
4. **Onda 4:** classificação com RAG, Slack ao vivo, botões e gabarito.
5. **Onda 5:** documentos do terceiro, eval, anti-injeção e cache.
6. **Ondas 6 a 8:** slides técnicos, diagrama, README de evidências e ensaios.
