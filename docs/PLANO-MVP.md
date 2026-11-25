# Plano do MVP · Radar de Desvios (25/11/2026)

3 devs, 1 dia. Este documento é a fonte única de **quem faz o quê, até quando e como as peças se encaixam**. O detalhe de cada tarefa está nas issues do GitHub (e em `docs/issues/`).

## 1. O que é o MVP de hoje

> Uma mensagem digitada no Slack vira alerta na DM do responsável, com a cláusula do contrato e a mensagem lado a lado, e o clique em **Aprovar / Descartar / Não é desvio** fica registrado. Os 4 desvios aparecem, as iscas **não** geram alerta, o eval imprime precisão e recall e o Langfuse mostra custo e tempo de cada alerta.

**Definição de pronto do MVP** (tudo ao vivo, sem vídeo):

- [ ] Mensagem nova no `#projeto-alfa` gera DM em menos de 10 s
- [ ] Os 4 desvios plantados são detectados e roteados ao papel certo
- [ ] A DM mostra cláusula (número e trecho) e evidência (autor, data, trecho)
- [ ] Os 3 botões funcionam, ficam registrados e o segundo clique não grava de novo
- [ ] Desvio 3 provado com documento (ASO vencido), e a Carla (documentos em dia) **não** gera alerta
- [ ] `python eval/rodar_eval.py` imprime precisão, recall e alarmes falsos nas iscas
- [ ] Cada alerta tem traço no Langfuse com custo, tokens e latência
- [ ] Saída do modelo sempre passa pelo schema Pydantic (com nova tentativa)
- [ ] Plano B: o mesmo fluxo roda pelo Streamlit com o Slack desligado

## 2. Quem faz o quê

| Dev | Papel no dia | Foco |
|-----|--------------|------|
| **Joe** | Maior autoridade | Tudo que exige permissão ou decisão (Slack admin, chaves, Langfuse, confirmar o desafio, falar com gestor), **dados sintéticos**, ROI, roteiro, slides e ensaios |
| **Ricardo** | Mais técnico | Caminho crítico do **pipeline**: schema, LangGraph, classificação com RAG, aprovação humana, Langfuse, eval |
| **Gabriel** | Dono do repositório | **Ingestão e Slack**: repositório, fontes e parsers, obrigações do contrato, ChromaDB, escuta do canal, DM, botões, Streamlit |

> **Atualização:** não há mais dono fixo por issue. A divisão acima é só a **sugestão inicial** (e o motivo das letras J, R e G nos IDs, que continuam servindo de identificador). As issues estão organizadas em **ondas de paralelização**: veja [ONDAS-PARALELIZACAO.md](ONDAS-PARALELIZACAO.md). Quem estiver livre pega uma issue da menor onda com dependências prontas, se atribui e move o card.

Os 3 trabalham em paralelo desde o minuto zero. Quem terminar antes **puxa** a próxima issue `P0` livre do quadro, depois as `P1`.

## 3. Marcos do dia

| Hora | Marco | Quem entrega |
|------|-------|--------------|
| **11:55** | Repo no ar, `models.py` congelado, chaves distribuídas, Slack de teste criado | Gabriel, Ricardo, Joe |
| **12:30** | Contrato pronto e 10 mensagens do Slack com o desvio 1 | Joe |
| **13:30** | Busca de cláusula funcionando (RAG) e grafo rodando com nós de teste | Gabriel, Ricardo |
| **14:00** | **Desvio 1 de ponta a ponta:** mensagem no Slack → classificação → DM | todos |
| **15:00** | Os 4 desvios no pipeline, botões funcionando, eval rodando, Langfuse ligado | todos |
| **15:30** | **Features congeladas.** Daqui em diante só correção de bug e evidência | todos |
| **15:45** | Ensaio 1 cronometrado, com o sistema rodando de verdade | todos |
| **16:15** | Ensaio 2, já com os cortes, testando o plano B (Slack desligado) | todos |
| **16:30** | **Código congelado.** Prints e links do GitHub no README e nos slides | todos |

> A conversa das 11h com o júri já está em curso ou passou. Foco na das **15h** (issue J-15).

## 4. Caminho crítico (onde o dia pode travar)

```
R-01 models  ──►  G-02 Fonte ──► G-03 parser Slack ──► G-06 escuta ──┐
     │                                                                ├─► G-07 DM ─► G-08 botões
     ├──►  G-04 obrigações ─► G-05 ChromaDB ─► R-03 classificar ──────┤
     └──►  R-02 grafo ─► R-04 aprovação ─────────────────────────────┘
J-06 contrato ─► G-04            J-08 mensagens ─► G-03 / R-08 eval
```

- **R-01 (schema) bloqueia todo mundo.** Ricardo faz primeiro; todos revisam em 5 minutos e **congela**.
- **R-03 (classificar)** pode começar com uma busca falsa (mock) enquanto o G-05 não termina.
- **G-06/G-07 (Slack)** dependem do app criado pelo Joe (J-02). Se o Slack atrasar, o plano B (Streamlit, G-11) mantém o time andando.

## 5. Contratos entre as frentes (assinaturas que não mudam sem avisar)

| Módulo | Dono | Assinatura |
|--------|------|------------|
| `radar/models.py` | Ricardo | `Registro`, `SaidaClassificacao`, `Alerta`, `Obrigacao`, `Decisao`, `DocumentoExtraido`, enums `Origem`, `TipoDesvio`, `Papel`, `Acao` |
| `radar/llm.py` | Ricardo | `chamar_estruturado(modelo, system, user, schema, temperatura=0.0) -> BaseModel` (já com nova tentativa e contador de saídas inválidas) |
| `radar/fontes/base.py` | Gabriel | `class Fonte(Protocol): fetch(desde=None) -> list[Registro]`; `FileSource(pasta)`; `contexto_de(registros, registro, n=3) -> list[Registro]` |
| `radar/contrato.py` | Gabriel | `dividir_clausulas(md)`, `extrair_obrigacoes(clausulas)`, `indexar_clausulas(...)`, `buscar(texto, k=3) -> list[dict]` com `numero`, `texto`, `tipo`, `distancia` |
| `radar/documentos.py` | Gabriel | `carregar_documentos() -> list[DocumentoExtraido]` |
| `radar/roteamento.py` | Ricardo | `PAPEL_POR_TIPO`, `decidir_acao(alerta) -> Acao` (`dm`, `resumo`, `descartar`) |
| `radar/pipeline.py` | Ricardo | `analisar(registro, contexto=()) -> Alerta \| None` (sem aprovação humana; é o que o **eval** chama) |
| `radar/grafo.py` | Ricardo | `configurar(notificador)`, `processar(registro, contexto=()) -> dict`, `retomar(registro_id, decisao) -> dict \| None` |
| `radar/slack_alertas.py` | Gabriel | `enviar_alerta(client, alerta, registro, usuario_id)` |

O `notificador` é o elo entre o grafo e o Slack: `Callable[[Alerta, Registro], None]`. O Ricardo chama no nó `rotear`; o Gabriel injeta a função que manda a DM (`grafo.configurar(notificador=...)`). Assim as duas frentes andam sem esperar uma pela outra.

## 6. Bíblia dos dados (todo mundo usa os mesmos fatos)

Para contrato, mensagens, reunião, documentos e gabarito baterem entre si:

| Item | Valor |
|------|-------|
| Projeto | **Projeto Alfa**, portal de atendimento, 12 semanas, 01/12/2026 a 23/02/2027 |
| Contratante / contratada | Distribuidora Boreal / ETEG |
| Terceiro | **Nimbus Serviços** (pessoas: **João Teixeira** com ASO vencido, **Carla Mota** com documentos em dia) |
| Cláusulas | `1` Objeto · `2.1` Módulos incluídos (atendimento, base de conhecimento, integração com CRM) · `2.2` Fora do escopo (**módulo de relatórios**, **treinamento presencial**) · `3` Prazos e marcos · `4` SLA · `5` Mudança de escopo só por **aditivo assinado** · `6.1` ASO válido na data de início · `6.2` NDA assinado · `6.3` Treinamento de segurança · `6.4` Guia de FGTS do mês e certidão negativa antes do início · `7` Treinamento: **uma sessão remota de 2 h** · `8` Preço · `9` Confidencialidade e LGPD |
| Marcos (cláusula 3) | M1 Atendimento no ar 22/12/2026 · M2 Base de conhecimento 25/01/2027 · **M3 Integração com CRM 29/01/2027** · Go-live 23/02/2027 |
| Desvio 1 (escopo) | 19/01/2027, `#projeto-alfa-cliente`: cliente pede o **módulo de relatórios**; alguém da equipe: "a gente faz, sem problema" |
| Desvio 2 (prazo) | 22/01/2027: aviso de que a integração com o CRM só fica pronta em **12/02/2027** (14 dias depois do marco M3) |
| Desvio 3 (terceiro) | 26/01/2027: gestor avisa "o João da Nimbus começa amanhã no cliente". ASO do João válido até **10/11/2026**. Lista de documentos da Nimbus **sem a guia de FGTS** de 01/2027 |
| Desvio 4 (promessa) | Reunião de 21/01/2027: comercial diz "a gente inclui um treinamento presencial pra equipe de vocês, sem custo" (cláusulas 2.2 e 7 contradizem) |
| Iscas | (1) pedido de módulo extra **já com aditivo assinado** · (2) prazo remarcado **com aceite formal do cliente** · (3) pedido do cliente **recusado educadamente** · (4) conversa sobre o módulo de atendimento (**dentro do escopo**) · (5) "A Carla da Nimbus começa amanhã" (documentos em dia) |
| Roteamento | `escopo_extra` → gestor · `prazo_sla` → comercial · `terceiro_sem_documento` → administrativo de contratos · `promessa_fora_do_contrato` → administrativo de contratos |
| Frase do momento uau | "pode incluir o módulo de relatórios sem custo, a gente resolve" |
| Frase reserva | "o João da Nimbus começa amanhã no cliente" |
| Isca ao vivo | "o aditivo do módulo de integração foi assinado, podemos seguir" (**não** pode alertar) |

Tudo fictício. Nada de nome real de colega ou cliente. CPF só via Faker.

## 7. Combinados de trabalho

- **Issue = branch.** `git switch -c G-04-obrigacoes`. PR pequeno; quem abriu mescla depois de 1 olhada rápida de outro dev. Em atraso, vale commit direto na `master` **desde que a `master` continue rodando**.
- **`radar/models.py` está congelado depois das 11:55.** Mudança só com aviso no canal e OK do Ricardo.
- **Um arquivo por nó do grafo** em `radar/nos/`. Ninguém edita o arquivo do outro.
- **Segredos:** só no `.env` (já no `.gitignore`). Chave vazada, revoga na hora.
- **Atualize o status no quadro** ao começar (Em andamento), ao abrir PR (Em revisão) e ao terminar (Pronto). Bloqueado? Comenta na issue marcando quem destrava.
- **Guarde prints dos melhores prompts** do vibe coding. Conta em *Time e experimentação*.

## 8. Se atrasar: ordem de corte

Corte **de baixo para cima**, nunca o que está em P0 de cima:

1. `P2`: parser de e-mail, triagem com Haiku, cartão de impacto, aba de execução.
2. `P1`: cache da demo (G-12), proteção extra contra injeção (R-09), Streamlit completo (deixe só o campo "simular mensagem").
3. **Desvio 3 com PDF** vira desvio 3 só por mensagem **somente se** o G-10 não ficar pronto até 14:45. Preferência é manter: é a ponte com o desafio declarado.
4. **Reunião (.vtt)** vira a promessa dita no Slack, se o G-09 atrasar.

O que **não** se corta: Slack ao vivo com DM e botões, RAG, grafo com aprovação humana, eval, Langfuse e ROI com premissas na tela.

## 9. Colunas do quadro (campo Situação)

| Situação | Significa |
|----------|-----------|
| 📥 Backlog | Existe, mas ainda não é a vez |
| 🎯 A fazer | Pronto para pegar: dependências resolvidas |
| 🚧 Em andamento | Alguém está nisso agora |
| 🔍 Em revisão | PR aberto ou esperando conferência |
| ⛔ Bloqueado | Esperando outra pessoa (comente quem) |
| ✅ Pronto | Todos os itens de "Pronto quando" marcados |

Prioridades: **P0** sem isso a demo não roda · **P1** sobe a nota · **P2** só se sobrar tempo.
