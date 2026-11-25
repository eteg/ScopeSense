"""ESCRITA no Slack do relatório (botão "Publicar" da tela web).

Separado das fontes, que só leem. Por decisão do time (25/11), usa o token de
USUÁRIO (SLACK_USER_TOKEN): a mensagem sai em nome de quem é dono do token.
Só sabe fazer uma coisa: postar mensagens no canal do relatório (nunca em thread).
"""

import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from radar.core.errors import FalhaNaFonte, FonteNaoConfigurada

LIMITE = 39_000  # teto do Slack; o prompt pede mensagens bem menores


def _client() -> WebClient:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        raise FonteNaoConfigurada("Defina SLACK_USER_TOKEN no .env para publicar no Slack.")
    return WebClient(token=token)


def _limitar(texto: str) -> str:
    """O Slack aceita até 40 mil caracteres; acima disso corta, sem virar outra mensagem."""
    return texto if len(texto) <= LIMITE else texto[: LIMITE - 1] + "…"


def publicar(canal: str, mensagens: list[str]) -> tuple[str, str | None]:
    """Posta cada mensagem no canal, como mensagens independentes e nesta ordem:
    o resumo e depois uma por responsável. Nenhuma vai em thread: a thread de cada
    mensagem fica livre para o grupo discutir aquele assunto.

    Devolve (ts do resumo, link para ele).
    """
    client = _client()
    blocos = [_limitar(m.strip()) for m in mensagens if m.strip()]
    if not blocos:
        raise FalhaNaFonte("Relatório vazio: nada para publicar.")
    try:
        enviadas = [
            client.chat_postMessage(
                channel=canal, text=bloco, unfurl_links=False, unfurl_media=False
            )["ts"]
            for bloco in blocos
        ]
        link = client.chat_getPermalink(channel=canal, message_ts=enviadas[0]).get("permalink")
    except SlackApiError as exc:
        raise FalhaNaFonte(f"Slack recusou a publicação: {exc.response.get('error')}.") from exc
    return enviadas[0], link
