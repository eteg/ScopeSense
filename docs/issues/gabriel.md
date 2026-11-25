<!-- issue
id: G-01
title: Estrutura do repositório, dependências e acesso do time
dev: gabriel
prio: P0
frente: setup
est: 20 min
prazo: 11:55
depende: nada
-->
## 🎯 Objetivo
Um lugar único onde os 3 trabalham **sem se atropelar**. **Todo mundo espera esta issue**, então faça primeiro e **avise no canal** quando estiver no ar.

## 🪜 Passo a passo
1. **Dê acesso ao time:** no GitHub, *Settings → Collaborators → Add people* (você é o dono do repositório): **Joe** e **Ricardo**, com permissão de escrita.
2. Confira o **Python 3.11** (`py -3.11 --version`). Todos usam a mesma versão. Crie o ambiente:
   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Crie a estrutura de pastas com `__init__.py` vazios onde for pacote:
   ```
   radar/  radar/fontes/  radar/nos/  eval/  eval/resultados/  data/  data/cache/  data/documentos/  scripts/  tests/  docs/
   ```
4. **`requirements.txt`:**
   ```
   langgraph
   anthropic
   pydantic
   chromadb
   sentence-transformers
   slack-bolt
   slack-sdk
   pymupdf
   langfuse
   streamlit
   faker
   python-dotenv
   tzdata
   pytest
   ```
   (`tzdata` é necessário para fuso horário no Windows. Presidio e faster-whisper ficam fora do MVP.)
5. **`.gitignore`:** `.env`, `.venv/`, `chroma/`, `data/cache/`, `__pycache__/`, `*.pyc`, `eval/resultados/*.json`.
6. **`.env.example`:**
   ```
   ANTHROPIC_API_KEY=
   LANGFUSE_PUBLIC_KEY=
   LANGFUSE_SECRET_KEY=
   LANGFUSE_HOST=https://cloud.langfuse.com
   SLACK_BOT_TOKEN=
   SLACK_APP_TOKEN=
   MODO_DEMO=0
   ```
7. **`app.py` mínimo** (Streamlit só com o título "Radar de Desvios").
8. Faça `pip install -r requirements.txt`. **Já deixe o modelo de embeddings baixando** (o Wi-Fi do evento pode ser lento):
   ```powershell
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
   ```
9. Atualize o README (já está na `master`) se algo do passo a passo mudar, faça commit e push na `master`. **Avise no canal.**

## 🤖 Prompt sugerido
```
Crie a estrutura de um projeto Python 3.11 chamado radar-desvios com as pastas radar/,
radar/fontes/, radar/nos/, eval/, data/, scripts/ e tests/. Inclua um app.py em Streamlit
que mostra só o título "Radar de Desvios", um requirements.txt com langgraph, anthropic,
pydantic, chromadb, sentence-transformers, slack-bolt, slack-sdk, pymupdf, langfuse,
streamlit, faker, python-dotenv, tzdata e pytest, um .gitignore para .env, .venv, chroma/
e data/cache/, e um .env.example.
```

## ✅ Pronto quando
- [ ] Joe e Ricardo conseguem fazer `git clone` e `git push`
- [ ] Todos clonam, instalam e abrem o Streamlit com o título
- [ ] `.gitignore` está no primeiro commit (o `.env` **nunca** vai para o Git)
- [ ] O modelo de embeddings já está baixado na sua máquina

## ⚠️ Armadilhas
- Duas pessoas editando o mesmo arquivo: por isso **um arquivo por nó** do grafo.
- `chromadb` ou `sentence-transformers` falhando na instalação no Windows: avise o Ricardo logo (plano B: guardar embeddings em `numpy` e fazer busca por cosseno).
<!-- /issue -->

<!-- issue
id: G-02
title: Interface de fonte (fetch) e leitura de arquivos (FileSource)
dev: gabriel
prio: P0
frente: ingestao
est: 30 min
prazo: 12:25
depende: R-01
-->
## 🎯 Objetivo
O pipeline recebe **registros sem saber de onde vieram**. Se um conector falhar no pitch, troca-se para arquivos sem mexer no resto. Também é a **aposta de arquitetura** do slide de roadmap (fonte trocável: Gmail e Meet entram depois).

## 🪜 Passo a passo
1. `radar/fontes/base.py`:
   ```python
   from datetime import datetime
   from typing import Protocol
   from radar.models import Registro

   class Fonte(Protocol):
       def fetch(self, desde: datetime | None = None) -> list[Registro]: ...
   ```
2. `radar/fontes/arquivos.py` com **`FileSource(pasta)`**: percorre a pasta e escolhe o parser **pela extensão**:
   - `slack_export.json` → parser do G-03
   - `*.vtt` → parser do G-09
   - `emails/*.eml` → parser do G-14 (P2; começa vazio)
   - `documentos/*.pdf` → parser do G-10
   - **ignore** `contrato_alfa.md`, `projeto_alfa.json`, `gabarito.json` e `cache/`.
   No começo, os parsers podem devolver lista vazia; registre-os num dicionário para os outros plugarem.
3. **Ordene os registros por data** (`sorted(..., key=lambda r: r.data)`).
4. **Id determinístico:** `id = f"{origem}:{sha1(origem + texto + data.isoformat()).hexdigest()[:12]}"`. **Nunca** `uuid4`/aleatório: um id aleatório **quebra o gabarito do eval**.
5. **Fuso:** use sempre o mesmo (`zoneinfo.ZoneInfo("America/Sao_Paulo")`), senão a ordem se mistura.
6. **`contexto_de(registros, registro, n=3)`:** devolve até `n` registros **anteriores** do mesmo `canal` (e da mesma `thread_id`, se houver). É o contexto que o classificador (R-03) usa e que o eval também precisa.
7. Teste: `FileSource("data").fetch()` devolve registros ordenados; rodar duas vezes gera **os mesmos ids**.

## 🤖 Prompt sugerido
```
Crie radar/fontes/base.py com um Protocol Fonte que tem fetch(desde: datetime | None) ->
list[Registro]. Crie radar/fontes/arquivos.py com FileSource(pasta), que percorre a pasta
e chama um parser por extensão (.json do Slack, .vtt, .eml, .pdf), com parsers vazios por
enquanto, registrados num dicionário. O id de cada Registro é origem + ":" + sha1 do
texto e da data (determinístico). Devolva a lista ordenada por data, com fuso America/
Sao_Paulo. Adicione contexto_de(registros, registro, n=3) que devolve os n registros
anteriores do mesmo canal/thread.
```

## ✅ Pronto quando
- [ ] `FileSource("data").fetch()` devolve registros ordenados
- [ ] Rodar duas vezes gera os **mesmos ids**
- [ ] `contexto_de` devolve as 3 mensagens anteriores da thread/canal
- [ ] Teste `pytest` cobrindo ids estáveis e ordenação

## ⚠️ Armadilhas
- **Id aleatório quebra o gabarito.** Datas sem fuso misturam a ordem.
- Esquecer `tzdata` no Windows: `ZoneInfo` falha.
<!-- /issue -->

<!-- issue
id: G-03
title: Parser do export do Slack e script que gera o gabarito base
dev: gabriel
prio: P0
frente: ingestao
est: 30 min
prazo: 12:55
depende: G-02, J-07, J-08
-->
## 🎯 Objetivo
Transformar **cada mensagem do Slack em um `Registro`**. A mesma função de conversão será usada pela escuta ao vivo (G-06), para as duas versões **não divergirem**. Entrega também o **script do gabarito base** que o Joe precisa (J-10).

## 🪜 Passo a passo
1. `radar/fontes/slack_export.py` com **`mensagem_para_registro(msg: dict, pessoas: dict, canais: dict | None) -> Registro`**:
   - **Data:** converta `ts` (segundos desde 1970, com decimais) em `datetime` com fuso.
   - **Autor:** troque o ID pelo **nome** usando `data/projeto_alfa.json` (`papeis[...].slack_id` e `pessoas_sinteticas`). ID desconhecido: mantenha o ID.
   - **Menções:** troque `<@U123>` pelo nome.
   - **Guarde `thread_ts`** em `thread_id` e o nome do canal em `canal` (o classificador precisa buscar as mensagens anteriores da thread).
   - **Link:** `slack://canal/ts` (no export); no ao vivo, o G-06 troca pelo permalink real.
2. `ler_export(caminho) -> list[Registro]`: **ignore** mensagens de bot (`bot_id`), `subtype` (entrada no canal, edição) e vazias.
3. Registre em `FileSource` (G-02) para `slack_export.json`.
4. **`scripts/gerar_gabarito_base.py`:** lê os registros via `FileSource` e escreve `data/gabarito.json` **pré-preenchido** com todos os ids:
   ```json
   {"registro_id": "slack:ab12...", "e_desvio": false, "tipo": "nenhum", "responsavel": null, "clausula": null, "nota": ""}
   ```
   O Joe só vira para `true` os desvios e anota as iscas (J-10). **Avise-o assim que o script rodar.**
5. Teste com as ~10 mensagens parciais que o Joe entrega às 12:30 e depois com o arquivo completo.

## 🤖 Prompt sugerido
```
Em radar/fontes/slack_export.py escreva mensagem_para_registro(msg, pessoas, canais) ->
Registro, que converte uma mensagem do export do Slack (ts, user, text, thread_ts,
channel) em Registro (models.py abaixo): data a partir do ts com fuso America/Sao_Paulo,
autor pelo dicionário pessoas (data/projeto_alfa.json), menções <@ID> trocadas por nomes,
thread_id = thread_ts, canal = nome do canal, link slack://canal/ts. Depois escreva
ler_export(caminho) que ignora mensagens com bot_id ou subtype e devolve a lista.
Crie também scripts/gerar_gabarito_base.py que gera data/gabarito.json com todos os ids
e e_desvio false.
```

## ✅ Pronto quando
- [ ] As 22 a 25 mensagens viram registros com **nome do autor e data certa**
- [ ] Mensagens com `thread_ts` carregam `thread_id`
- [ ] `scripts/gerar_gabarito_base.py` roda e o **Joe foi avisado**
- [ ] Teste `pytest` da conversão (ts → data, menção → nome)

## ⚠️ Armadilhas
- **Duplicar a conversão no G-06 faz as duas versões divergirem.** Reaproveite a função.
- `ts` é string com decimal (`"1768827600.000100"`): converta com `float`.
<!-- /issue -->

<!-- issue
id: G-04
title: Extrair as obrigações do contrato (uma cláusula por chamada)
dev: gabriel
prio: P0
frente: ingestao
est: 45 min
prazo: 13:05
depende: J-06, R-01
-->
## 🎯 Objetivo
Transformar o contrato em uma **lista de obrigações, cada uma com o número da cláusula**. É a primeira etapa do Radar ("lê o contrato e transforma as obrigações em lista estruturada").

## 🪜 Passo a passo
1. `radar/contrato.py` → **`dividir_clausulas(texto_md) -> list[dict]`**. O contrato (J-06) usa títulos `### N Título` / `### N.N Título`:
   ```python
   import re
   PADRAO = re.compile(r"^###\s+(\d+(?:\.\d+)?)\s+(.*)$", re.M)
   ```
   Cada cláusula = título + corpo até o próximo título: `{"numero": "2.2", "titulo": "...", "texto": "..."}`.
2. **`extrair_obrigacoes(clausulas) -> list[Obrigacao]`:** para **cada cláusula**, chame o Sonnet com saída estruturada (`chamar_estruturado`, do R-01) usando `ListaObrigacoes` como schema. **Uma cláusula por chamada** é mais barato e mais fácil de conferir que mandar o contrato inteiro (saída longa, cara e com mais erro).
3. **O número da cláusula é preenchido pelo código, nunca pelo modelo** (`obrigacao.clausula = clausula["numero"]`).
4. Valide com Pydantic (o `llm.py` já tenta de novo até 2 vezes).
5. **Cache em disco:** salve em `data/cache/obrigacoes.json`. Na segunda execução, **leia do cache e não chame o modelo**.
6. **Plano B (não bloqueie o G-05):** se a API falhar, gere uma `Obrigacao` por cláusula com o texto bruto e `tipo="outro"`. O RAG usa o **texto da cláusula**, então o G-05 pode começar antes de esta issue terminar.
7. Teste: cláusulas `2.2`, `3`, `5`, `6.1`–`6.4` e `7` viram pelo menos 1 obrigação cada, com o número certo.

## 🤖 Prompt sugerido
```
Em radar/contrato.py escreva dividir_clausulas(texto_md) que separa o contrato pelos
títulos "### N Título" ou "### N.N Título" (regex), e extrair_obrigacoes(clausulas) que,
para cada cláusula, chama chamar_estruturado (radar/llm.py) com MODELO_PRINCIPAL e o schema
ListaObrigacoes (models.py abaixo). O campo clausula é preenchido pelo código. Guarde o
resultado em data/cache/obrigacoes.json e leia do cache quando o arquivo existir.
```

## ✅ Pronto quando
- [ ] Todas as cláusulas de `2` a `7` viram **pelo menos uma obrigação**, com o **número certo**
- [ ] A **segunda execução lê do cache** e não chama o modelo
- [ ] Teste `pytest` de `dividir_clausulas` com o contrato real

## ⚠️ Armadilhas
- Mandar o contrato inteiro numa chamada gera saída longa, cara e com mais erro.
- Se o J-06 mudar o formato dos títulos, a regex quebra: combine com o Joe (formato `### N Título`).
<!-- /issue -->

<!-- issue
id: G-05
title: Índice das cláusulas no ChromaDB (a técnica RAG)
dev: gabriel
prio: P0
frente: ingestao
est: 30 min
prazo: 13:30
depende: G-04
-->
## 🎯 Objetivo
Dada uma mensagem, achar as **3 cláusulas mais parecidas**. É a técnica **RAG** da demo (peso 25 em Desafios técnicos). **O Ricardo (R-03) espera isto**, então publique cedo a função `buscar`, mesmo que com poucas cláusulas.

## 🪜 Passo a passo
1. Em `radar/contrato.py`:
   ```python
   import chromadb
   from chromadb.utils import embedding_functions

   ef = embedding_functions.SentenceTransformerEmbeddingFunction(
       model_name="intfloat/multilingual-e5-small")
   cliente = chromadb.PersistentClient(path="chroma")
   colecao = cliente.get_or_create_collection("clausulas_alfa", embedding_function=ef)
   ```
2. **`indexar_clausulas(clausulas)`:** adicione o texto de **cada cláusula** com o prefixo **`passage: `** e os metadados `numero` e `tipo`.
3. **`buscar(texto, k=3) -> list[dict]`:** consulta com o prefixo **`query: `** e devolve `[{"numero", "texto", "tipo", "distancia"}]`.
4. **Os modelos e5 foram treinados com esses prefixos.** Sem eles a busca piora.
5. O modelo **corta textos acima de 512 tokens**: se uma cláusula for muito longa, divida-a (por parágrafo).
6. Reindexe do zero a cada execução do script de preparação (`chroma/` está no `.gitignore`), usando `get_or_create_collection` e `delete_collection` antes, para não duplicar.
7. Testes de aceitação:
   - `buscar("módulo de relatórios")` traz a **cláusula 2.2** entre as 3
   - `buscar("o João começa amanhã")` traz uma **cláusula 6.x** entre as 3
   - `buscar("entrega remarcada para depois do prazo")` traz a **cláusula 3**
8. Avise o Ricardo no canal quando `buscar` estiver pronta.

## 🤖 Prompt sugerido
```
Em radar/contrato.py crie indexar_clausulas(clausulas) e buscar(texto, k=3) usando
chromadb.PersistentClient(path="chroma") e SentenceTransformerEmbeddingFunction com o
modelo intfloat/multilingual-e5-small. Indexe cada cláusula com o prefixo "passage: " e os
metadados numero e tipo; consulte com o prefixo "query: ". buscar devolve numero, texto,
tipo e distancia de cada cláusula. Inclua testes que buscam "módulo de relatórios" e
esperam a cláusula 2.2 entre os resultados.
```

## ✅ Pronto quando
- [ ] `buscar("módulo de relatórios")` traz a 2.2 entre as 3
- [ ] `buscar("o João começa amanhã")` traz uma cláusula 6 entre as 3
- [ ] Ricardo avisado e usando `buscar` no R-03

## ⚠️ Armadilhas
- **Sem os prefixos `query:`/`passage:` a qualidade cai.**
- Primeira execução baixa o modelo (~120 MB): já deixe baixado (G-01).
- Collection duplicada ao rodar duas vezes: apague e recrie.
<!-- /issue -->

<!-- issue
id: G-06
title: Slack ao vivo: escutar o canal e disparar o pipeline sozinho
dev: gabriel
prio: P0
frente: slack
est: 45 min
prazo: 13:55
depende: J-02, G-03, R-02
-->
## 🎯 Objetivo
A mensagem **digitada ao vivo** dispara o pipeline sozinha. É o coração do **momento uau** (peso 20 em Protótipo funcional, que exige **fluxo de ponta a ponta ao vivo, sem corte**).

## 🪜 Passo a passo
1. **Teste de vida primeiro (10 min):** `slack_bot.py` com Bolt em Socket Mode respondendo `pong` a `ping` na thread. Se funcionar, o app do Joe (J-02) está certo.
   ```python
   import os
   from dotenv import load_dotenv
   from slack_bolt import App
   from slack_bolt.adapter.socket_mode import SocketModeHandler

   load_dotenv()
   app = App(token=os.environ["SLACK_BOT_TOKEN"])

   @app.event("message")
   def ao_receber(event, client, logger): ...

   if __name__ == "__main__":
       SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
   ```
2. **No handler `message`:**
   - **Ignore** mensagens de bot, **do próprio Radar** e com `subtype` (edição, entrada no canal). **Se o bot processar as próprias mensagens, entra em loop.**
   - **Deduplicar** pelo `ts` (guarde os já vistos): o Slack pode reentregar o evento.
   - Converta com `mensagem_para_registro` (**a mesma função do G-03**).
   - Busque o **permalink** com `client.chat_getPermalink(channel=..., message_ts=...)` (em `try/except`) e preencha `registro.link`.
   - Monte o **contexto** (3 mensagens anteriores): se tiver `thread_ts`, use `conversations_replies`; senão, `conversations_history(limit=4)`.
   - **Rode `processar(registro, contexto)` em segundo plano** (`threading.Thread`) para o handler responder rápido.
3. **`SlackSource.fetch()`:** com o `WebClient`, leia o histórico dos canais com `conversations_history` a partir da data pedida (só para carregar o passado). **Não chame o histórico a cada mensagem nova:** estoura o limite de chamadas. O tempo real vem pelo **evento**.
4. **Injete o notificador** do R-02: `grafo.configurar(notificador=lambda alerta, registro: enviar_alerta(app.client, alerta, registro, usuario_id_do_papel(alerta.responsavel)))` (a função `enviar_alerta` é o G-07; enquanto não existe, deixe o notificador imprimir).
5. **`usuario_id_do_papel`:** lê `data/projeto_alfa.json → papeis[papel].slack_id`.
6. **Este processo hospeda também os botões** (G-08): o `InMemorySaver` precisa que `processar` e `retomar` rodem **no mesmo processo**.
7. Teste: digite no `#projeto-alfa` e veja o registro e o alerta no terminal em segundos.

## 🤖 Prompt sugerido
```
Crie slack_bot.py com slack-bolt em Socket Mode lendo SLACK_BOT_TOKEN e SLACK_APP_TOKEN do
.env. No handler app.event("message"): ignore mensagens com bot_id, do próprio bot e com
subtype; deduplique pelo ts; converta com mensagem_para_registro (radar/fontes/
slack_export.py); busque o permalink com chat_getPermalink; monte o contexto com
conversations_replies ou conversations_history; e rode radar.grafo.processar(registro,
contexto) em uma threading.Thread. Configure o notificador com grafo.configurar.
```

## ✅ Pronto quando
- [ ] "ping" no `#projeto-alfa` recebe "pong" (teste de vida)
- [ ] Uma mensagem digitada no `#projeto-alfa` vira registro e dispara o grafo **sozinha, em segundos**
- [ ] O bot **não** processa as próprias mensagens (sem loop)
- [ ] O mesmo evento recebido duas vezes não processa duas vezes

## ⚠️ Armadilhas
- Chamar o histórico a cada mensagem estoura o limite. Use o **evento**.
- Mensagem **editada** chega com outro formato e deve ser **ignorada**.
- O bot só recebe mensagens dos canais para onde foi convidado.
<!-- /issue -->

<!-- issue
id: G-07
title: DM com Block Kit: contrato e evidência lado a lado
dev: gabriel
prio: P0
frente: slack
est: 45 min
prazo: 14:25
depende: R-05, J-02
-->
## 🎯 Objetivo
O alerta chega **à pessoa certa**, com **contrato e evidência lado a lado**. **É a tela do momento uau.**

## 🪜 Passo a passo
1. `radar/slack_alertas.py` → **`enviar_alerta(client, alerta, registro, usuario_id)`**.
2. Abra a DM com `client.conversations_open(users=[usuario_id])` e use `channel["id"]`.
3. Monte a mensagem em **Block Kit**:
   - **`header`** com o tipo do desvio **em português e tom neutro**: *"Possível desvio de escopo"*, *"Possível prazo contrariado"*, *"Possível terceiro sem documento"*, *"Possível promessa fora do contrato"*. **Não coloque o nome de quem escreveu no título**: soaria como acusação.
   - **`section` com 2 `fields`**: à esquerda `*Cláusula {N}*\n{trecho_contrato}`; à direita `*Evidência* ({autor}, {data})\n{trecho_evidencia}`. **Corte cada trecho em ~300 caracteres** (limites do Block Kit).
   - **`context`** com a **confiança** (`Confiança: 92%`), a **origem** (Slack/reunião/documento) e o **link da mensagem original** (só se começar com `http`).
   - **`actions`** com **3 botões**: `Aprovar` (`action_id="aprovar"`, estilo `primary`), `Descartar` (`action_id="descartar"`), `Não é desvio` (`action_id="nao_e_desvio"`). **`value` = `alerta.registro_id`.**
4. **Preencha o `text` de fallback**: é o que aparece na **notificação do celular** (ex.: *"Possível desvio de escopo · cláusula 2.2"*).
5. Mapeamento **tipo → título** num dicionário (um lugar só).
6. Teste com os 4 tipos de alerta de exemplo (sem o modelo): a DM chega no usuário do papel.

## 🤖 Prompt sugerido
```
Em radar/slack_alertas.py escreva enviar_alerta(client, alerta, registro, usuario_id) com
o slack-sdk. Abra a DM com conversations_open e envie uma mensagem em Block Kit com:
header com o tipo do desvio em português ("Possível desvio de escopo"); section com dois
fields (Cláusula N: trecho_contrato, e Evidência de autor em data: trecho_evidencia), cada
trecho cortado em 300 caracteres; context com a confiança e o link da mensagem original;
actions com três botões (Aprovar action_id=aprovar, Descartar action_id=descartar, Não é
desvio action_id=nao_e_desvio) cujo value é alerta.registro_id. Preencha o text de fallback.
```

## ✅ Pronto quando
- [ ] A DM chega ao usuário do **papel certo** com as duas citações e o link funcionando
- [ ] A notificação do celular mostra o tipo do desvio
- [ ] Trechos longos não estouram o Block Kit
- [ ] O título **não** nomeia a pessoa

## ⚠️ Armadilhas
- Trechos longos estouram os limites do Block Kit: corte em ~300.
- Sem `im:write` não abre DM (J-02). **Se mudou os scopes, reinstale o app.**
<!-- /issue -->

<!-- issue
id: G-08
title: Botões Aprovar / Descartar / Não é desvio ligados à pausa do grafo
dev: gabriel
prio: P0
frente: slack
est: 45 min
prazo: 14:55
depende: G-07, R-04
-->
## 🎯 Objetivo
O clique no Slack **retoma o grafo e registra a decisão**. É o critério **human-in-the-loop** ao vivo.

## 🪜 Passo a passo
1. No `slack_bot.py` (**mesmo processo** do G-06), um handler para cada botão:
   ```python
   @app.action("aprovar")
   def ao_aprovar(ack, body, client):
       ack()                                  # IMEDIATAMENTE: o Slack exige em até 3 s
       tratar(body, client, "aprovar")
   # idem para "descartar" e "nao_e_desvio"
   ```
2. **O `ack()` vem primeiro.** Chamar o modelo ou o grafo antes dele faz aparecer **erro na tela, na frente do júri**.
3. Em `tratar`: pegue `registro_id = body["actions"][0]["value"]`, `quem = body["user"]["name"]` (ou `real_name` via `users_info`) e crie `Decisao(alerta_id=registro_id, acao=acao, quem=quem, quando=datetime.now())`.
4. Chame **`retomar(registro_id, decisao)`** (R-04). Se devolver `None`, o alerta **já foi decidido**: **não** grave de novo.
5. **Atualize a mensagem** com `client.chat_update(channel=body["channel"]["id"], ts=body["message"]["ts"], blocks=..., text=...)`, **trocando os botões** por uma linha de contexto: *"✅ Aprovado por Joe às 14:32"*, *"🗑️ Descartado por ..."* ou *"🚫 Marcado como não é desvio por ..."*.
6. **Trave o segundo clique:** se `retomar` devolveu `None`, apenas atualize a mensagem (ou ignore), sem gravar outra decisão.
7. Teste ponta a ponta: digite a frase do momento uau → DM → clique em **Aprovar** → o `data/decisoes.jsonl` ganha **uma** linha; clique de novo e **nada** novo é gravado.

## 🤖 Prompt sugerido
```
No slack_bot.py (slack-bolt) crie handlers app.action para aprovar, descartar e
nao_e_desvio. Em cada um chame ack() imediatamente; depois monte a Decisao (models.py)
com alerta_id = value do botão, quem = nome do usuário e quando = agora, chame
radar.grafo.retomar(registro_id, decisao) e, se não devolver None, atualize a mensagem
com chat_update trocando os botões por um context com "Aprovado por <nome> às HH:MM".
```

## ✅ Pronto quando
- [ ] O clique **grava a decisão** e a mensagem mostra **quem decidiu e quando**
- [ ] Um **segundo clique não grava** outra decisão
- [ ] Nenhum erro de timeout aparece no Slack (o `ack()` é o primeiro comando)
- [ ] Os 3 botões funcionam e ficam registrados

## ⚠️ Armadilhas
- **O Slack exige `ack()` em até 3 segundos.**
- `retomar` só funciona no **mesmo processo** que `processar` (InMemorySaver).
<!-- /issue -->

<!-- issue
id: G-09
title: Parser da reunião (.vtt) com a promessa inteira em um registro só
dev: gabriel
prio: P0
frente: ingestao
est: 20 min
prazo: 13:40
depende: G-02, J-09
-->
## 🎯 Objetivo
Cada fala da reunião vira um `Registro` com **autor e horário**, e a **promessa do desvio 4 fica inteira em um registro**.

## 🪜 Passo a passo
1. `radar/fontes/reuniao.py` → `ler_vtt(caminho) -> list[Registro]`. Formato do arquivo (J-09):
   ```
   WEBVTT
   NOTE data: 2027-01-21

   00:00:12.500 --> 00:00:20.000
   <v Bruno Siqueira>A gente inclui um treinamento presencial pra equipe de vocês, sem custo.
   ```
2. **Data de cada fala** = data do `NOTE data: AAAA-MM-DD` + horário de início do trecho.
3. **Autor:** do prefixo `<v Nome>` (ou `Nome:`).
4. **Junte falas seguidas da mesma pessoa** em um registro só (uma frase cortada entre dois trechos some da análise se não for juntada).
5. `origem = Origem.reuniao`, `canal = "reuniao_alfa"`, `link = None`.
6. Registre em `FileSource` (G-02) para `*.vtt`.
7. Teste: a frase da promessa aparece **inteira, com o nome de quem falou**.

## ✅ Pronto quando
- [ ] A promessa do desvio 4 fica **inteira em um único registro**, com o autor certo
- [ ] A data usa o `NOTE data:` do arquivo

## ⚠️ Armadilhas
- Frase quebrada entre dois cues do `.vtt` some se não for juntada.
- Sem a linha `NOTE data:`, use a data do arquivo ou avise o Joe.
<!-- /issue -->

<!-- issue
id: G-10
title: PDFs do terceiro: gerar os 3 documentos e extrair tipo, pessoa e validade
dev: gabriel
prio: P0
frente: ingestao
est: 60 min
prazo: 14:25
depende: J-06, R-01
-->
## 🎯 Objetivo
Dar ao **desvio 3 uma prova documental**: é o elo com o desafio declarado (*conformidade documental de terceiros*) e a entrada de **entrada multimodal** (PDF) que pontua como técnica extra. **O Ricardo (R-07) depende desta issue.**

## 🪜 Passo a passo
### Parte A: gerar 3 PDFs sintéticos (30 min)
1. Script `scripts/gerar_pdfs.py` com **PyMuPDF** (`fitz`): crie 3 PDFs em `data/documentos/`, com **texto selecionável** (não imagem, para não precisar de OCR) e a marca **"DOCUMENTO FICTÍCIO"** no topo:
   1. **`aso_joao_teixeira.pdf`:** ASO de **João Teixeira**, **validade 10/11/2026 (vencido)**. CPF **falso via Faker** (`Faker("pt_BR").cpf()`). **CPF real é proibido.**
   2. **`documentos_nimbus_012027.pdf`:** *"Relação de documentos entregues, Nimbus Serviços, competência 01/2027"* com tabela `pessoa / documento / validade`: ASO da **Carla Mota** válido até 15/08/2027, NDA assinado, certificado de treinamento de segurança, **sem a guia de FGTS** do mês.
   3. **`certidao_negativa_nimbus.pdf`:** certidão negativa da Nimbus, **válida até 30/06/2027** (documento em ordem, serve de isca).
2. Formato fixo e simples, para a extração ser confiável.

### Parte B: extrair (30 min)
3. `radar/documentos.py` → **`carregar_documentos() -> list[DocumentoExtraido]`**:
   - Abra cada PDF com **PyMuPDF** (`page.get_text()`).
   - **MVP determinístico:** extraia com **regex** (formato fixo): tipo, pessoa, empresa, validade. É rápido e à prova de falha na demo.
   - **Bônus (técnica multimodal):** use o **Haiku** com saída estruturada (`DocumentoExtraido`) e compare com o regex. **Peça a data em ISO** no schema (data brasileira é lida com mês e dia invertidos).
   - Documento **ausente**: a "Relação de documentos" lista o que **foi** entregue; o **R-07** compara com o que a cláusula 6.4 exige (guia de FGTS) e acusa a falta.
4. Salve em `data/cache/documentos_extraidos.json`.
5. **Gere também Registros** (`origem=documento`) com um resumo (*"ASO de João Teixeira, válido até 10/11/2026"*), registrados no `FileSource`, para os documentos aparecerem como evidência.
6. Teste: o ASO vencido sai com **validade 2026-11-10** e a lista de documentos mostra **ausência** da guia de FGTS.

## 🤖 Prompt sugerido
```
Crie scripts/gerar_pdfs.py com PyMuPDF que gera em data/documentos/ três PDFs com texto
selecionável e a marca "DOCUMENTO FICTÍCIO": (1) ASO de João Teixeira com validade
10/11/2026 e CPF falso do Faker pt_BR; (2) relação de documentos entregues pela Nimbus
Serviços na competência 01/2027, com ASO da Carla Mota válido até 15/08/2027, NDA e
treinamento de segurança, sem guia de FGTS; (3) certidão negativa da Nimbus válida até
30/06/2027. Depois crie radar/documentos.py com carregar_documentos() -> list
[DocumentoExtraido] (models.py abaixo) que lê os PDFs com PyMuPDF e extrai tipo, pessoa e
validade (em date) com regex.
```

## ✅ Pronto quando
- [ ] Os 3 PDFs existem, com texto selecionável e a marca "DOCUMENTO FICTÍCIO"
- [ ] `carregar_documentos()` devolve tipo, pessoa e **validade em `date`** certos
- [ ] O ASO do João sai vencido (`2026-11-10`) e o da Carla em dia
- [ ] **Ricardo avisado** para plugar no R-07

## ⚠️ Armadilhas
- **PDF salvo como imagem obriga OCR.** Gere com texto.
- **CPF real é proibido:** use o Faker.
- Data no formato brasileiro lida como mês/dia invertidos: use ISO no schema.
<!-- /issue -->

<!-- issue
id: G-11
title: Streamlit: fila de alertas e "simular mensagem" (plano B sem Slack)
dev: gabriel
prio: P1
frente: slack
est: 45 min
prazo: 15:15
depende: R-04
-->
## 🎯 Objetivo
Uma visão de **todos os alertas** (os 4 desvios juntos na demo) e o **plano B**: se o Slack cair, a demo continua de pé. **Vídeo não vale como plano B.**

## 🪜 Passo a passo
1. **Aba "Fila de alertas":** leia `data/alertas.jsonl` e `data/decisoes.jsonl`. Mostre cada alerta em um container com **2 colunas** (`st.columns`): cláusula (número e `trecho_contrato`) à esquerda, evidência (origem, autor, data, `trecho_evidencia`) à direita. Mostre tipo, confiança, responsável e **status** (pendente, aprovado, descartado, não é desvio).
2. **Filtros** por papel e por status.
3. **Aba "Simular mensagem"** (o plano B): campo de texto + escolha do autor → cria um `Registro` de origem Slack → roda o **mesmo `processar()`** → mostra o alerta com os **botões Aprovar / Descartar / Não é desvio ali mesmo**, chamando o **mesmo `retomar()`**. **Um caminho diferente do real vira outro sistema para manter.**
4. **Botão "Processar histórico":** roda `FileSource("data")` pelo pipeline (carrega os 4 desvios na fila).
5. **`st.cache_resource`** para o cliente do ChromaDB, o modelo de embeddings e o grafo. O Streamlit reexecuta o script a cada clique: sem cache, recarrega o modelo toda vez e fica lento.
6. O grafo do Streamlit é uma **instância própria** (outro processo que o `slack_bot.py`): o `retomar` do plano B só funciona para alertas criados **ali**.

## 🤖 Prompt sugerido
```
Em app.py (Streamlit) crie a aba "Fila de alertas" que lê data/alertas.jsonl e data/
decisoes.jsonl e mostra cada alerta em um container com duas colunas: à esquerda a
cláusula (número e trecho_contrato), à direita a evidência (origem, autor, data,
trecho_evidencia). Mostre tipo, confiança, responsável e status. Adicione filtros e um
botão "Processar histórico" que chama FileSource("data").fetch() e radar.grafo.processar.
Crie a aba "Simular mensagem" que cria um Registro, chama processar e mostra botões que
chamam retomar. Use st.cache_resource para recursos pesados.
```

## ✅ Pronto quando
- [ ] Os 4 desvios aparecem na fila, com status
- [ ] O fluxo completo roda **com o Slack desligado**
- [ ] A simulação usa o mesmo `processar()` e `retomar()`

## ⚠️ Armadilhas
- Sem `st.cache_resource` o modelo recarrega a cada clique.
<!-- /issue -->

<!-- issue
id: G-12
title: Cache das respostas do modelo para a demo (MODO_DEMO=1)
dev: gabriel
prio: P1
frente: pipeline
est: 20 min
prazo: 15:30
depende: R-03
-->
## 🎯 Objetivo
A **demo não pode depender da API estar rápida na hora.**

## 🪜 Passo a passo
1. No `radar/llm.py` (do R-01), preencha os hooks `_cache_get/_cache_set`: guarde cada resposta em `data/cache/llm/{hash}.json`, com `hash = sha1(modelo + system + user + schema)`.
2. Com **`MODO_DEMO=1`**, **leia do cache primeiro** e só chame a API se não houver resposta guardada.
3. **Rode o fluxo ensaiado inteiro uma vez** (as 3 frases da demo e os 4 desvios) para encher o cache.
4. **Ligue também o cache de prompt da API** (`cache_control`) no prompt de sistema e nas cláusulas, que se repetem em toda chamada (leitura a 0,05× da entrada no Sonnet).
5. Teste: **remova a chave da API** (`ANTHROPIC_API_KEY` vazia) e rode o fluxo ensaiado: deve rodar igual.

## ✅ Pronto quando
- [ ] Com a chave da API removida, o fluxo ensaiado **roda igual**
- [ ] O cache está no `.gitignore` (`data/cache/`)

## ⚠️ Armadilhas
- **O cache esconde bugs.** Limpe antes de rodar o eval (R-08 roda com `MODO_DEMO=0`).
<!-- /issue -->

<!-- issue
id: G-13
title: Diagrama de arquitetura (slide 4) e README de evidências
dev: gabriel
prio: P0
frente: pitch
est: 30 min
prazo: 16:20
depende: R-02, R-10
-->
## 🎯 Objetivo
Mostrar **o grafo de verdade, não um desenho genérico**, e juntar as evidências no README para o júri.

## 🪜 Passo a passo
1. **Slide 4, Arquitetura:** parta do `docs/grafo.mmd` exportado no R-02 e do diagrama do README. **Confira com o Ricardo que bate com o código** (incluindo `conferir_documentos`, e a triagem se o R-11 entrar). Renderize o Mermaid (mermaid.live) e exporte imagem.
2. Mostre a **interface de fonte trocável** (arquivos hoje, Gmail/Meet amanhã), que sustenta o critério *Aplicabilidade e replicação*.
3. **README:** complete a seção **"Critérios de qualidade e evidências"** com os links e prints que o Ricardo (R-10) entregar. Atualize o **Status** (checkboxes) e remova do README o que não foi feito.
4. Commit e push na `master` (**depois** do código congelado às 16:30, ou antes se não houver risco).

## ✅ Pronto quando
- [ ] O diagrama do slide é **o mesmo que o código executa**
- [ ] README com evidências e links reais
- [ ] Slide 4 entregue ao Joe (J-14) às 16:20
<!-- /issue -->

<!-- issue
id: G-14
title: Parser de e-mail .eml (se sobrar tempo)
dev: gabriel
prio: P2
frente: ingestao
est: 25 min
prazo: 15:30
depende: G-02, J-17
-->
## 🎯 Objetivo
Cada e-mail vira um `Registro`. **Só se o J-17 (e-mails) existir e sobrar tempo.**

## 🪜 Passo a passo
1. Abra com `email.message_from_file(f, policy=email.policy.default)`.
2. Corpo em texto simples: `msg.get_body(preferencelist=("plain",)).get_content()`.
3. Autor do `From`; data com `email.utils.parsedate_to_datetime`.
4. Texto = **assunto + corpo**, **sem as linhas citadas** do e-mail anterior (as que começam com `>`): senão duplica o conteúdo e gera alerta repetido.
5. Registre em `FileSource` para `emails/*.eml`.

## ✅ Pronto quando
- [ ] Os e-mails viram registros e o desvio 2 aparece no texto
<!-- /issue -->

<!-- issue
id: G-15
title: Cartão de impacto e aba de execução com link do Langfuse (se sobrar tempo)
dev: gabriel
prio: P2
frente: slack
est: 40 min
prazo: 15:30
depende: G-11, R-06, J-12
-->
## 🎯 Objetivo
Ligar a demo ao ROI com um **número na tela** e mostrar ao júri o que acontece por dentro e quanto custa. **Só se sobrar tempo.**

## 🪜 Passo a passo
1. **Cartão de impacto:** leia `data/premissas.json` (J-12) e mostre com `st.metric` os desvios pegos, as horas de retrabalho evitadas e o valor evitado no cenário base. Mostre as **premissas** logo abaixo, em texto pequeno.
2. **Aba de execução:** liste as últimas execuções, cada uma com o **link do traço no Langfuse** (R-06), o custo e o tempo por alerta e o custo acumulado do dia.

## ✅ Pronto quando
- [ ] Os números batem com a planilha de ROI e as premissas estão visíveis
- [ ] O clique abre o traço certo no Langfuse
<!-- /issue -->
