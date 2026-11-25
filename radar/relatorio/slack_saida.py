"""ESCRITA no Slack do relatório (botão "Publicar" da tela web).

Separado das fontes, que só leem. Por decisão do time (25/11), usa o token de
USUÁRIO (SLACK_USER_TOKEN): a mensagem sai em nome de quem é dono do token.
Só sabe fazer duas coisas: postar no canal do relatório e responder na thread dela.
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
    """Posta a primeira mensagem no canal e cada uma das demais como UMA resposta na
    thread dela (uma por responsável; nada é quebrado em várias respostas).

    Devolve (ts da mensagem principal, link para ela).
    """
    client = _client()
    blocos = [_limitar(m.strip()) for m in mensagens if m.strip()]
    if not blocos:
        raise FalhaNaFonte("Relatório vazio: nada para publicar.")
    try:
        principal = client.chat_postMessage(
            channel=canal, text=blocos[0], unfurl_links=False, unfurl_media=False
        )
        ts = principal["ts"]
        for resposta in blocos[1:]:
            client.chat_postMessage(
                channel=canal, thread_ts=ts, text=resposta, unfurl_links=False, unfurl_media=False
            )
        link = client.chat_getPermalink(channel=canal, message_ts=ts).get("permalink")
    except SlackApiError as exc:
        raise FalhaNaFonte(f"Slack recusou a publicação: {exc.response.get('error')}.") from exc
    return ts, link
