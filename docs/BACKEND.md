# Radar de Desvios

POC do hackathon ETEG 2026. O Radar cruza o que foi combinado em contrato com o que acontece no projeto (Slack, Gmail, Google Calendar e anotações do Meet) e aponta desvios.

> **Regra do projeto: as fontes só LÊEM os canais.** Enviar mensagem, reagir, criar, editar ou apagar qualquer coisa nunca passa pelas fontes. A regra é garantida em três camadas: escopos de leitura no token, lista de métodos permitidos no cliente da Web API e política de ferramentas no cliente MCP.
>
> **Atualização do time (25/11): o Radar também precisa escrever no Slack, só que em outro módulo.** Os alertas são postados no **grupo (canal) do projeto**, marcando o responsável, com os botões Aprovar, Descartar e Não é desvio. Isso é feito por `radar/slack_alertas.py`, com um **token de bot** (`xoxb-`, escopos `chat:write` e, se houver DM, `im:write`) e Socket Mode (`xapp-`). **O código das fontes continua somente leitura**; escrita só existe nesse módulo, e nunca com o token de usuário das fontes.
>
> **Persistência:** tudo fica em **SQLite local** (`data/radar.db`, ver `radar/db.py`).

Estado atual:

- leitura de canais do Slack, pela Web API e pelo servidor MCP oficial do Slack;
- achados (desvios e problemas) guardados em SQLite, com a decisão humana de cada um;
- frontend em React (`web/`) para revisar os achados e decidir: **Aprovar**, **Descartar** ou **Não é desvio**.

Decidir no frontend só grava no banco do próprio Radar. Nada é publicado no Slack: isso será um passo separado, com token de bot próprio, e só para achados aprovados.

## Ambiente

Com venv (não precisa de conda):

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
source .venv/bin/activate
```

Com conda, se preferir:

```bash
conda env create -f environment.yml    # cria o ambiente dev-hackthon
conda activate dev-hackthon
```

O frontend precisa de Node 20 ou mais novo. O `dev.sh` acha sozinho o `.venv` do projeto e um Node instalado em `~/.local/node`.

## Configurar o Slack

1. Em [api.slack.com/apps](https://api.slack.com/apps), crie um app **From scratch** no workspace de teste. Ele precisa ser um app interno: o Slack só libera o MCP para apps internos ou publicados no Marketplace.
2. Em **OAuth & Permissions → User Token Scopes**, adicione **somente** escopos de leitura:

   | Escopo | Para quê |
   |---|---|
   | `channels:history` | Ler mensagens de canais públicos |
   | `groups:history` | Ler mensagens de canais privados |
   | `channels:read` | Dados dos canais públicos |
   | `groups:read` | Dados dos canais privados |
   | `users:read` | Nome de quem escreveu |
   | `users:read.email` | Achar o ID no Slack de quem marcar, pelo e-mail de cada papel (`/slack/users/lookup`) |

   Não adicione escopos de escrita (`chat:write`, `reactions:write`, `*:write`).
3. Para usar o MCP: no menu **Agents** do app, ligue **Slack Model Context Protocol (MCP) Server**.
4. Clique em **Install to Workspace** e copie o **User OAuth Token** (`xoxp-...`).
5. A pessoa dona do token precisa ser membro dos canais do projeto. O token lê o que ela lê.
6. Copie `.env.example` para `.env` e preencha:
   - `SLACK_TEAM_ID`: ID do workspace (`T...`). Se não souber, preencha qualquer valor e rode `GET /fontes/slack/status`: o erro mostra o ID do token.
   - `SLACK_USER_TOKEN`: o `xoxp-...`.
   - `SLACK_CHANNEL_IDS`: IDs dos canais do projeto (`C...`), separados por vírgula. No Slack, clique no nome do canal; o ID aparece no rodapé da janela.
   - Opcionais: `RADAR_TIMEZONE` (padrão `America/Sao_Paulo`) e `SLACK_THREAD_LOOKBACK_DAYS` (padrão 30). Veja [Como a leitura trata o Slack](#como-a-leitura-trata-o-slack).

## Configurar o Gmail

O Radar lê **só os e-mails do projeto**, nunca a caixa inteira. Um e-mail é do projeto se:

- **envolve o cliente** (`GMAIL_CLIENT_CONTACTS` ou `GMAIL_CLIENT_DOMAINS` em de, para ou cópia), **em qualquer assunto**; assim, um pedido do cliente sobre outro tema também é rastreado; ou
- **é só da equipe interna** (`GMAIL_PARTICIPANTS`) e **cita um termo do projeto** (`GMAIL_PROJECT_TERMS`) ou tem o marcador `GMAIL_LABEL`. Sem essa condição, entraria conversa interna de outros projetos.

A busca é montada no código e pode ser vista em `GET /gmail/query`. Cada mensagem ainda passa por uma segunda checagem depois da busca. Limitação: se o mesmo contato do cliente participar de dois projetos, os e-mails dos dois entram. Nesse caso, use o termo ou o marcador.

Credencial, só com o escopo `gmail.readonly`:

1. **Recomendado (renova sozinha):**
   1. No Google Cloud, ative a **Gmail API**.
   2. Crie um cliente OAuth do tipo **App para computador** (Desktop).
   3. Se a tela de consentimento estiver em modo de teste, adicione a conta monitorada como usuária de teste.
   4. Baixe o JSON do cliente para `.secrets/gmail_client_secret.json`.
   5. Rode:
      ```bash
      python -m radar.fontes.gmail.autorizar
      ```
      O navegador abre. Entre com a conta monitorada e aprove; o token fica em `.secrets/gmail_token.json`.
2. **Teste rápido:** defina `GMAIL_ACCESS_TOKEN=ya29...` no `.env`. Esse token expira em cerca de 1 hora e não é renovado.

A pasta `.secrets/` e o `.env` ficam fora do Git. `GET /fontes/email/status` mostra a conta, os escopos do token e um aviso se houver escopo além de leitura.

## Rodar

```bash
uvicorn radar.api.app:app --reload
```

Documentação interativa: http://localhost:8000/docs

### Frontend (`web/`): a tela da Fila de alertas

A tela segue o design do MVP no canvas [Radar de Desvios · Interfaces](https://claude.ai/artifact/WQzLGJCfodQF3BpFjFoud8) (tela "1 · Fila de alertas + cartão de impacto"). Precisa de Node 20 ou mais novo.

**Rodar tudo com um comando** (API + tela, Ctrl+C para as duas):

```bash
./dev.sh --demo     # --demo recria o banco com os achados sintéticos do design
```

Abra http://localhost:5173.

**Ou em dois terminais:**

```bash
# terminal 1: API
source .venv/bin/activate              # ou: conda activate dev-hackthon
python -m radar.achados.demo --limpar   # só na primeira vez, ou para zerar a demo
uvicorn radar.api.app:app --reload
```

```bash
# terminal 2: tela
cd web
npm install        # só na primeira vez
npm run dev        # http://localhost:5173
```

O Vite repassa `/api/*` para o FastAPI na porta 8000, então o navegador fala com uma origem só e não precisa de CORS. Os tokens ficam só no backend.

O que a tela faz:

- **Resumo do dia** (cartão escuro) e **impacto**: desvios, críticos, horas e custo evitado (`horas_estimadas` × `RADAR_VALOR_HORA`).
- **Notificar por Slack** e **Enviar alertas em lote** gravam a decisão `aprovado`; **Não é desvio** grava `nao_e_desvio` (vira caso de teste). **Desfazer** volta para pendente.
- **Ainda não publica no Slack.** A aprovação só fica no banco; o envio de verdade será um passo separado, com token de bot próprio.
- Quem decide: na primeira decisão a tela pede seu nome (sem login na POC); clique no avatar para trocar.
- **Rodar análise** só recarrega os alertas: o detector com LLM ainda não existe. A volta para "Projetos" ainda não tem tela.

### Tela de Configurações (engrenagem → `#/configuracoes`)

Segue a tela "3 · Configurações do projeto" do mesmo canvas.

- **Contrato e arquivos:** o botão + envia PDFs do computador (até 20 MB). O arquivo vai na hora para `.data/arquivos/`, fora do Git; a lixeira apaga na hora. O tipo (Contrato, Terceiro, Reunião…) sai do nome do arquivo, enquanto o detector não lê o conteúdo. **Buscar no Drive, Gmail e Meet aparece como "em breve"**: os conectores ainda não existem.
- **Slack:** "Canais lidos" aceita `#nome` ou ID (`C…`). Canal novo é conferido no Slack ao salvar (se não existir ou o token não enxergar, a tela mostra o erro). Depois de salvar, **esses passam a ser os únicos canais que o Radar lê**, no lugar de `SLACK_CHANNEL_IDS`. O selo "Slack conectado" testa o token de verdade (`auth.test`).
- **Pessoas envolvidas:** nome e papel. O papel decide quem aparece em cada alerta da Fila.
- **Salvar alterações** grava canais e pessoas no banco e volta para a Fila.
- Antes da primeira gravação, a tela mostra o que está no `.env` (`SLACK_CHANNEL_IDS`, `RADAR_GESTOR`, `RADAR_COMERCIAL`, `RADAR_ADM_CONTRATOS`). Nome do projeto, cliente e valor da hora continuam no `.env`.
- Na demo (`--demo`), os canais `#alfa-projeto` e `#alfa-contratos` têm IDs fictícios. Salvar sem mexer neles não consulta o Slack.

Os tipos do frontend vêm do OpenAPI do backend. Depois de mudar um modelo, com a API rodando:

```bash
cd web && npm run gen:api
```

| Pasta | O que tem |
|---|---|
| `web/src/api/client.ts` | Chamadas à API e tipos (gerados em `schema.d.ts`) |
| `web/src/App.tsx` | Barra superior, nome de quem decide e troca de tela (`#/` e `#/configuracoes`) |
| `web/src/pages/Fila.tsx` | Fila de alertas: cabeçalho, resumo do dia, impacto, filtros, envio em lote, aviso com Desfazer |
| `web/src/pages/Configuracoes.tsx` | Contrato e arquivos, Slack, pessoas e categorias |
| `web/src/components/AlertCard.tsx` | Cartão do alerta: contrato × evidência, responsável e ações |
| `web/src/components/NomeDialog.tsx` | Pergunta quem está decidindo |
| `web/src/csv.ts` | Botão "Baixar CSV" |

Rotas genéricas (valem para qualquer canal registrado):

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/health` | Verifica se a API está no ar |
| GET | `/fontes` | Canais implementados e se estão configurados no `.env` |
| GET | `/fontes/{origem}/status` | Confere a conexão (Slack: workspace e usuário do token; recusa token de outro workspace) |
| GET | `/fontes/{origem}/registros` | Registros do projeto no formato comum. Filtros: `desde`, `ate` (ISO 8601), `limite`, `escopo` |

Rotas específicas do Slack:

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/slack/channels` | Canais do projeto (`SLACK_CHANNEL_IDS`) |
| GET | `/slack/channels/{id}/messages` | Mensagens como `Registro`. Filtros: `oldest`, `latest`, `limit`, `include_threads` |
| GET | `/slack/channels/{id}/threads/{ts}` | Uma thread completa |
| GET | `/slack/users/lookup?email=` | ID do Slack e `<@ID>` pronto para marcar, a partir do e-mail. 404 se ninguém usa o e-mail |
| GET | `/slack/mcp/tools` | Ferramentas do servidor MCP do Slack e quais estão liberadas |
| POST | `/slack/mcp/tools/{nome}` | Executa uma ferramenta MCP **de leitura**; o corpo traz os argumentos em JSON |

Rotas dos achados:

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/achados` | Achados em ordem de gravidade (crítico primeiro). Filtros: `status`, `categoria`, `projeto` |
| GET | `/achados/{id}` | Um achado |
| GET | `/projeto` | Nome, cliente, canais, pessoas e valor da hora |
| PUT | `/projeto/config` | Salva canais (`#nome` ou ID) e pessoas. 422 se um canal novo não existir no Slack |
| GET | `/projeto/slack` | O token do Slack funciona? |
| GET / POST / DELETE | `/projeto/arquivos` | Lista, envia (`?nome=`, corpo = bytes do PDF) e remove arquivos |
| GET | `/analises/ultima` | Última análise: resumo do dia e registros lidos. 404 se nunca rodou |
| DELETE | `/achados/{id}/decisao?por=` | Desfaz a decisão: volta para pendente (fica no histórico) |
| POST | `/achados/{id}/decisao` | `{"decisao": "aprovado" \| "descartado" \| "nao_e_desvio", "decidido_por": "...", "comentario": "..."}`. Cada achado é decidido uma vez só: a segunda decisão volta com 409 |

Um **desvio** sem o trecho do contrato (`combinado`) é recusado na validação: se só existe um dos lados, não é desvio. Toda decisão também entra na tabela `decisoes`, que alimenta os evals (cada "não é desvio" é um falso positivo registrado).

Exemplos:

```bash
# tudo o que aconteceu no Slack do projeto desde as 9h
curl "localhost:8000/fontes/slack/registros?desde=2026-11-25T09:00:00-03:00"

curl "localhost:8000/slack/channels/C0123456789/messages?limit=50&include_threads=true"

# mensagens a partir de um instante (timestamp Unix)
curl "localhost:8000/slack/channels/C0123456789/messages?oldest=1764028800"

# descobrir as ferramentas MCP e chamar uma de leitura
curl localhost:8000/slack/mcp/tools
curl -X POST localhost:8000/slack/mcp/tools/<nome> \
  -H 'content-type: application/json' -d '{"channel_id": "C0123456789"}'
```

Qualquer pedido para um canal fora de `SLACK_CHANNEL_IDS` volta com 403.

Rotas específicas do Gmail:

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/gmail/query` | Busca aplicada (envolvidos + projeto) |
| GET | `/gmail/threads/{id}` | Uma conversa do projeto; conversa fora do projeto volta com 403 |
| GET | `/gmail/mcp/tools` | Ferramentas do servidor MCP do Gmail e quais estão liberadas |
| POST | `/gmail/mcp/tools/{nome}` | Executa uma ferramenta MCP de leitura. A busca é sempre embrulhada no filtro do projeto; a leitura por ID é conferida antes pela Gmail API |

```bash
# e-mails do projeto desde 1º/11
curl "localhost:8000/fontes/email/registros?desde=2026-11-01T00:00:00-03:00"
```

### Como a leitura trata o Slack

- **Menções viram texto.** `<@U123>` vira `@Ana`, `<!channel>` vira `@channel`, `<!subteam^…|@devs>` vira `@devs`. Assim, citar um trecho no relatório não notifica ninguém. Os IDs mencionados ficam em `metadados.mencionados`. As entidades `&lt;` e `&gt;` não são desfeitas, para que um `&lt;!channel&gt;` escrito por alguém não vire menção de verdade.
- **Threads antigas com conversa nova.** Com `desde`, o Radar também procura threads abertas até `SLACK_THREAD_LOOKBACK_DAYS` dias antes do período e traz as respostas delas que caem no período. A raiz antiga não entra; o `metadados.thread_ts` e a rota `/threads/{ts}` dão o contexto.
- **Datas no fuso do projeto.** `data` sai em `RADAR_TIMEZONE` (ex.: `2026-11-24T22:40:00-03:00`), para que "madrugada" e "fim de semana" sejam do horário local. Filtros `desde`/`ate` sem fuso também são lidos nesse fuso.
- **Sem duplicatas.** Uma resposta enviada "também ao canal" aparece uma vez só.

### Política das ferramentas MCP

O Slack não publica o nome de todas as ferramentas do servidor MCP. Por isso a API descobre as ferramentas na hora e só libera uma ferramenta quando:

- o servidor a marca como somente leitura;
- o nome indica leitura (`read`, `list`) e nenhum verbo de escrita;
- ela não é de busca. A busca cobre o workspace inteiro, não só os canais do projeto, e por isso fica bloqueada por ora.

Ferramentas de canal ou thread também precisam receber um canal do projeto nos argumentos.

## Formato do Registro

Toda fonte devolve o mesmo formato, que o pipeline de detecção vai consumir:

```json
{
  "id": "slack:C0123456789:1764028800.000100",
  "origem": "slack",
  "data": "2025-11-24T21:00:00-03:00",
  "autor": "Ana Gestora",
  "texto": "@Bruno a gente faz o módulo extra",
  "link": "https://workspace.slack.com/archives/C0123456789/p1764028800000100",
  "metadados": {"canal": "C0123456789", "ts": "...", "thread_ts": null, "autor_id": "U...", "mencionados": ["U..."]}
}
```

## Testes

```bash
pytest
ruff check . && ruff format --check .
```

## Arquitetura

O projeto segue **Ports & Adapters** (arquitetura hexagonal) de forma enxuta:

- **Núcleo (`radar/core`)**: os modelos (`Registro`, `Consulta`), a porta `Fonte` e os erros comuns. Não importa nada de Slack nem de Google.
- **Adaptadores (`radar/fontes/<canal>`)**: cada canal implementa `Fonte` (`status()` e `fetch(consulta)`), lê a própria configuração do `.env` e traduz os erros do SDK para os erros do núcleo.
- **Registro (`radar/fontes/registry.py`)**: o único lugar que liga uma `Origem` ao seu adaptador.
- **MCP (`radar/mcp`)**: cliente e política de só leitura compartilhados pelos servidores MCP do Slack e do Google.
- **API (`radar/api`)**: as rotas usam o registro e tratam os erros num único ponto, que traduz cada erro para o status HTTP: não configurada → 503, acesso negado/escrita/fora do escopo → 403, não encontrado → 404, achado já decidido → 409, valor inválido (ex.: canal inexistente) → 422, falha externa → 502.

```
radar/
├── core/
│   ├── models.py        # Origem, Registro, Consulta
│   ├── ports.py         # porta Fonte (status, fetch)
│   └── errors.py        # FonteNaoConfigurada, AcessoNegado, EscritaBloqueada, ForaDoEscopo, NaoEncontrado, FalhaNaFonte
├── achados/
│   ├── models.py        # Achado, Citacao, Decisao (schema da saída do detector)
│   ├── store.py         # SQLite: achados + histórico de decisões
│   ├── config.py        # RADAR_DB_PATH, RADAR_PROJETO, pessoas por papel, valor da hora
│   └── demo.py          # achados e configuração sintéticos para a demo
├── projeto/
│   ├── models.py        # Projeto, ProjetoConfig, Pessoa, CanalSlack, Arquivo
│   ├── store.py         # configuração e índice dos PDFs (SQLite) + arquivos em disco
│   └── service.py       # .env como valor inicial; só consulta o Slack para canal novo
├── mcp/
│   ├── policy.py        # política de só leitura para ferramentas MCP
│   └── client.py        # cliente MCP remoto (Streamable HTTP + Bearer)
├── fontes/
│   ├── registry.py      # Origem -> fábrica do adaptador
│   └── slack/
│       ├── config.py    # SlackSettings (SLACK_* do .env)
│       ├── readonly.py  # Web API com lista de métodos de leitura
│       ├── fonte.py     # SlackFonte (implementa Fonte)
│       ├── texto.py     # menções do Slack -> texto que não notifica
│       └── mcp.py       # servidor MCP do Slack: política e validação de canal
└── api/
    ├── app.py           # FastAPI e tradução de erros para HTTP
    ├── deps.py          # injeção de dependências
    └── routes/          # fontes.py (genéricas), slack.py (específicas), achados.py
web/                     # frontend React (Vite + TanStack Query)
tests/
```

### Como incluir um canal novo (ex.: Gmail)

1. Crie `radar/fontes/gmail/` com:
   - `config.py`: `GmailSettings` com o prefixo `GMAIL_`;
   - uma classe com `origem`, `status()` e `fetch(consulta)` que devolve `Registro`;
   - a função `create()`, que levanta `FonteNaoConfigurada` se faltar configuração.
2. Acrescente `Origem.email: gmail.create` em `FACTORIES`, no `registry.py`.
3. Se usar o servidor MCP do Google, reutilize `ReadOnlyMcpClient` com uma `ReadOnlyPolicy` e um validador de escopo próprio (por exemplo, só e-mails dos envolvidos no projeto).

Pronto: `/fontes/email/registros` e o pipeline passam a enxergar o Gmail. Rotas específicas são opcionais.
