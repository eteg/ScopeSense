# Radar de Desvios

POC do hackathon ETEG 2026. O Radar cruza o que foi combinado em contrato com o que acontece no projeto (Slack, Gmail, Google Calendar e anotações do Meet) e aponta desvios.

> **Regra do projeto: as fontes só LÊEM os canais.** Enviar mensagem, reagir, criar, editar ou apagar qualquer coisa nunca passa pelas fontes. A regra é garantida em três camadas: escopos de leitura no token, lista de métodos permitidos no cliente da Web API e política de ferramentas no cliente MCP.
>
> **Atualização do time (25/11): o Radar também precisa escrever no Slack, só que em outro módulo.** Os alertas são postados no **grupo (canal) do projeto**, marcando o responsável, com os botões Aprovar, Descartar e Não é desvio. Isso é feito por `radar/slack_alertas.py`, com um **token de bot** (`xoxb-`, escopos `chat:write` e, se houver DM, `im:write`) e Socket Mode (`xapp-`). **O código das fontes continua somente leitura**; escrita só existe nesse módulo, e nunca com o token de usuário das fontes.
>
> **Persistência:** tudo fica em **SQLite local** (`data/radar.db`, ver `radar/db.py`).

Estado atual: leitura de canais do Slack, pela Web API e pelo servidor MCP oficial do Slack.

## Ambiente (conda)

```bash
conda env create -f environment.yml    # cria o ambiente dev-hackthon
conda activate dev-hackthon
# se o ambiente já existir: pip install -e ".[dev]"
```

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
   | `users:read.email` | Cruzar autor com o e-mail cadastrado no projeto |

   Não adicione escopos de escrita (`chat:write`, `reactions:write`, `*:write`).
3. Para usar o MCP: no menu **Agents** do app, ligue **Slack Model Context Protocol (MCP) Server**.
4. Clique em **Install to Workspace** e copie o **User OAuth Token** (`xoxp-...`).
5. A pessoa dona do token precisa ser membro dos canais do projeto. O token lê o que ela lê.
6. Copie `.env.example` para `.env` e preencha:
   - `SLACK_TEAM_ID`: ID do workspace (`T...`). Se não souber, preencha qualquer valor e rode `GET /fontes/slack/status`: o erro mostra o ID do token.
   - `SLACK_USER_TOKEN`: o `xoxp-...`.
   - `SLACK_CHANNEL_IDS`: IDs dos canais do projeto (`C...`), separados por vírgula. No Slack, clique no nome do canal; o ID aparece no rodapé da janela.

## Rodar

```bash
uvicorn radar.api.app:app --reload
```

Documentação interativa: http://localhost:8000/docs

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
| GET | `/slack/mcp/tools` | Ferramentas do servidor MCP do Slack e quais estão liberadas |
| POST | `/slack/mcp/tools/{nome}` | Executa uma ferramenta MCP **de leitura**; o corpo traz os argumentos em JSON |

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
  "data": "2025-11-25T00:00:00Z",
  "autor": "Ana Gestora",
  "texto": "a gente faz o módulo extra",
  "link": "https://workspace.slack.com/archives/C0123456789/p1764028800000100",
  "metadados": {"canal": "C0123456789", "ts": "...", "thread_ts": null, "autor_id": "U..."}
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
- **API (`radar/api`)**: as rotas usam o registro e tratam os erros num único ponto, que traduz cada erro para o status HTTP: não configurada → 503, acesso negado/escrita/fora do escopo → 403, falha externa → 502.

```
radar/
├── core/
│   ├── models.py        # Origem, Registro, Consulta
│   ├── ports.py         # porta Fonte (status, fetch)
│   └── errors.py        # FonteNaoConfigurada, AcessoNegado, EscritaBloqueada, ForaDoEscopo, FalhaNaFonte
├── mcp/
│   ├── policy.py        # política de só leitura para ferramentas MCP
│   └── client.py        # cliente MCP remoto (Streamable HTTP + Bearer)
├── fontes/
│   ├── registry.py      # Origem -> fábrica do adaptador
│   └── slack/
│       ├── config.py    # SlackSettings (SLACK_* do .env)
│       ├── readonly.py  # Web API com lista de métodos de leitura
│       ├── fonte.py     # SlackFonte (implementa Fonte)
│       └── mcp.py       # servidor MCP do Slack: política e validação de canal
└── api/
    ├── app.py           # FastAPI e tradução de erros para HTTP
    ├── deps.py          # injeção de dependências
    └── routes/          # fontes.py (genéricas), slack.py (específicas)
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
