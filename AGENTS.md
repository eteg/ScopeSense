# AGENTS.md · Radar de Desvios (Hackathon ETEG 2026)

Guia para qualquer agente de código (Claude Code, Cursor, Codex) que trabalhe neste repositório. Leia inteiro antes de escrever código. Contexto completo: [README.md](README.md) e [docs/PLANO-MVP.md](docs/PLANO-MVP.md).

## 1. O problema

Na ETEG, e em qualquer empresa que compra ou vende projetos, o **desvio só aparece tarde**: a feature entregue fora do escopo, o prazo prometido que estourou, o terceiro trabalhando sem o documento exigido, a promessa feita em reunião que não está no contrato. Ninguém compara **contrato** com **conversa**, e cada área olha só a sua parte.

**O que o Radar faz:** lê o contrato (obrigações por cláusula) e a execução do projeto (Slack, reunião, e-mail, documentos do terceiro), detecta quando algo sai do combinado e avisa **por DM no Slack** a pessoa certa, com **contrato e evidência lado a lado**. Uma pessoa **aprova, descarta ou marca "não é desvio"**. Nada é registrado sem decisão humana.

**Desafio declarado do hackathon:** *Conformidade documental de terceiros*, adaptado ao processo interno da ETEG. O desvio 3 (terceiro sem documento) é a ponte com o desafio e **precisa aparecer na demo**.

## 2. O que estamos construindo hoje (25/11/2026)

Um **MVP em um dia, com 3 devs**: Joe (permissões, dados, ROI, pitch), Ricardo (pipeline, grafo, eval) e Gabriel (ingestão, Slack, telas). As tarefas estão nas issues do GitHub e em `docs/issues/`.

**Meta:** uma mensagem digitada no Slack vira alerta na DM do responsável, com a cláusula e a mensagem lado a lado, e o clique nos botões fica registrado. Os 4 desvios aparecem; as iscas **não** geram alerta; o eval imprime precisão e recall; o Langfuse mostra custo e tempo de cada alerta.

Os 4 desvios: **1** escopo extra (→ gestor) · **2** prazo ou SLA contrariado (→ comercial) · **3** terceiro sem documento (→ administrativo de contratos) · **4** promessa fora do contrato (→ administrativo de contratos).

Como o júri avalia: demo ao vivo que funciona (peso 20), técnicas **rodando** na demo, não só citadas (RAG e graph engineering, peso 25), potencial de negócio com ROI (peso 25), aplicabilidade (15) e time (15). **Vídeo não substitui a demo.**

## 3. Princípios de trabalho (leia com atenção)

1. **Funcional primeiro, rápido, não perfeito.** Entregue a versão mais simples que passa no "Pronto quando" da issue e siga. Sem abstração prematura, sem refatoração, sem testes além do que a issue pede. O dia tem prazo duro: features congeladas às **15:30**, código às **16:30**.
2. **Tem que ser bonito.** A demo é visual (DM no Slack, tela do Streamlit, slides). O funcional não pode parecer protótipo cru. Mas **estética não é tarefa sua agora**: veja a seção 4.
3. **O que não pode faltar:** Slack ao vivo com DM e botões, RAG, grafo com aprovação humana, eval, Langfuse, ROI. Se algo precisa ser cortado, corte de baixo para cima (P2, depois P1). A ordem está em `docs/PLANO-MVP.md`.
4. **Plano B sempre:** o fluxo roda também pelo Streamlit com o Slack desligado, usando o **mesmo** `processar()` e `retomar()`. Nunca crie um segundo caminho.
5. **Dado fictício, sempre.** Só base sintética. Nenhum dado real da ETEG ou de cliente. CPF só via Faker. Nada de nome real de colega ou cliente.

## 4. Design: a Lara cria, nós implementamos depois

A **Lara está criando o design** (visual das telas, da DM e dos slides). **Depois** vamos implementar literalmente a parte estética que ela criou. Por isso, hoje:

- **Não gaste tempo com pixels.** Faça a interface limpa e legível, sem inventar identidade visual.
- **Mantenha a estética isolada em poucos lugares**, para trocar tudo de uma vez quando o design chegar:
  - `radar/ui/tema.py`: tokens (cores, fontes, ícones/emoji por tipo de desvio, rótulos dos botões)
  - `radar/ui/textos.py`: todos os textos exibidos (títulos da DM, mensagens, rótulos)
  - `radar/ui/estilo.css`: CSS do Streamlit, injetado em um só ponto (`st.markdown(..., unsafe_allow_html=True)`)
  - `radar/slack_alertas.py`: **toda** a montagem do Block Kit numa função só (`montar_blocos(alerta, registro)`), sem lógica de negócio
- **Separe lógica de apresentação.** Nenhuma regra de negócio dentro de CSS, Block Kit ou textos. Funções de apresentação recebem dados prontos e devolvem a interface.
- **Não espalhe cores nem textos literais** pelo código. Quando precisar de um, ponha em `tema.py` ou `textos.py`.
- Tom dos textos: **neutro**. "Possível desvio", nunca acusação. O alerta é sobre o contrato, não sobre a pessoa.

## 5. Arquitetura em uma tela

```
Fontes (Slack · reunião .vtt · e-mail .eml · PDF)  ──►  Registro padrão
Registro ──► buscar cláusulas (RAG, ChromaDB, top 3) ──► classificar (LLM, schema Pydantic)
         ──► conferir documentos (código) ──► rotear (regras em código) ──► DM no Slack
         ──► aprovar (interrupt, humano) ──► registrar (decisoes.jsonl)
```

- **Graph engineering:** LangGraph, um nó por arquivo em `radar/nos/`.
- **RAG:** ChromaDB + `intfloat/multilingual-e5-small` (prefixos `passage:` e `query:`).
- **O modelo só devolve JSON.** Quem age é o código. O campo `responsavel` **nunca** é preenchido pelo modelo.
- **Interface de fonte:** tudo implementa `fetch() -> list[Registro]`. O grafo não sabe de onde o registro veio.

## 6. Estrutura e contratos

```
app.py                 Streamlit (fila, simular mensagem)
slack_bot.py           Bolt em Socket Mode (escuta + botões, MESMO processo do grafo)
radar/models.py        schema (CONGELADO)        radar/llm.py       chamada estruturada ao modelo
radar/config.py        modelos e limiares        radar/contrato.py  obrigações + ChromaDB
radar/fontes/          FileSource, parsers       radar/pipeline.py  analisar() (usado pelo eval)
radar/grafo.py         processar/retomar         radar/nos/         um arquivo por nó
radar/roteamento.py    tipo → papel              radar/ui/          tema, textos, css
eval/rodar_eval.py     precisão e recall         data/              contrato, mensagens, gabarito (sintéticos)
```

As assinaturas entre módulos estão na tabela da seção 5 de `docs/PLANO-MVP.md`. **Não as mude sem avisar o time.**

## 7. Regras que não se quebram

- **`radar/models.py` está congelado** depois das 11:55. Mudança só com aviso no canal e OK do Ricardo.
- **Um arquivo por nó do grafo.** Não edite o arquivo de outro dev.
- **`InMemorySaver`:** `processar` e `retomar` rodam no **mesmo processo**. Efeito colateral (DM, gravação do alerta) vai no nó `rotear`, **nunca** antes do `interrupt` no nó `aprovar` (na retomada o nó roda de novo).
- **Slack:** chame `ack()` **primeiro** (limite de 3 s). O bot ignora mensagens de bot, do próprio Radar e com `subtype`. Só lê canais públicos onde foi convidado, **nunca DMs**.
- **Id determinístico** dos registros (`sha1` de origem + texto + data), nunca aleatório: o gabarito do eval depende disso.
- **Citações conferidas em código:** `trecho_contrato` e `trecho_evidencia` precisam existir no texto original; senão a confiança cai para menos de 0,5.
- **Datas** sempre como `date`/`datetime` com fuso `America/Sao_Paulo`, nunca texto. Peça datas em ISO ao modelo.
- **Segredos só no `.env`** (no `.gitignore`). Nunca no Git, nunca no Slack. Chave vazou: revogue na hora.
- **Eval com `MODO_DEMO=0`** (cache desligado). Itere com o Haiku e rode o Sonnet só para o número final.
- Nomes dos modelos **só** em `radar/config.py` (`claude-sonnet-5-5` e `claude-haiku-5-5`).

## 8. Como trabalhar numa issue

1. Pegue uma issue do seu nome cujas dependências estejam prontas. O corpo da issue tem **passo a passo, trechos de código, prompt sugerido e "Pronto quando"**. Siga.
2. Branch com o ID: `git switch -c G-04-obrigacoes`. PR pequeno. A `master` precisa continuar rodando.
3. Entregue o mínimo que satisfaz o "Pronto quando". Marque os itens e mova o card no projeto: 🚧 Em andamento → 🔍 Em revisão → ✅ Pronto.
4. Bloqueado? Mude para ⛔ Bloqueado e comente na issue marcando quem destrava.
5. Guarde prints dos melhores prompts do vibe coding: contam em *Time e experimentação*.

## 9. Comandos (planejados; ajuste conforme o código for entregue)

```bash
py -3.11 -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env              # preencha as chaves
python scripts/ping_modelo.py     # deve responder "ok"
streamlit run app.py              # fila de alertas e simulação
python slack_bot.py               # escuta o canal e trata os botões
python eval/rodar_eval.py         # precisão, recall e alarmes falsos
pytest                            # testes
```

## 10. O que NÃO fazer hoje

Login, banco de dados de verdade (JSON ou SQLite basta), Gmail e Meet pela API, vários projetos ao mesmo tempo, painel executivo, notificação por e-mail, servidor MCP do Radar (só se tudo estiver pronto), refatorações e abstrações que a issue não pede.
