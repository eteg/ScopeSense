"""ESCRITA no Slack do relatório (botão "Publicar" da tela web).

Separado das fontes, que só leem. Por decisão do time (25/11), usa o token de
USUÁRIO (SLACK_USER_TOKEN): a mensagem sai em nome de quem é dono do token.
Só sabe fazer duas coisas: postar no canal do relatório e responder na thread dela.
"""

import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from radar.core.errors import FalhaNaFonte, FonteNaoConfigurada

LIMITE = 3900  # o Slack corta texto longo; o prompt já pede até 3.500 por mensagem


def _client() -> WebClient:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        raise FonteNaoConfigurada("Defina SLACK_USER_TOKEN no .env para publicar no Slack.")
    return WebClient(token=token)


def _cortar(texto: str) -> list[str]:
    """Garante que nenhuma mensagem passe do limite (quebra em parágrafos)."""
    if len(texto) <= LIMITE:
        return [texto]
    partes, atual = [], ""
    for paragrafo in texto.split("\n\n"):
        if atual and len(atual) + len(paragrafo) + 2 > LIMITE:
            partes.append(atual)
            atual = ""
        atual = f"{atual}\n\n{paragrafo}" if atual else paragrafo
        while len(atual) > LIMITE:
            partes.append(atual[:LIMITE])
            atual = atual[LIMITE:]
    if atual:
        partes.append(atual)
    return partes


def publicar(canal: str, mensagens: list[str]) -> tuple[str, str | None]:
    """Posta a primeira mensagem no canal e as demais na thread dela.

    Devolve (ts da mensagem principal, link para ela).
    """
    client = _client()
    blocos = [p for m in mensagens for p in _cortar(m.strip()) if p.strip()]
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
