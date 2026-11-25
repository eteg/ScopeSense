# Anotações do `slack_export.json` (insumo do gabarito, J-10)

Dados fictícios. A posição é a ordem no arquivo (1 a 25), que é a ordem cronológica. Os ids do gabarito vêm sempre de `scripts/gerar_gabarito_base.py`, nunca digitados à mão.

Classes: **normal** (conversa de projeto), **DESVIO n** (deve gerar alerta), **ISCA n** (parece desvio, mas não é: `e_desvio: false`) e **contexto** (mensagem normal que dá sentido a um desvio ou a uma isca).

Canais: `A` = `projeto-alfa` (interno), `C` = `projeto-alfa-cliente`.

| # | Data (BRT) | Canal | Autor | Texto (resumo) | Classe | Detalhe |
|---|------------|-------|-------|----------------|--------|---------|
| 1 | 18/01 09:05 | A | Helena Prado | Bom dia, entrega da base de conhecimento dia 25 | normal | |
| 2 | 18/01 09:22 | A | Bruno Siqueira | Confirma a demo com o Marcos | normal | |
| 3 | 18/01 15:30 | C | Patrícia Souza | Pede mudar a ordem das colunas da fila do módulo de atendimento | contexto (ISCA 4) | Pedido pequeno, dentro do módulo de atendimento |
| 4 | 18/01 15:52 | C | Helena Prado | Dá sim, é configuração da fila (thread do #3) | **ISCA 4** | Motivo: módulo de atendimento está no escopo (2.1 a), é só configuração dele |
| 5 | 19/01 10:12 | C | Marcos Lima | Pede o módulo de relatórios com painéis | contexto (DESVIO 1) | Sozinho não é desvio, o pedido não obriga ninguém |
| 6 | 19/01 10:41 | C | Bruno Siqueira | "Claro, a gente faz, sem problema" (thread do #5) | **DESVIO 1** | `escopo_extra`, cláusula **2.2** (relatórios fora do escopo; 5.1 e 5.4: só com aditivo), responsável **gestor** |
| 7 | 19/01 10:44 | C | Marcos Lima | "Show, obrigado" (thread do #5) | normal | |
| 8 | 20/01 09:30 | C | Marcos Lima | Pergunta se já podem começar o módulo extra de integração com o estoque | contexto (ISCA 1) | |
| 9 | 20/01 09:48 | C | Helena Prado | "o aditivo do módulo de integração foi assinado, podemos seguir" | **ISCA 1** | Motivo: módulo extra com aditivo já assinado (cláusula 5 cumprida) |
| 10 | 20/01 14:15 | A | Helena Prado | Café da tarde | normal | |
| 11 | 21/01 10:20 | C | Helena Prado | Base de conhecimento remarcada de 25/01 para 28/01, com aceite formal do Marcos | **ISCA 2** | Motivo: prazo remarcado com aceite formal e escrito do cliente (3.2) |
| 12 | 21/01 10:35 | C | Marcos Lima | Confirma a nova data | normal | |
| 13 | 21/01 17:10 | A | Bruno Siqueira | A reunião de status foi boa | normal | |
| 14 | 22/01 09:15 | A | Helena Prado | Homologação voltou? | normal | |
| 15 | 22/01 09:40 | A | Bruno Siqueira | Voltou, a infra reiniciou o serviço | normal | |
| 16 | 22/01 16:20 | C | Bruno Siqueira | Integração com o CRM, prevista para 29/01, só fica pronta em 12/02 | **DESVIO 2** | `prazo_sla`, cláusula **3.1 c / 3.2** (M3 em 29/01 só muda por aditivo ou aceite formal; aviso informal não vale), responsável **comercial** |
| 17 | 22/01 16:31 | C | Marcos Lima | "Entendi, obrigado por avisar" | normal | Não é aceite formal da nova data |
| 18 | 25/01 08:50 | A | Helena Prado | Pede ao Bruno (menção `<@U_PENDENTE_COMERCIAL>`) o resumo da reunião de quinta | normal | Serve para testar a troca de menção por nome |
| 19 | 25/01 09:10 | A | Bruno Siqueira | Manda hoje | normal | |
| 20 | 26/01 09:00 | A | Helena Prado | "o João da Nimbus começa amanhã no cliente" | **DESVIO 3** | `terceiro_sem_documento`, cláusulas **6.1** (ASO do João venceu em 10/11/2026) e **6.4** (falta a guia de FGTS de 01/2027), responsável **administrativo_contratos** |
| 21 | 27/01 10:05 | A | Camila Reis | Lembrete da reunião de acompanhamento em 04/02 | normal | |
| 22 | 28/01 14:00 | C | Patrícia Souza | Pede um aplicativo de celular para abrir chamados | contexto (ISCA 3) | |
| 23 | 28/01 14:22 | C | Helena Prado | Recusa educadamente e oferece pedido formal de mudança (thread do #22) | **ISCA 3** | Motivo: pedido recusado, nada foi prometido (5.3: recusar não é descumprimento) |
| 24 | 02/02 17:30 | A | Helena Prado | "A Carla da Nimbus começa amanhã" | **ISCA 5** | Motivo: os documentos da Carla estão em dia |
| 25 | 05/02 16:45 | A | Helena Prado | Fechamos a semana, bom fim de semana | normal | |

Resumo: 25 mensagens, 3 desvios (#6, #16, #20), 5 iscas (#4, #9, #11, #23, #24) e 17 normais (68%). Os contextos (#3, #5, #8, #22) contam como normais.

Falta no gabarito completo (outras fontes): **DESVIO 4** (reunião de 21/01, `promessa_fora_do_contrato`, cláusulas 2.2 e 7, responsável administrativo_contratos) e as linhas de PDF e e-mail. Entram quando os parsers de `.vtt` (G-09), `.pdf` (G-10) e `.eml` (G-14) existirem.

## Frases da demo (digitadas ao vivo, NÃO estão no arquivo)

| Frase | Esperado |
|-------|----------|
| "pode incluir o módulo de relatórios sem custo, a gente resolve" | Alerta de `escopo_extra` (2.2) para o gestor (frase do momento uau) |
| "o João da Nimbus começa amanhã no cliente" | Alerta de `terceiro_sem_documento` (6.1, 6.4) para administrativo de contratos (frase reserva; também está no arquivo, #20) |
| "o aditivo do módulo de integração foi assinado, podemos seguir" | **Nenhum alerta** (isca ao vivo; também está no arquivo, #9) |
