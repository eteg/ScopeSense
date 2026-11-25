"""App do Slack (G-06 escuta do canal e G-08 botões), Bolt em Socket Mode.

Os handlers do Bolt são FINOS: só chamam `tratar_mensagem` e `tratar_clique`, funções simples
com as dependências injetáveis em `Estado` (`processar`, `retomar`, `agora`, `em_segundo_plano`),
para testar sem rede. `processar` e `retomar` rodam NESTE processo (checkpointer em memória).
Este módulo só LÊ o canal e responde aos cliques; quem escreve o alerta é `slack_alertas`.
"""

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from radar.core.models import Decisao, Registro
from radar.fontes.slack_export import FUSO, carregar_pessoas, mensagem_para_registro
from radar.slack_alertas import CAMINHO_PROJETO, atualizar_apos_decisao
from radar.ui import textos

log = logging.getLogger(__name__)

ACOES = ("aprovar", "descartar", "nao_e_desvio")
TAMANHO_CONTEXTO = 3  # mensagens anteriores enviadas ao grafo


def _em_thread(funcao: Callable[..., Any], *args: Any) -> None:
    threading.Thread(target=funcao, args=args, daemon=True).start()


def _agora() -> datetime:
    return datetime.now(FUSO)


@dataclass
class Estado:
    """Dependências e memória do processo (vistos, cache de nomes, id do bot)."""

    processar: Callable[..., Any] | None = None
    retomar: Callable[..., Any] | None = None
    agora: Callable[[], datetime] = _agora
    em_segundo_plano: Callable[..., Any] = _em_thread
    pessoas: dict[str, str] = field(default_factory=dict)
    vistos: set[str] = field(default_factory=set)
    canais: dict[str, str] = field(default_factory=dict)
    bot_user_id: str | None = None

    def __post_init__(self) -> None:
        # Import tardio: carregar o grafo é pesado e os testes injetam os dois.
        if self.processar is None or self.retomar is None:
            from radar import grafo

            self.processar = self.processar or grafo.processar
            self.retomar = self.retomar or grafo.retomar


def carregar_estado(caminho_projeto: str | Path | None = None, **dependencias: Any) -> Estado:
    """Cria o `Estado` com as pessoas de `projeto_alfa.json` (tolerante se o arquivo faltar)."""
    pessoas: dict[str, str] = {}
    try:
        pessoas = carregar_pessoas(caminho_projeto or CAMINHO_PROJETO)
    except (OSError, ValueError):
        log.warning("projeto_alfa.json não encontrado: autores aparecem pelo ID do Slack.")
    return Estado(pessoas=pessoas, **dependencias)


# --- auxiliares com o cliente do Slack (todos tolerantes a falha) --------------------------


def _id_do_bot(client: Any, estado: Estado) -> str | None:
    """`auth.test` uma vez só; se falhar, tenta de novo na próxima mensagem."""
    if estado.bot_user_id is None:
        try:
            estado.bot_user_id = client.auth_test().get("user_id")
        except Exception:  # noqa: BLE001 - sem o id ainda vale o filtro por bot_id
            log.warning("auth.test falhou; não deu para descobrir o id do bot.")
    return estado.bot_user_id


def _nome_do_canal(client: Any, estado: Estado, canal_id: str) -> str:
    if canal_id not in estado.canais:
        try:
            info = client.conversations_info(channel=canal_id)
            estado.canais[canal_id] = info["channel"]["name"]
        except Exception:  # noqa: BLE001
            return canal_id  # não guarda a falha: tenta de novo depois
    return estado.canais[canal_id]


def _nome_do_usuario(client: Any, estado: Estado, user_id: str | None) -> str | None:
    if not user_id:
        return None
    if user_id not in estado.pessoas:
        try:
            usuario = client.users_info(user=user_id)["user"]
            nome = usuario.get("real_name") or (usuario.get("profile") or {}).get("real_name")
            if not nome:
                return None
            estado.pessoas[user_id] = nome
        except Exception:  # noqa: BLE001
            return None
    return estado.pessoas[user_id]


def _converter(msg: dict, canal_id: str, client: Any, estado: Estado) -> Registro:
    """Mesma função do export (G-03), com o canal pelo nome e o autor resolvido."""
    _nome_do_usuario(client, estado, msg.get("user"))
    nome_canal = _nome_do_canal(client, estado, canal_id)
    return mensagem_para_registro({**msg, "channel": nome_canal}, estado.pessoas)


def _contexto(event: dict, registro: Registro, client: Any, estado: Estado) -> list[Registro]:
    """Até 3 mensagens ANTERIORES (thread, se houver; senão o histórico do canal)."""
    canal_id, ts = event["channel"], str(event["ts"])
    thread_ts = event.get("thread_ts")
    try:
        if thread_ts:
            resposta = client.conversations_replies(channel=canal_id, ts=thread_ts, limit=20)
        else:
            resposta = client.conversations_history(channel=canal_id, limit=4)
        mensagens = resposta.get("messages") or []
    except Exception:  # noqa: BLE001
        log.warning("Não consegui ler o contexto do canal; seguindo sem ele.")
        return []

    anteriores: list[Registro] = []
    for msg in mensagens:
        if msg.get("bot_id") or msg.get("subtype") or not (msg.get("text") or "").strip():
            continue
        if str(msg.get("ts")) == ts:
            continue
        outro = _converter(msg, canal_id, client, estado)
        if outro.data < registro.data and outro.id != registro.id:
            anteriores.append(outro)
    anteriores.sort(key=lambda r: r.data)
    return anteriores[-TAMANHO_CONTEXTO:]


def _rodar_grafo(estado: Estado, registro: Registro, contexto: Sequence[Registro]) -> None:
    try:
        estado.processar(registro, contexto)
    except Exception:  # noqa: BLE001 - um erro no grafo não pode derrubar o bot
        log.exception("Falha ao processar o registro %s", registro.id)


# --- G-06: escuta ------------------------------------------------------------------------


def tratar_mensagem(event: dict, client: Any, estado: Estado) -> Registro | None:
    """Converte a mensagem e dispara o grafo em segundo plano. Devolve o `Registro` ou None."""
    if event.get("bot_id") or event.get("subtype"):
        return None
    if not (event.get("text") or "").strip():
        return None
    canal_id, ts = event.get("channel"), event.get("ts")
    if not canal_id or not ts:
        return None
    if event.get("user") and event.get("user") == _id_do_bot(client, estado):
        return None
    chave = f"{canal_id}:{ts}"
    if chave in estado.vistos:  # o Slack pode reentregar o evento
        return None
    estado.vistos.add(chave)

    registro = _converter(event, canal_id, client, estado)
    try:
        permalink = client.chat_getPermalink(channel=canal_id, message_ts=ts)["permalink"]
        registro = registro.model_copy(update={"link": permalink})
    except Exception:  # noqa: BLE001
        log.warning("Sem permalink para %s; mantendo o link padrão.", chave)
    contexto = _contexto(event, registro, client, estado)
    estado.em_segundo_plano(_rodar_grafo, estado, registro, contexto)
    return registro


def handler_mensagem(estado: Estado) -> Callable[..., None]:
    def ao_receber(event, client):  # noqa: ANN001
        try:
            tratar_mensagem(event, client, estado)
        except Exception:  # noqa: BLE001
            log.exception("Falha ao tratar a mensagem do Slack")

    return ao_receber


# --- G-08: botões ------------------------------------------------------------------------


def _avisar(client: Any, canal: str | None, usuario: str | None, texto: str) -> None:
    """Resposta discreta (só para quem clicou). Falhar aqui não pode estourar."""
    if not canal or not usuario:
        return
    try:
        client.chat_postEphemeral(channel=canal, user=usuario, text=texto)
    except Exception:  # noqa: BLE001
        log.warning("Não consegui avisar o usuário %s no canal %s.", usuario, canal)


def tratar_clique(acao: str, body: dict, client: Any, estado: Estado) -> bool:
    """Monta a `Decisao`, retoma o grafo e troca os botões. True se esta foi a decisão nova."""
    registro_id = body["actions"][0]["value"]
    usuario = body.get("user") or {}
    canal = (body.get("channel") or {}).get("id")
    mensagem = body.get("message") or {}
    quem = (
        _nome_do_usuario(client, estado, usuario.get("id")) or usuario.get("name") or "alguém"
    )
    decisao = Decisao(alerta_id=registro_id, acao=acao, quem=quem, quando=estado.agora())

    try:
        final = estado.retomar(registro_id, decisao)
    except Exception:  # noqa: BLE001
        log.exception("Falha ao retomar o grafo de %s", registro_id)
        _avisar(client, canal, usuario.get("id"), textos.TEXTO_DECISAO_FALHOU)
        return False
    if final is None:  # já decidido (ou o grafo não está pausado neste processo)
        _avisar(client, canal, usuario.get("id"), textos.TEXTO_JA_DECIDIDO)
        return False

    alerta = final.get("alerta") if isinstance(final, dict) else None
    try:
        atualizar_apos_decisao(
            client,
            canal,
            mensagem.get("ts"),
            alerta,
            decisao,
            blocos_originais=mensagem.get("blocks"),
        )
    except Exception:  # noqa: BLE001 - a decisão já foi gravada; só a mensagem não mudou
        log.exception("Decisão gravada, mas não consegui atualizar a mensagem de %s", registro_id)
    return True


def handler_botao(acao: str, estado: Estado) -> Callable[..., None]:
    def ao_clicar(ack, body, client):  # noqa: ANN001
        ack()  # PRIMEIRA instrução: o Slack exige a confirmação em até 3 s
        tratar_clique(acao, body, client, estado)

    return ao_clicar


# --- fábrica -----------------------------------------------------------------------------


def criar_app(token: str | None = None, *, estado: Estado | None = None, **bolt: Any) -> Any:
    """App Bolt com a escuta da mensagem e os 3 botões. `bolt` vai direto ao `App(...)`."""
    import os

    from slack_bolt import App

    estado = estado or carregar_estado()
    app = App(token=token or os.environ["SLACK_BOT_TOKEN"], **bolt)
    app.event("message")(handler_mensagem(estado))
    for acao in ACOES:
        app.action(acao)(handler_botao(acao, estado))
    return app
