"""ESCRITA no Slack do relatório (botão "Publicar" da tela web).

Separado das fontes, que só leem. Publica pelo BOT do app (SLACK_BOT_TOKEN, xoxb-,
escopos chat:write e chat:write.customize): as mensagens saem como "Radar de Desvios".
O bot precisa ter sido convidado para o canal (/invite). Sem token de bot, usa o token
de usuário (SLACK_USER_TOKEN) e a mensagem sai em nome do dono dele.
Só sabe fazer uma coisa: postar mensagens no canal do relatório (nunca em thread).
"""

import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from radar.core.errors import FalhaNaFonte, FonteNaoConfigurada

LIMITE = 39_000  # teto do Slack; o prompt pede mensagens bem menores


NOME_BOT = "Radar de Desvios"
ICONE_BOT = ":satellite_antenna:"


def _client() -> tuple[WebClient, bool]:
    """(cliente, é_bot). Prefere o bot; sem ele, o token de usuário."""
    bot = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if bot.startswith("xoxb-"):
        return WebClient(token=bot, timeout=60), True
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        raise FonteNaoConfigurada(
            "Defina SLACK_BOT_TOKEN (ou SLACK_USER_TOKEN) no .env para publicar no Slack."
        )
    return WebClient(token=token, timeout=60), False


def _limitar(texto: str) -> str:
    """O Slack aceita até 40 mil caracteres; acima disso corta, sem virar outra mensagem."""
    return texto if len(texto) <= LIMITE else texto[: LIMITE - 1] + "…"


def publicar(canal: str, mensagens: list[str | dict]) -> tuple[str, str | None]:
    """Posta cada mensagem no canal, como mensagens independentes e nesta ordem:
    o resumo e depois uma por responsável. Nenhuma vai em thread: a thread de cada
    mensagem fica livre para o grupo discutir aquele assunto.

    Cada mensagem é um texto (mrkdwn) ou um dict Block Kit com "text" (fallback das
    notificações), "blocks" e "attachments" (a barra colorida de cada ponto).
    Devolve (ts da primeira mensagem, link para ela).
    """
    client, e_bot = _client()
    # Bot com chat:write.customize: nome e ícone do Radar em cada mensagem.
    identidade = {"username": NOME_BOT, "icon_emoji": ICONE_BOT} if e_bot else {}
    pedidos = []
    for m in mensagens:
        if isinstance(m, str):
            if m.strip():
                pedidos.append({"text": _limitar(m.strip())})
        else:
            pedidos.append({
                "text": _limitar(m.get("text") or "Radar de Desvios"),
                "blocks": m.get("blocks") or None,
                "attachments": m.get("attachments") or None,
            })  # fmt: skip
    if not pedidos:
        raise FalhaNaFonte("Relatório vazio: nada para publicar.")
    try:
        enviadas = [
            client.chat_postMessage(
                channel=canal,
                unfurl_links=False,
                unfurl_media=False,
                **identidade,
                **{k: v for k, v in pedido.items() if v is not None},
            )["ts"]
            for pedido in pedidos
        ]
    except SlackApiError as exc:
        erro = exc.response.get("error")
        if e_bot and erro in ("channel_not_found", "not_in_channel"):
            raise FalhaNaFonte(
                "O bot do Radar não está no canal. No Slack, digite /invite @ e o nome do app "
                "no canal do projeto e publique de novo."
            ) from exc
        raise FalhaNaFonte(f"Slack recusou a publicação: {erro}.") from exc
    try:
        link = client.chat_getPermalink(channel=canal, message_ts=enviadas[0]).get("permalink")
    except SlackApiError:
        link = None  # a mensagem já foi; só o link "Ver no Slack" fica de fora
    return enviadas[0], link
