@AGENTS.md

# CLAUDE.md · notas específicas do Claude Code

Tudo o que importa (problema, princípios, arquitetura, regras e design) está em `AGENTS.md`, importado acima. Aqui ficam só os pontos próprios do Claude Code.

## Prioridades, em uma linha
**Funcional, rápido e bonito.** Não precisa ficar perfeito. Estética real vem depois, da Lara, e será implementada em cima da estrutura isolada de `radar/ui/` e de `montar_blocos()`.

## Ondas de paralelização (leia antes de escolher o que fazer)
**Leia [docs/ONDAS-PARALELIZACAO.md](docs/ONDAS-PARALELIZACAO.md).** As 43 issues estão divididas em **8 ondas**: tudo dentro de uma onda roda ao mesmo tempo, e uma onda só depende das anteriores. **Não há dono fixo por pessoa**: quem estiver livre pega uma issue, se atribui e move o card para 🚧 Em andamento.

- **Escolha a issue da menor onda cujas dependências já estejam prontas.** No GitHub, cada issue tem a label `onda:N` e o card tem o campo **Onda**.
- **Não espere a onda anterior fechar inteira:** se faltar pouco, comece com um *mock* (a seção 3 do documento lista qual mock usar em cada issue).
- Prefira os **gargalos do caminho crítico** (R-01 `models.py`, J-06 contrato, G-04 → G-05 → R-03) antes de P1 e P2.
- Antes de pegar uma issue, confira no quadro se ninguém já está nela (👤 atribuída ou 🚧 em andamento).
- Para ver só o que está livre agora: `gh issue list --label onda:1 --state open --json number,title,assignees`.

## Como começar uma sessão
1. Descubra o que está livre: olhe o quadro ou use `gh issue list --label onda:1 --state open` (troque pelo número da onda). Atribua a issue a você antes de começar.
2. Leia o corpo da issue inteiro. Ele já traz passo a passo, código, prompt sugerido e "Pronto quando".
3. Leia `radar/core/models.py` antes de mexer em qualquer coisa que use `Registro`, `Alerta` ou `Decisao`. Cole-o no contexto quando a issue pedir.
4. Faça o mínimo que fecha o "Pronto quando", teste na hora e siga. Não refatore código que não é da sua issue.

## Hábitos que economizam tempo
- **Peça código pequeno e rode na hora.** Prefira passos curtos a gerar um módulo inteiro de uma vez.
- **Nunca altere `radar/core/models.py`** sem combinar com o time. Se achar que falta um campo, pare e avise.
- **Antes de escrever uma chamada a biblioteca nova** (LangGraph, Langfuse, Slack Bolt, ChromaDB, API da Anthropic), confira o exemplo da issue e a documentação atual. Dois erros comuns:
  - Langfuse: o import certo é `from langfuse import observe, get_client`, não `langfuse.decorators`.
  - LangGraph: compile com `InMemorySaver`; sem checkpointer a aprovação humana falha.
- **Slack:** `ack()` na primeira linha do handler. Rode o grafo em `threading.Thread`.
- **Windows/PowerShell:** use `py -3.12`, `.venv\Scripts\Activate.ps1`, e `tzdata` instalado para `zoneinfo`.
- **Arquivos de texto em UTF-8.** Contrato, mensagens e README têm acentos.

## O que o Claude Code não deve fazer sem pedir
- Subir (`git push`) direto na `master` quando a issue pede PR, ou reescrever histórico.
- Gravar chave, token ou dado real em qualquer arquivo versionado.
- Criar dependência pesada ou serviço novo fora do que está em `requirements.txt`.
- Mexer na estética (cores, layout, fontes) além do mínimo legível. Isso é do design da Lara.
- Rodar o eval com o Sonnet em loop: gasta a verba (US$ 20 de API para o time inteiro).

## Quando houver dúvida
Escolha a opção **mais simples que funciona na demo de hoje** e registre a dúvida como comentário na issue. A ordem de corte do plano (P2, depois P1) vale para decisões de escopo.
