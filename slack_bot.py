"""Radar no Slack ao vivo: escuta o canal, posta o alerta no grupo e trata os botões.

Uso: `python slack_bot.py` (Socket Mode, sem URL pública). Este processo hospeda o grafo inteiro:
`processar` e `retomar` precisam rodar aqui (checkpointer em memória).
"""

import logging
import os
import sys
from collections.abc import Callable, Mapping

from dotenv import load_dotenv

OBRIGATORIAS = ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ALERT_CHANNEL_ID", "ANTHROPIC_API_KEY")
VALORES_DE_EXEMPLO = {"C0000000000"}

log = logging.getLogger("slack_bot")


def variaveis_faltantes(env: Mapping[str, str] | None = None) -> list[str]:
    """Nomes (nunca valores) das variáveis obrigatórias ausentes ou com o valor de exemplo."""
    env = os.environ if env is None else env
    faltantes = []
    for nome in OBRIGATORIAS:
        valor = (env.get(nome) or "").strip()
        if not valor or valor.endswith("...") or valor in VALORES_DE_EXEMPLO:
            faltantes.append(nome)
    return faltantes


def criar_notificador(client, canal: str) -> Callable:
    """Notificador do grafo: posta no canal do projeto marcando o responsável do papel."""
    from radar.slack_alertas import enviar_alerta, usuario_do_papel

    def notificar(alerta, registro) -> None:
        try:
            enviar_alerta(
                client, alerta, registro, canal, usuario_id=usuario_do_papel(alerta.responsavel)
            )
        except Exception:  # noqa: BLE001 - falha no Slack não derruba o grafo
            log.exception("Não consegui postar o alerta de %s", alerta.registro_id)

    return notificar


def main() -> int:
    load_dotenv()  # antes de importar `radar.*` (a configuração lê o ambiente na importação)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    faltantes = variaveis_faltantes()
    if faltantes:
        print(
            "Faltam variáveis no .env (ou ainda com o valor de exemplo): " + ", ".join(faltantes),
            file=sys.stderr,
        )
        return 1

    from slack_bolt.adapter.socket_mode import SocketModeHandler

    from radar import cache_llm, contrato, db, grafo, observabilidade
    from radar.slack_app import criar_app

    db.init_db()
    observabilidade.ativar_langfuse()  # no-op (desligado) sem as chaves do Langfuse no .env
    cache_llm.ativar_cache_sqlite()  # grava sempre; só lê com MODO_DEMO=1
    try:
        total = contrato.indexar_clausulas(contrato.carregar_contrato())
        log.info("Contrato indexado: %s trechos.", total)
    except Exception:  # noqa: BLE001
        log.exception("Não consegui indexar o contrato; o RAG pode estar vazio.")

    app = criar_app()
    grafo.configurar(criar_notificador(app.client, os.environ["SLACK_ALERT_CHANNEL_ID"]))
    log.info("Radar escutando o Slack (Socket Mode). Ctrl+C para sair.")
    try:
        SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    finally:
        observabilidade.flush()  # garante o envio dos últimos traços ao Langfuse
    return 0


if __name__ == "__main__":
    sys.exit(main())
