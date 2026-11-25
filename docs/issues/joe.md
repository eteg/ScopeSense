<!-- issue
id: J-01
title: Criar o workspace de teste do Slack e dar um papel a cada dev
dev: joe
prio: P0
frente: setup
est: 20 min
prazo: 11:45
depende: nada
-->
## 🎯 Objetivo
Ter um Slack **de verdade e isolado do Slack da ETEG** para o momento uau da demo, com um usuário por papel.

## 🪜 Passo a passo
1. Em https://slack.com/create, crie o workspace gratuito **`radar-hackathon`**.
2. Convide **Gabriel** e **Ricardo** por e-mail. Cada pessoa assume um papel (é por ele que a DM chega à pessoa certa):

   | Dev | Papel no Radar | Recebe alertas de |
   |-----|----------------|-------------------|
   | Joe | `gestor` | `escopo_extra` |
   | Gabriel | `comercial` | `prazo_sla` |
   | Ricardo | `administrativo_contratos` | `terceiro_sem_documento` e `promessa_fora_do_contrato` |

   O **cliente** e o **terceiro** (João, Carla) não precisam de usuário: falam pelo JSON sintético. Para o momento uau ao vivo, qualquer um digita a frase no canal.
3. Crie dois canais **públicos** (não privados): `#projeto-alfa` e `#projeto-alfa-cliente`.
4. Anote os **IDs** e cole em um comentário desta issue:
   - Usuário: perfil → `⋯` → **Copiar ID do membro** (formato `U0123ABCD`).
   - Canal: nome do canal → aba **Sobre** → rodapé (formato `C0123ABCD`).

## ✅ Pronto quando
- [ ] Os 3 devs estão no workspace, cada um com o seu papel
- [ ] Os dois canais públicos existem
- [ ] Comentário com a tabela `papel → ID do usuário` e `canal → ID` (o J-07 e o Gabriel usam)

## ⚠️ Armadilhas
- Canal **privado** exige outro escopo (`groups:history`) e o plano é só canais públicos.
- Não use o workspace da ETEG, nem convide ninguém de fora.
- Depois de criar o app (J-02), o bot precisa ser **convidado** nos dois canais.
<!-- /issue -->

<!-- issue
id: J-02
title: Criar o app "Radar" no Slack (Socket Mode, scopes e tokens)
dev: joe
prio: P0
frente: setup
est: 25 min
prazo: 12:10
depende: J-01
-->
## 🎯 Objetivo
Criar o app que lê o canal e manda a DM com botões. É o que **bloqueia o Gabriel** (G-06, G-07, G-08), então vale fazer logo depois do J-01.

## 🪜 Passo a passo
1. https://api.slack.com/apps → **Create New App → From scratch** → nome `Radar` → workspace `radar-hackathon`.
2. **Socket Mode** → ligue → *Generate token* com o escopo `connections:write`. Guarde o **app token** (`xapp-...`).
3. **OAuth & Permissions → Bot Token Scopes**, adicione:
   - `channels:history` (ler mensagens dos canais públicos)
   - `channels:read` (nome do canal)
   - `chat:write` (postar e atualizar mensagens)
   - `im:write` (abrir DM com o responsável)
   - `users:read` (nome de quem escreveu)
4. **Event Subscriptions** → *Enable Events* → *Subscribe to bot events* → adicione **`message.channels`** (não `app_mention`). Salve.
5. **Interactivity & Shortcuts** → ligue. Com Socket Mode não precisa de URL.
6. **App Home** → habilite a *Messages Tab* e marque *Allow users to send Slash commands and messages from the messages tab* (garante que a DM do bot aparece).
7. **Install to Workspace** e autorize. Copie o **bot token** (`xoxb-...`).
8. Nos dois canais, digite: `/invite @Radar`.
9. **Entregue os tokens por mensagem privada** ao Gabriel e ao Ricardo (nunca no canal do time, nunca no Git). Eles colocam no `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   ```

## ✅ Pronto quando
- [ ] Os dois tokens foram entregues em privado
- [ ] O bot aparece nos dois canais
- [ ] Event Subscriptions e Interactivity salvos
- [ ] Gabriel conseguiu rodar o teste "ping → pong" (G-06)

## ⚠️ Armadilhas
- **Mudou scopes? Reinstale o app** no workspace, senão os novos scopes não valem.
- `xapp-` (app token, Socket Mode) e `xoxb-` (bot token) são **dois tokens diferentes**. Confundir é o erro mais comum.
- Sem `im:write` o bot não consegue abrir DM.
- O bot só recebe mensagens dos canais para onde foi convidado.
<!-- /issue -->

<!-- issue
id: J-03
title: Console da Anthropic: crédito, limite de gasto e chave da API
dev: joe
prio: P0
frente: setup
est: 15 min
prazo: 11:45
depende: nada
-->
## 🎯 Objetivo
Todos chamam o modelo sem estourar a verba e sem expor a chave. A verba prevista é **US$ 50**: US$ 20 de API, US$ 20 de assinatura de ferramenta de código e US$ 10 de reserva.

## 🪜 Passo a passo
1. Entre no **Console da Anthropic** (console.anthropic.com) com a conta do hackathon.
2. Em *Billing*, adicione **US$ 20** de crédito.
3. Em *Limits*, defina o **limite mensal de gasto** em US$ 20 **antes** de distribuir a chave.
4. Em *API keys*, crie uma chave chamada `hackathon-radar`.
5. Envie a chave **em privado** para Ricardo e Gabriel (ou por gerenciador de senhas). Eles colocam no `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
6. Modelos do projeto (ficam só em `radar/config.py`): `claude-sonnet-5-5` para classificação e extração, `claude-haiku-5-5` para triagem, juiz do eval e leitura de PDF.

## ✅ Pronto quando
- [ ] O limite de gasto está ativo
- [ ] Ricardo e Gabriel rodam `python scripts/ping_modelo.py` (R-01) e recebem "ok"

## ⚠️ Armadilhas
- Chave no Git ou no Slack = **revogue na hora** e gere outra.
- Estimativa de custo: ~US$ 0,009 por registro no Sonnet e ~US$ 0,00045 no Haiku; 20 rodadas de eval no Sonnet custam ~US$ 11. Avise o time para não rodar o eval no Sonnet à toa.
<!-- /issue -->

<!-- issue
id: J-04
title: Langfuse: conta, projeto, chaves e convite ao Ricardo
dev: joe
prio: P0
frente: setup
est: 15 min
prazo: 11:55
depende: nada
-->
## 🎯 Objetivo
Ter onde ver **custo, tokens e tempo de cada alerta**. O custo real daqui alimenta o slide de ROI.

## 🪜 Passo a passo
1. Crie a conta no **Langfuse Cloud, plano Hobby** (grátis, sem cartão) e um projeto `radar-desvios`.
2. Em *Settings → API Keys*, gere as chaves pública e secreta e anote o **host** (`https://cloud.langfuse.com` ou o da sua região).
3. Entregue **em privado** ao Ricardo (e Gabriel, que só precisa das chaves):
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
4. Convide o **Ricardo** como usuário do projeto. O plano Hobby tem **2 usuários**: Joe e Ricardo. O Gabriel mostra o painel por tela compartilhada.

## ✅ Pronto quando
- [ ] Ricardo consegue entrar no painel
- [ ] Chaves entregues (o R-06 faz o traço de teste)

## ⚠️ Armadilhas
- Não compartilhe um único login para driblar o limite de usuários.
- Se o painel mostrar **custo zero** para o modelo, é preciso cadastrar o preço dele em *Models* (o R-06 explica).
<!-- /issue -->

<!-- issue
id: J-05
title: Confirmar com a organização o desafio declarado
dev: joe
prio: P0
frente: pitch
est: 10 min
prazo: 11:50
depende: nada
-->
## 🎯 Objetivo
Evitar surpresa no julgamento: o **prazo para declarar o desafio era 24/11** e hoje é 25/11. Um desafio do catálogo declarado e confirmado é requisito mínimo; sem ele a nota despenca.

## 🪜 Passo a passo
1. Mande a mensagem abaixo à organização (use o canal oficial do hackathon):
   > Oi! O nosso time declara o desafio **"Conformidade documental de terceiros"**, aplicado ao processo interno da ETEG: o sistema cruza contrato, documentos do terceiro e a execução do projeto (Slack, reuniões e e-mails) e avisa o responsável quando algo sai do combinado. Técnicas: **RAG** e **graph engineering**. Critérios de qualidade: **observabilidade, evals, human-in-the-loop e saída validada por schema**. Recursos: crédito de API de modelo. Podem confirmar se está ok?
2. Registre a **resposta** em comentário nesta issue e no canal do time.
3. Se pedirem ajuste (outro nome de desafio, outra técnica), avise o time **antes das 12h**.

## ✅ Pronto quando
- [ ] Confirmação da organização registrada aqui

## ⚠️ Armadilhas
- O desafio fala de terceiros e o Radar nasceu como gestão de risco do projeto. A **ponte é o desvio 3** (terceiro sem documento), que precisa aparecer na demo.
<!-- /issue -->

<!-- issue
id: J-06
title: Escrever o contrato do Projeto Alfa (a referência de tudo)
dev: joe
prio: P0
frente: dados
est: 40 min
prazo: 12:30
depende: nada
-->
## 🎯 Objetivo
O contrato é a referência de tudo. Cada desvio precisa de uma cláusula clara que o contradiga. **Gabriel (G-04) e Ricardo (R-03) esperam este arquivo.**

## 🪜 Passo a passo
1. Peça o texto ao Claude (prompt abaixo) e **revise à mão** as cláusulas `2.2`, `3`, `5`, `6.x` e `7`, que sustentam os 4 desvios.
2. **Formato obrigatório** (o parser de cláusulas do Gabriel depende dele): cada cláusula começa com um título de nível 3 `### N Título` ou `### N.N Título`, seguido do texto.
   ```markdown
   ### 2.2 Fora do escopo
   Não fazem parte deste contrato: (a) o módulo de relatórios; (b) treinamento presencial.
   ```
3. Use os **fatos da bíblia dos dados** (`docs/PLANO-MVP.md`, seção 6): projeto, datas, nomes e numeração de cláusulas. Em especial:
   - `2.1` módulos incluídos: atendimento, base de conhecimento, integração com CRM
   - `2.2` fora do escopo: **módulo de relatórios** e **treinamento presencial**
   - `3` marcos: M1 22/12/2026 · M2 25/01/2027 · **M3 29/01/2027** (integração com CRM) · go-live 23/02/2027
   - `5` mudança de escopo **somente por aditivo assinado**
   - `6.1` ASO válido na data de início · `6.2` NDA · `6.3` treinamento de segurança · `6.4` guia de FGTS do mês e certidão negativa **antes do início**
   - `7` treinamento: **uma sessão remota de 2 horas**
4. Salve em **`data/contrato_alfa.md`** e faça commit. Entrega parcial importa: se as cláusulas 2.2, 3 e 6 estiverem prontas, avise o Gabriel.
5. (Opcional) exporte em PDF para mostrar na demo.

## 🤖 Prompt sugerido
```
Escreva em markdown um contrato fictício de prestação de serviços entre a ETEG e a
Distribuidora Boreal para implantar o Projeto Alfa (portal de atendimento) em 12
semanas, de 01/12/2026 a 23/02/2027. Use EXATAMENTE este formato: cada cláusula começa
com uma linha "### N Título" ou "### N.N Título", seguida do texto. Cláusulas: 1 Objeto;
2.1 Módulos incluídos (atendimento, base de conhecimento, integração com CRM); 2.2 Fora
do escopo (módulo de relatórios, treinamento presencial); 3 Prazos e marcos (M1 22/12/2026
atendimento no ar; M2 25/01/2027 base de conhecimento; M3 29/01/2027 integração com CRM;
go-live 23/02/2027); 4 SLA de incidentes; 5 Mudança de escopo só por aditivo assinado
por ambas as partes; 6.1 ASO válido na data de início de cada subcontratado; 6.2 NDA
assinado; 6.3 Treinamento de segurança; 6.4 Guia de FGTS do mês e certidão negativa
entregues antes do início; 7 Treinamento limitado a uma sessão remota de 2 horas;
8 Preço e pagamento; 9 Confidencialidade e LGPD. Linguagem jurídica simples, de 6 a 10
páginas, todos os nomes fictícios.
```

## ✅ Pronto quando
- [ ] Arquivo `data/contrato_alfa.md` no repositório, com cláusulas no formato `### N Título`
- [ ] Cada um dos 4 desvios tem uma cláusula que o contradiz (2.2, 3, 6.x, 7)
- [ ] Numeração igual à da bíblia dos dados

## ⚠️ Armadilhas
- **Contrato vago** faz o modelo não conseguir provar nada. **Contrato longo demais** encarece cada chamada.
- Não mude a numeração depois: o gabarito e o eval citam `2.2`, `6.1` etc.
<!-- /issue -->

<!-- issue
id: J-07
title: Ficha do projeto e personas (projeto_alfa.json)
dev: joe
prio: P0
frente: dados
est: 15 min
prazo: 12:20
depende: J-01
-->
## 🎯 Objetivo
Ligar cada **papel** ao **usuário do Slack de teste**, para a DM chegar à pessoa certa. Também alimenta o parser (nomes no lugar de IDs).

## 🪜 Passo a passo
1. Crie **`data/projeto_alfa.json`** com este formato (substitua os IDs pelos do J-01):
   ```json
   {
     "projeto": {"nome": "Projeto Alfa", "cliente": "Distribuidora Boreal",
                 "inicio": "2026-12-01", "fim": "2027-02-23"},
     "papeis": {
       "gestor":                   {"nome": "Helena Prado",  "slack_id": "U0JOE...",     "autor_slack": true},
       "comercial":                {"nome": "Bruno Siqueira", "slack_id": "U0GABRIEL...", "autor_slack": true},
       "administrativo_contratos": {"nome": "Camila Reis",    "slack_id": "U0RICARDO...", "autor_slack": true}
     },
     "pessoas_sinteticas": {
       "U_CLIENTE_01": {"nome": "Marcos Lima",   "papel": "cliente"},
       "U_CLIENTE_02": {"nome": "Patrícia Souza","papel": "cliente"}
     },
     "terceiro": {
       "empresa": "Nimbus Serviços",
       "pessoas": [{"nome": "João Teixeira"}, {"nome": "Carla Mota"}]
     },
     "roteamento": {
       "escopo_extra": "gestor",
       "prazo_sla": "comercial",
       "terceiro_sem_documento": "administrativo_contratos",
       "promessa_fora_do_contrato": "administrativo_contratos"
     }
   }
   ```
2. Os nomes das personas são **fictícios** (o nome do dev real não aparece no dado). O que liga ao Slack é o `slack_id`.
3. Os IDs `U_CLIENTE_xx` são autores fictícios usados no `data/slack_export.json` (J-08).

## ✅ Pronto quando
- [ ] O JSON é válido (`python -c "import json;json.load(open('data/projeto_alfa.json'))"`)
- [ ] Os 3 `slack_id` batem com o workspace
- [ ] O mapeamento `tipo → papel` é o da bíblia dos dados

## ⚠️ Armadilhas
- Nome real de colega ou de cliente: **proibido**. Tudo fictício.
<!-- /issue -->

<!-- issue
id: J-08
title: Mensagens do Slack, iscas e frases da demo (slack_export.json)
dev: joe
prio: P0
frente: dados
est: 50 min
prazo: 13:15
depende: J-06
-->
## 🎯 Objetivo
Uma conversa de projeto que **pareça real**, com os desvios 1, 2 e 3 escondidos e 5 iscas que parecem desvio mas não são. É o que o eval usa para provar precisão (a pergunta mais perigosa do júri é *"quantos alertas são falsos?"*).

## 📦 Entregas
1. **12:30, entrega parcial:** as primeiras ~10 mensagens com o **desvio 1**, para o Gabriel testar o parser (G-03).
2. **13:15, entrega completa:** `data/slack_export.json` com **22 a 25 mensagens** em 2 canais.

## 🪜 Passo a passo
1. Formato do export do Slack (lista de objetos):
   ```json
   {"ts": "1768827600.000100", "user": "U_CLIENTE_01", "text": "...", "thread_ts": null, "channel": "projeto-alfa-cliente"}
   ```
   `ts` é segundos desde 1970 com decimais, **crescente**, coerente com as datas de 18/01/2027 a 05/02/2027. Se a mensagem responde outra, use o mesmo `thread_ts` da mãe.
2. Linha do tempo de 3 semanas nos canais `projeto-alfa` e `projeto-alfa-cliente`. ~70% é **conversa normal** (status, dúvidas, piadas, combinados).
3. **Plante os 3 desvios** (datas da bíblia dos dados), cada um em 1 ou 2 mensagens, **sem as palavras "desvio", "contrato" ou "cláusula"**:
   - **Desvio 1 (19/01/2027, `#projeto-alfa-cliente`):** o cliente pede o módulo de relatórios; alguém da equipe responde "a gente faz, sem problema". *Use thread*: a resposta fica na thread do pedido.
   - **Desvio 2 (22/01/2027):** mensagem avisando que a integração com o CRM só fica pronta em 12/02, 14 dias depois do marco de 29/01.
   - **Desvio 3 (26/01/2027):** o gestor diz "o João da Nimbus começa amanhã no cliente".
4. **Plante as 5 iscas** (cada uma precisa de um motivo claro, senão confunde até humano):
   1. Pedido de módulo extra **que já tem aditivo assinado** ("o aditivo do módulo de integração foi assinado, podemos seguir")
   2. Prazo remarcado **com aceite formal do cliente**
   3. Pedido do cliente **recusado educadamente** pela equipe
   4. Conversa sobre o módulo de atendimento (**está no escopo**)
   5. "A Carla da Nimbus começa amanhã" (os documentos dela estão em dia)
5. Anote em uma **tabela no comentário da issue** quais mensagens são desvio, qual é isca e por quê: vira insumo do gabarito (J-10).
6. Escreva também as **3 frases da demo** (já definidas na bíblia dos dados) e confira que cada uma, enviada ao vivo, dá o resultado esperado (testar 3 vezes quando o pipeline estiver pronto).

## 🤖 Prompt sugerido
```
Com base no contrato abaixo, gere em JSON (formato de export do Slack: ts, user, text,
thread_ts, channel) 24 mensagens em português informal de um projeto entre 18/01/2027 e
05/02/2027, nos canais projeto-alfa e projeto-alfa-cliente. ts em segundos desde 1970
com decimais, crescente. Autores: U_CLIENTE_01 (Marcos Lima), U_CLIENTE_02 (Patrícia
Souza) e os IDs da equipe que eu informar. Esconda no meio da conversa normal: (1) em
19/01, o cliente pedindo o módulo de relatórios e alguém da equipe aceitando na thread;
(2) em 22/01, um aviso de que a integração com o CRM só fica pronta em 12/02; (3) em
26/01, o gestor dizendo que o João da Nimbus começa amanhã no cliente. Inclua 5 iscas
que parecem desvio mas não são: aditivo já assinado, prazo remarcado com aceite formal,
pedido recusado educadamente, conversa sobre o módulo de atendimento, e "a Carla da
Nimbus começa amanhã". Nunca use as palavras desvio, contrato ou cláusula nas mensagens.
```

## ✅ Pronto quando
- [ ] 22 a 25 mensagens, e o parser do Gabriel (G-03) lê o arquivo sem erro
- [ ] Cada desvio aparece em 1 ou 2 mensagens, sem a palavra "desvio"
- [ ] 5 iscas, cada uma com motivo anotado
- [ ] As 3 frases da demo testadas (depois do pipeline pronto)

## ⚠️ Armadilhas
- Desvio óbvio demais não impressiona; conversa limpa demais não testa o falso alarme.
- Mensagem de bot e de entrada no canal são ignoradas pelo parser, não gaste tempo com elas.
<!-- /issue -->

<!-- issue
id: J-09
title: Reunião com o desvio 4 (arquivo .vtt)
dev: joe
prio: P0
frente: dados
est: 20 min
prazo: 13:30
depende: J-06
-->
## 🎯 Objetivo
Ter a **reunião como fonte**, com a promessa feita fora do contrato (desvio 4). Para hoje, **escreva o `.vtt` direto**. Gravar no Meet e transcrever com faster-whisper fica para o futuro (a transcrição automática erra nomes e números).

## 🪜 Passo a passo
1. Crie **`data/reuniao_alfa.vtt`** com 2 a 3 minutos de reunião de status de 21/01/2027. Formato (o parser do Gabriel, G-09, lê exatamente isto):
   ```
   WEBVTT
   NOTE data: 2027-01-21

   00:00:05.000 --> 00:00:12.000
   <v Marcos Lima>Pessoal, a nossa equipe ainda está com dificuldade de usar o portal.

   00:00:12.500 --> 00:00:20.000
   <v Bruno Siqueira>A gente inclui um treinamento presencial pra equipe de vocês, sem custo.
   ```
   - A linha `NOTE data: AAAA-MM-DD` dá a data da reunião (o parser soma o horário de cada fala a ela).
   - Quem fala vem em `<v Nome>`. Use os **nomes fictícios** do J-07 (comercial = Bruno Siqueira).
2. **A promessa é o desvio 4:** o comercial diz que inclui *treinamento presencial, sem custo*. Ela contradiz `2.2` (fora do escopo) e `7` (uma sessão remota de 2 h). **Mantenha a frase inteira em uma única fala**, sem quebrar entre dois trechos.
3. Misture a promessa com conversa normal (status, próximos passos, dúvidas).
4. Revise nomes e números à mão.

## ✅ Pronto quando
- [ ] `data/reuniao_alfa.vtt` no repositório
- [ ] A frase da promessa aparece inteira, com o nome de quem falou
- [ ] Cabeçalho `NOTE data:` presente

## ⚠️ Armadilhas
- Frase cortada entre dois trechos do `.vtt` some da análise se o parser não juntar (o G-09 junta falas seguidas da mesma pessoa, mas não dependa disso).
<!-- /issue -->

<!-- issue
id: J-10
title: Gabarito: rotular os registros (o que é desvio, tipo, responsável)
dev: joe
prio: P0
frente: dados
est: 30 min
prazo: 14:15
depende: G-03, J-08, J-09
-->
## 🎯 Objetivo
A **resposta certa** para cada registro. O eval (R-08) compara o pipeline com este arquivo e calcula precisão e recall. Sem gabarito, não há prova de qualidade.

## 🪜 Passo a passo
1. Peça ao Gabriel o script **`scripts/gerar_gabarito_base.py`** (entrega do G-03). Ele lê os registros pelo `FileSource` e gera `data/gabarito.json` **pré-preenchido** com todos os ids e `e_desvio: false`. **Nunca digite ids à mão**: eles são hashes e não batem.
2. Para cada registro, o formato é:
   ```json
   {
     "registro_id": "slack:ab12cd...",
     "e_desvio": true,
     "tipo": "escopo_extra",
     "responsavel": "gestor",
     "clausula": "2.2",
     "nota": "Cliente pede módulo de relatórios e a equipe aceita; cláusula 2.2 exclui relatórios"
   }
   ```
   `tipo` ∈ `escopo_extra | prazo_sla | terceiro_sem_documento | promessa_fora_do_contrato | nenhum`.
3. Marque como `e_desvio: true` **os 4 desvios**: a mensagem do pedido aceito (1), o aviso de prazo (2), "o João começa amanhã" (3), a fala da promessa (4). Preencha tipo, responsável (tabela de roteamento), cláusula e uma nota.
4. Nas **iscas**, deixe `e_desvio: false`, `tipo: "nenhum"` e escreva **o motivo** em `nota` ("aditivo já assinado", "aceite formal do cliente" etc.).
5. Os demais registros (conversa normal) ficam `false`/`nenhum`, como o script já gerou.
6. Rode o `python eval/rodar_eval.py` (R-08) assim que existir e corrija o gabarito **se o erro for do gabarito**, não do modelo.

## ✅ Pronto quando
- [ ] Os 4 desvios e as 5 iscas estão no gabarito, com nota
- [ ] Todos os registros do `FileSource` têm uma linha no gabarito
- [ ] O eval roda sem ajuste manual

## ⚠️ Armadilhas
- Id digitado à mão não bate com o do `FileSource`. Use sempre a saída do script.
- Gabarito ambíguo gera "falso erro" no eval. Se até um humano hesita, reescreva a mensagem.
<!-- /issue -->

<!-- issue
id: J-11
title: Premissas do ROI com um gestor de projeto (e um caso real para o gancho)
dev: joe
prio: P0
frente: roi
est: 20 min
prazo: 13:00
depende: nada
-->
## 🎯 Objetivo
Trocar os números de exemplo por **números vindos de quem vive o problema**. Número honesto, marcado como *premissa a validar*, vale mais que número inventado.

## 🪜 Passo a passo
1. Converse com 1 ou 2 gestores de projeto da ETEG (sem pedir dado de cliente) e pergunte:
   1. Em um projeto típico, **quantas vezes entregamos algo fora do contrato** sem cobrar?
   2. **Quantas horas** cada vez custou?
   3. Qual o **custo médio da hora** do time?
   4. Quantos **projetos rodam por ano**?
2. Anote cada número como *"premissa do time, a validar"*, com a data da conversa (25/11/2026).
3. Peça **uma história real, sem nomes**, de feature entregue fora do contrato. Ela vale mais que qualquer estatística e vira o **gancho do pitch** (J-13).
4. Cole os 4 números e a história em um comentário desta issue.

**Números de exemplo (se não houver conversa a tempo):** 20 projetos/ano, 3 desvios não cobrados por projeto (cenário base), 16 h por desvio, R$ 150/h. O mercado ajuda a defender a ordem de grandeza: o PMI mostra que 52% dos projetos têm expansão de escopo e a SPI mede 4,5% de vazamento de receita em serviços profissionais.

## ✅ Pronto quando
- [ ] 4 números anotados, com origem e data
- [ ] 1 história real anonimizada para o gancho
- [ ] Em tudo, a marcação "a validar"

## ⚠️ Armadilhas
- Número sem marcação é desmontado na primeira pergunta do júri.
<!-- /issue -->

<!-- issue
id: J-12
title: Planilha de ROI em 3 cenários (com custo real do Langfuse)
dev: joe
prio: P0
frente: roi
est: 40 min
prazo: 15:30
depende: J-11, R-06
-->
## 🎯 Objetivo
Fechar o pitch com o ROI **na estrutura que o deck exige**: linha de base, ganho, custo de operar, ROI e payback, em três cenários, com as premissas à vista. **Potencial de negócio vale 25 pontos**, o maior peso.

## 🪜 Passo a passo
1. **Fórmula obrigatória:** `ROI = (ganho − custo) ÷ custo`. Payback = implantação ÷ ganho líquido mensal.
2. **Linha de base (perda anual)** = projetos × desvios não cobrados × horas por desvio × valor da hora.
3. **Ganho** = perda × % de desvios capturados a tempo. A captura **nunca passa do recall medido no eval** (R-08). Se o eval der 3 de 4, o otimista cai para 70% no máximo.
4. **Custo de operar** (igual nos três cenários):
   - Modelo de IA: **troque a estimativa pelo custo por registro medido no Langfuse** × volume do mês
   - Infraestrutura: servidor pequeno e observabilidade, se o plano grátis não bastar
   - Pessoas aprovando alertas: alertas por projeto/mês × minutos × valor da hora
   - Sustentação: horas de dev por mês × valor da hora
5. **Implantação** (só ano 1): horas × valor da hora.
6. Três cenários: **conservador** (metade), **base** e **otimista** (uma vez e meia). **Deixe o conservador negativo à vista**: é o que dá credibilidade.
7. Mostre o **ponto de equilíbrio**: com a perda do cenário base, quantos % dos desvios o Radar precisa pegar para pagar implantação e operação.
8. **Não some horas liberadas como dinheiro em caixa.** Escopo não cobrado é *receita recuperada*; retrabalho evitado é *custo evitado*. Misturar os dois é o erro que o próprio deck critica.
9. Exporte `data/premissas.json` (alimenta o cartão de impacto) e deixe a planilha com link no README.

**Referência (números de exemplo, para conferir sua conta):**

| Cenário | Ganho ano 1 | Custo ano 1 | ROI ano 1 | Payback |
|---------|------------:|------------:|----------:|---------|
| Conservador | R$ 21.600 | R$ 39.480 | −45% | Não se paga |
| Base | R$ 72.000 | R$ 39.480 | 82% | 3,2 meses |
| Otimista | R$ 151.200 | R$ 39.480 | 283% | 1,2 mês |

Base: perda de R$ 144.000/ano, custo de operar R$ 27.480 (modelo R$ 5.280 + infra R$ 3.000 + aprovação R$ 12.000 + sustentação R$ 7.200) + implantação R$ 12.000. Ponto de equilíbrio: **27%** dos desvios no ano 1 e **19%** nos anos seguintes.

## ✅ Pronto quando
- [ ] Três cenários com ROI e payback, premissas visíveis e marcadas "a validar"
- [ ] Custo do modelo vem do Langfuse (ou está marcado como estimativa)
- [ ] O mesmo número aparece na planilha e no slide
- [ ] `data/premissas.json` gerado

## ⚠️ Armadilhas
- Contar hora liberada como caixa.
- Deixar o ROI "bonito demais": o cenário conservador negativo é um ponto a favor.
<!-- /issue -->

<!-- issue
id: J-13
title: Roteiro dos 15 minutos e respostas para as perguntas do júri
dev: joe
prio: P0
frente: pitch
est: 40 min
prazo: 14:30
depende: nada
-->
## 🎯 Objetivo
Cada pessoa sabe **o que fala, quando e por quanto tempo**. Pitch: **15 min + 5 de perguntas**, aviso aos 15 e corte aos 20. O que passar dos 15 sai do tempo de perguntas. **Demo ao vivo** no centro e **ROI no fechamento**.

## 🪜 Passo a passo
1. Use este roteiro e **ponha um nome em cada bloco**:

   | Bloco | Tempo | Quem | O que mostrar |
   |-------|-------|------|---------------|
   | 1. Gancho | 0'–1' | Joe | A cena real (J-11): terceiro entra sem o documento exigido, o cliente pede um módulo extra no Slack, ninguém percebe |
   | 2. Dor e público | 1'–2'30 | Joe | Desafio declarado, números do deck (13.813 documentos pendentes, 4.800 terceiros bloqueados, Súmula 331) e a dor da ETEG |
   | 3. Solução | 2'30–3'30 | Joe | A solução numa frase e o antes × depois |
   | 4. Demo ao vivo | 3'30–8'30 | Gabriel nas telas, Ricardo narra as técnicas | Mensagem no Slack → DM → aprovação → os 4 desvios na fila |
   | 5. Por dentro | 8'30–10'30 | Ricardo | RAG e graph engineering: por que resolvem, parâmetros, link do GitHub |
   | 6. Qualidade | 10'30–12' | Ricardo ou Gabriel | Os 4 critérios, cada um com evidência na tela e link |
   | 7. Resultado e ROI | 12'–15' | Joe | 3 cenários, premissas à vista |
   | 8. Perguntas | 15'–20' | Ricardo (técnica) e Joe (negócio) | Respostas curtas, com evidência |

2. **Mínimo de 4 pessoas falando** (exigência da nota de *Time e experimentação*). Somos 3 devs: **convide mais uma pessoa do time** (de outra área) para abrir o gancho ou apresentar o ROI.
3. Escreva a **frase de abertura** do gancho e a **frase de passagem** entre cada bloco.
4. **Dono de cada pergunta do júri**, com resposta de até 30 segundos e uma evidência quando der:

   | Pergunta | Resposta curta |
   |----------|----------------|
   | Quantos alertas são falsos? *(a mais perigosa)* | Mostrar precisão e recall do eval, com as conversas isca |
   | Por que isso é conformidade de terceiros? | Desvio 3 é o motor: obrigação do contrato contra evidência da execução, inclusive o documento do terceiro |
   | E a privacidade das conversas? | O bot só lê os canais do projeto onde foi adicionado, nunca DMs; PII mascarada quando der tempo |
   | Isso não vira vigilância do time? | O alerta é sobre o contrato, não sobre a pessoa: tom neutro, "possível desvio", e um humano decide |
   | Como vira oferta? | Conectores reais no lugar dos arquivos sintéticos e venda para quem gerencia projetos com contrato e terceiros |
   | De onde vem o ROI? | Premissa levantada com um gestor, marcada "a validar", e custo real do Langfuse |
   | Quanto custa rodar em escala? | Custo por registro do Langfuse × volume de mensagens de um projeto por mês |
   | E se o modelo errar? | Nada é registrado sem aprovação humana, e o "não é desvio" volta para o eval |

## ✅ Pronto quando
- [ ] O roteiro tem **nomes** e foi lido pelo time todo
- [ ] Pelo menos 4 pessoas falam
- [ ] Cada pergunta tem dono e resposta ensaiada

## ⚠️ Armadilhas
- Vídeo **não** serve como plano B da demo. Vídeo ou imagem só como apoio à fala.
- Cortar texto: o júri olha a demo, não o slide.
<!-- /issue -->

<!-- issue
id: J-14
title: Os 8 slides (Joe faz 1, 2, 3, 7 e 8)
dev: joe
prio: P0
frente: pitch
est: 60 min
prazo: 16:00
depende: J-13
-->
## 🎯 Objetivo
Slides que **apoiam a demo sem competir com ela**. Ricardo faz os slides 5 e 6 (R-10) e Gabriel o 4 (G-13).

## 🪜 Passo a passo
1. **Uma ideia por slide:**
   1. **Gancho** (uma imagem e uma frase) · *Joe*
   2. **Dor** com os números do deck (13.813 documentos pendentes, 4.800 terceiros bloqueados, Súmula 331) · *Joe*
   3. **Solução** e antes × depois · *Joe*
   4. **Arquitetura** (o diagrama do fluxo) · *Gabriel (G-13)*
   5. **Técnicas:** qual, por que resolve, parâmetros e link do GitHub · *Ricardo (R-10)*
   6. **Critérios de qualidade:** o que foi usado, evidência e link do GitHub · *Ricardo (R-10)*
   7. **ROI:** 3 cenários e premissas · *Joe*
   8. **Como vira produto e oferta:** roadmap com Gmail, Meet, vários projetos; piloto de 60 dias · *Joe*
2. Deixe **espaço reservado** para os prints e links que chegam à tarde.
3. Slide 8, **o pedido em uma frase:** *"Queremos um diretor patrocinador, dois projetos e 40 horas de desenvolvimento para provar, em 60 dias, quanto do escopo não cobrado o Radar recupera."*
4. Se citar estatística do PMI, **diga o ano** no slide (escopo: 2018; comunicação: 2013).

## ✅ Pronto quando
- [ ] 8 slides, com pouco texto
- [ ] Espaços de prints e links preenchidos até 16:00
- [ ] O número do ROI é o mesmo da planilha (J-12) e do cartão de impacto

## ⚠️ Armadilhas
- Slide cheio de texto tira o olho do júri da demo.
<!-- /issue -->

<!-- issue
id: J-15
title: Preparar a conversa com o júri das 15h
dev: joe
prio: P1
frente: pitch
est: 15 min
prazo: 14:45
depende: nada
-->
## 🎯 Objetivo
As conversas com o júri **também formam a impressão sobre Time e experimentação**. A das 11h já passou ou está em curso; foco na das **15h**.

## 🪜 Passo a passo
1. Prepare **3 frases**: o que já roda, o que falta e o próximo passo.
2. Leve **uma pergunta** para o júri, por exemplo: *"o que pesa mais para vocês no ROI?"*.
3. Anote o que o júri disser e ajuste o roteiro (J-13).
4. Cole as anotações da conversa das 11h (se houver) e da das 15h em comentário nesta issue.

## ✅ Pronto quando
- [ ] 3 frases prontas
- [ ] Anotações das duas conversas registradas
<!-- /issue -->

<!-- issue
id: J-16
title: Dois ensaios cronometrados, com o sistema rodando e o plano B
dev: joe
prio: P0
frente: pitch
est: 40 min
prazo: 16:30
depende: todas as P0
-->
## 🎯 Objetivo
Chegar ao palco **sem surpresa de tempo nem de sistema**. Todos participam.

## 🪜 Passo a passo
1. **Ensaio 1 às 15:45**, com o sistema **rodando de verdade** e cronômetro. Anote o que cortar.
2. **Ensaio 2 às 16:15**, já com os cortes. **Teste o plano B**: desligue o Slack no meio e rode o fluxo pelo Streamlit.
3. **Checklist de setup** antes de subir ao palco:
   - [ ] Slack aberto no `#projeto-alfa`, projetado
   - [ ] `slack_bot.py` rodando
   - [ ] Streamlit rodando (`streamlit run app.py`)
   - [ ] Langfuse logado, no projeto certo
   - [ ] Slides na aba certa
   - [ ] `MODO_DEMO=1` com o cache cheio (G-12), por segurança
   - [ ] As 3 frases da demo à mão
4. Ensaie a **frase do momento uau** 3 vezes: *"pode incluir o módulo de relatórios sem custo, a gente resolve"*.

## ✅ Pronto quando
- [ ] As duas versões cabem em 15 minutos
- [ ] O plano B foi testado ao menos uma vez
- [ ] Setup conferido

## ⚠️ Armadilhas
- Não rode o eval no Sonnet durante o ensaio: gasta verba e deixa a demo lenta.
<!-- /issue -->

<!-- issue
id: J-17
title: E-mails .eml reforçando o desvio 2 (se sobrar tempo)
dev: joe
prio: P2
frente: dados
est: 30 min
prazo: 15:00
depende: J-06
-->
## 🎯 Objetivo
Mais uma fonte, reforçando o desvio 2 e trazendo uma isca. **Só se sobrar tempo**: o desvio 2 já aparece no Slack.

## 🪜 Passo a passo
1. Escreva 5 a 8 e-mails entre ETEG e cliente em texto simples (nada de HTML pesado).
2. Um, do gestor ao cliente, confirma a nova data da integração depois do marco de 29/01 (**desvio 2**).
3. Outro traz um prazo remarcado **com aceite formal e aditivo** (**isca**).
4. Gere os arquivos `.eml` com a biblioteca `email` do Python em `data/emails/`.

## ✅ Pronto quando
- [ ] Cada arquivo abre com `email.message_from_file` e tem assunto, remetente, data e corpo
<!-- /issue -->
