"""Limpa o texto das mensagens do Slack antes de virar evidência.

O texto cru traz menções no formato do Slack (`<@U123>`, `<!channel>`,
`<!subteam^S1|@time>`). Se um trecho desses for citado literalmente no
relatório, o Slack notifica a pessoa, o grupo ou o canal inteiro. Por isso
toda menção vira texto simples (`@Ana`, `@channel`) e os IDs dos usuários
mencionados vão para os metadados, onde servem de dado sem notificar ninguém.

As entidades `&lt;`, `&gt;` e `&amp;` ficam como estão: desfazê-las
transformaria um `&lt;!channel&gt;` escrito por alguém numa menção de verdade.
"""

import re
from collections.abc import Callable

# <@U123>, <@U123|ana>, <!channel>, <!subteam^S123|@time>, <!date^...|fallback>, <#C123|geral>
_ENTITY = re.compile(r"<([@#!])([^>|]+)(?:\|([^>]*))?>")
_BROADCASTS = {"channel", "here", "everyone"}


def limpar_mencoes(texto: str, user_name: Callable[[str], str]) -> tuple[str, list[str]]:
    """Devolve (texto sem menções que notificam, IDs dos usuários mencionados)."""
    mencionados: list[str] = []

    def troca(match: re.Match[str]) -> str:
        tipo, alvo, rotulo = match.group(1), match.group(2), match.group(3)
        if tipo == "@":
            if alvo not in mencionados:
                mencionados.append(alvo)
            return f"@{user_name(alvo)}"
        if tipo == "#":
            return f"#{rotulo or alvo}"
        # tipo "!": aviso ao canal, grupo de usuários, data formatada...
        if alvo in _BROADCASTS:
            return f"@{alvo}"
        if alvo.startswith("subteam^"):
            nome = (rotulo or alvo.removeprefix("subteam^")).lstrip("@")
            return f"@{nome}"
        return rotulo or alvo.split("^", 1)[0]

    return _ENTITY.sub(troca, texto), mencionados
