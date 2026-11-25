@AGENTS.md

# CLAUDE.md · notas específicas do Claude Code

Tudo o que importa (problema, princípios, arquitetura, regras e design) está em `AGENTS.md`, importado acima. Aqui ficam só os pontos próprios do Claude Code.

## Prioridades, em uma linha
**Funcional, rápido e bonito.** Não precisa ficar perfeito. Estética real vem depois, da Lara, e será implementada em cima da estrutura isolada de `radar/ui/` e de `montar_blocos()`.

## Como começar uma sessão
1. Descubra qual issue está em andamento: `gh issue list --assignee @me --state open` (ou olhe o quadro do projeto).
2. Leia o corpo da issue inteiro. Ele já traz passo a passo, código, prompt sugerido e "Pronto quando".
3. Leia `radar/models.py` antes de mexer em qualquer coisa que use `Registro`, `Alerta` ou `Decisao`. Cole-o no contexto quando a issue pedir.
4. Faça o mínimo que fecha o "Pronto quando", teste na hora e siga. Não refatore código que não é da sua issue.

## Hábitos que economizam tempo
- **Peça código pequeno e rode na hora.** Prefira passos curtos a gerar um módulo inteiro de uma vez.
- **Nunca altere `radar/models.py`** sem combinar com o time. Se achar que falta um campo, pare e avise.
- **Antes de escrever uma chamada a biblioteca nova** (LangGraph, Langfuse, Slack Bolt, ChromaDB, API da Anthropic), confira o exemplo da issue e a documentação atual. Dois erros comuns:
  - Langfuse: o import certo é `from langfuse import observe, get_client`, não `langfuse.decorators`.
  - LangGraph: compile com `InMemorySaver`; sem checkpointer a aprovação humana falha.
- **Slack:** `ack()` na primeira linha do handler. Rode o grafo em `threading.Thread`.
- **Windows/PowerShell:** use `py -3.11`, `.venv\Scripts\Activate.ps1`, e `tzdata` instalado para `zoneinfo`.
- **Arquivos de texto em UTF-8.** Contrato, mensagens e README têm acentos.

## O que o Claude Code não deve fazer sem pedir
- Subir (`git push`) direto na `master` quando a issue pede PR, ou reescrever histórico.
- Gravar chave, token ou dado real em qualquer arquivo versionado.
- Criar dependência pesada ou serviço novo fora do que está em `requirements.txt`.
- Mexer na estética (cores, layout, fontes) além do mínimo legível. Isso é do design da Lara.
- Rodar o eval com o Sonnet em loop: gasta a verba (US$ 20 de API para o time inteiro).

## Quando houver dúvida
Escolha a opção **mais simples que funciona na demo de hoje** e registre a dúvida como comentário na issue. A ordem de corte do plano (P2, depois P1) vale para decisões de escopo.
