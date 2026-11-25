"""Adaptador do Slack para a porta `Fonte`."""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from radar.core.errors import AcessoNegado, EntradaInvalida, ForaDoEscopo
from radar.core.models import Consulta, Origem, Registro
from radar.fontes.slack.config import SlackSettings
from radar.fontes.slack.readonly import ReadOnlySlackClient
from radar.fontes.slack.texto import limpar_mencoes

# Mensagens de sistema que não são evidência do projeto.
IGNORED_SUBTYPES = frozenset({"channel_join", "channel_leave", "channel_purpose", "channel_topic"})
PAGE_SIZE = 200
MAX_LIST_PAGES = 50  # até 10 mil canais ao procurar um nome
CHANNEL_ID = re.compile(r"^[CG][A-Z0-9]{8,}$")


class SlackFonte:
    origem = Origem.slack

    def __init__(self, settings: SlackSettings, client: ReadOnlySlackClient | None = None) -> None:
        self.settings = settings
        self._client = client or ReadOnlySlackClient(settings.user_token)
        self._allowed = set(settings.channel_ids)
        self._auth: dict[str, Any] | None = None
        self._user_names: dict[str, str] = {}

    # --- porta Fonte ------------------------------------------------------

    def status(self) -> dict[str, Any]:
        data = self._auth_data()
        scopes = data.get("scopes") or []
        write_scopes = [s for s in scopes if ":write" in s or s.startswith("admin")]
        return {
            **{k: data.get(k) for k in ("team", "team_id", "user", "user_id", "url")},
            "canais": sorted(self._allowed),
            "escopos": scopes,
            "escopos_de_escrita": write_scopes,
            "aviso": (
                "O token tem escopos de escrita. O Radar não os usa, mas o recomendado é "
                "removê-los do app e reinstalar."
                if write_scopes
                else None
            ),
        }

    def fetch(self, consulta: Consulta) -> list[Registro]:
        """Mensagens (com threads) de um canal do projeto, ou de todos se `escopo` vier vazio."""
        channels = [consulta.escopo] if consulta.escopo else sorted(self._allowed)
        desde, ate = self._aware(consulta.desde), self._aware(consulta.ate)
        oldest = str(desde.timestamp()) if desde else None
        latest = str(ate.timestamp()) if ate else None

        registros: list[Registro] = []
        for channel_id in channels:
            registros.extend(
                self.channel_messages(
                    channel_id,
                    oldest=oldest,
                    latest=latest,
                    limit=consulta.limite,
                    include_threads=True,
                )
            )
        # Garantia final de que nada fora do período passa adiante.
        registros = [
            r for r in registros if (not desde or r.data >= desde) and (not ate or r.data <= ate)
        ]
        registros.sort(key=lambda r: r.data)
        return registros[-consulta.limite :]

    # --- leitura específica do Slack ---------------------------------------

    def set_allowed(self, channel_ids: list[str]) -> None:
        """Troca os canais do projeto (vêm da tela de Configurações)."""
        if channel_ids:
            self._allowed = set(channel_ids)

    def resolver_canais(self, refs: list[str]) -> list[dict[str, str]]:
        """Converte "#nome" ou ID em {id, nome}, conferindo que o token enxerga o canal.

        Levanta EntradaInvalida com os canais que não existem ou não são visíveis.
        """
        self._auth_data()
        resolvidos: list[dict[str, str]] = []
        faltando: list[str] = []
        por_nome: dict[str, dict[str, str]] | None = None
        for ref in refs:
            ref = ref.strip()
            if CHANNEL_ID.match(ref):
                try:
                    info = self._client.call("conversations.info", channel=ref)["channel"]
                except AcessoNegado:
                    faltando.append(ref)
                    continue
                resolvidos.append({"id": info["id"], "nome": info.get("name") or ref})
                continue
            if por_nome is None:
                por_nome = self._canais_por_nome()
            canal = por_nome.get(ref.lstrip("#").lower())
            if canal:
                resolvidos.append(canal)
            else:
                faltando.append(ref)
        if faltando:
            raise EntradaInvalida(
                f"Canal não encontrado ou sem acesso no Slack: {', '.join(faltando)}."
            )
        return resolvidos

    def ids_por_nome(self, nomes: list[str]) -> dict[str, str | None]:
        """ID do Slack de cada nome (real_name ou display_name, sem acento e caixa).

        Nome que não bate com ninguém (ou bate com mais de uma pessoa) fica None:
        o relatório escreve o nome em negrito com "(não encontrei no Slack)".
        """
        self._auth_data()
        indice: dict[str, set[str]] = {}
        cursor: str | None = None
        for _ in range(MAX_LIST_PAGES):
            params: dict[str, Any] = {"limit": PAGE_SIZE}
            if cursor:
                params["cursor"] = cursor
            data = self._client.call("users.list", **params)
            for u in data.get("members", []):
                if u.get("deleted") or u.get("is_bot"):
                    continue
                perfil = u.get("profile") or {}
                for nome in (perfil.get("real_name"), perfil.get("display_name"), u.get("name")):
                    if nome:
                        indice.setdefault(_normalizar(nome), set()).add(u["id"])
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
        saida: dict[str, str | None] = {}
        for nome in nomes:
            ids = indice.get(_normalizar(nome), set())
            saida[nome] = next(iter(ids)) if len(ids) == 1 else None
        return saida

    def _canais_por_nome(self) -> dict[str, dict[str, str]]:
        canais: dict[str, dict[str, str]] = {}
        cursor: str | None = None
        for _ in range(MAX_LIST_PAGES):
            params: dict[str, Any] = {
                "types": "public_channel,private_channel",
                "exclude_archived": True,
                "limit": PAGE_SIZE,
            }
            if cursor:
                params["cursor"] = cursor
            data = self._client.call("conversations.list", **params)
            for c in data.get("channels", []):
                canais[c["name"].lower()] = {"id": c["id"], "nome": c["name"]}
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
        return canais

    def check_channel(self, channel_id: str) -> None:
        if channel_id not in self._allowed:
            raise ForaDoEscopo(f"Canal {channel_id} não está em SLACK_CHANNEL_IDS.")

    def list_channels(self) -> list[dict[str, Any]]:
        self._auth_data()
        channels = []
        for channel_id in sorted(self._allowed):
            info = self._client.call("conversations.info", channel=channel_id)["channel"]
            channels.append(
                {
                    "id": info["id"],
                    "nome": info.get("name"),
                    "privado": info.get("is_private", False),
                    "membro": info.get("is_member"),
                    "topico": (info.get("topic") or {}).get("value") or None,
                }
            )
        return channels

    def channel_messages(
        self,
        channel_id: str,
        *,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 100,
        include_threads: bool = False,
    ) -> list[Registro]:
        """Mensagens do canal em ordem cronológica (mais antiga primeiro).

        Com `include_threads`, traz as respostas das threads que caem no período,
        inclusive de threads abertas antes de `oldest` (até `thread_lookback_days`
        antes) que continuaram recebendo respostas dentro do período.
        """
        self.check_channel(channel_id)
        self._auth_data()

        params: dict[str, Any] = {"channel": channel_id}
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        raw = self._paginate("conversations.history", params, limit)

        registros: list[Registro] = []
        for message in reversed(raw):
            if message.get("subtype") in IGNORED_SUBTYPES:
                continue
            registros.append(self._to_registro(channel_id, message))
            if include_threads and message.get("reply_count"):
                registros.extend(self._replies_in_period(channel_id, message, oldest, latest))

        if include_threads and oldest:
            registros.extend(self._older_threads_replies(channel_id, oldest, latest))
        # Resposta enviada "também ao canal" aparece no histórico e na thread.
        unicos = {r.id: r for r in registros}
        return sorted(unicos.values(), key=lambda r: r.data)

    def thread_replies(
        self, channel_id: str, thread_ts: str, *, include_parent: bool = True
    ) -> list[Registro]:
        self.check_channel(channel_id)
        self._auth_data()
        raw = self._paginate("conversations.replies", {"channel": channel_id, "ts": thread_ts})
        if not include_parent:
            raw = [m for m in raw if m.get("ts") != thread_ts]
        return [self._to_registro(channel_id, m) for m in raw]

    def lookup_user(self, email: str) -> dict[str, Any]:
        """ID do Slack a partir do e-mail (para marcar o responsável de cada papel).

        Levanta NaoEncontrado se ninguém no workspace usa esse e-mail.
        """
        self._auth_data()
        user = self._client.call("users.lookupByEmail", email=email)["user"]
        profile = user.get("profile") or {}
        return {
            "id": user["id"],
            "nome": profile.get("display_name") or profile.get("real_name") or user.get("name"),
            "nome_completo": profile.get("real_name"),
            "email": profile.get("email") or email,
            "mencao": f"<@{user['id']}>",
            "ativo": not user.get("deleted", False),
            "bot": user.get("is_bot", False),
        }

    # --- internos ---------------------------------------------------------

    def _aware(self, value: datetime | None) -> datetime | None:
        """Data sem fuso é lida no fuso do projeto (e não no do servidor)."""
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=self.settings.tz)

    def _replies_in_period(
        self, channel_id: str, parent: dict[str, Any], oldest: str | None, latest: str | None
    ) -> list[Registro]:
        """Respostas de uma thread (sem a raiz) com data dentro de [oldest, latest]."""
        replies = self.thread_replies(channel_id, parent["ts"], include_parent=False)
        start = float(oldest) if oldest else None
        end = float(latest) if latest else None
        return [
            r
            for r in replies
            if (start is None or float(r.metadados["ts"]) >= start)
            and (end is None or float(r.metadados["ts"]) <= end)
        ]

    def _older_threads_replies(
        self, channel_id: str, oldest: str, latest: str | None
    ) -> list[Registro]:
        """Threads abertas antes do período que receberam respostas dentro dele.

        `conversations.history` com `oldest` só devolve raízes criadas no período,
        então uma conversa antiga que continua viva ficaria de fora.
        """
        lookback = timedelta(days=self.settings.thread_lookback_days).total_seconds()
        if not lookback:
            return []
        params = {
            "channel": channel_id,
            "oldest": str(float(oldest) - lookback),
            "latest": oldest,
        }
        registros: list[Registro] = []
        for parent in self._paginate("conversations.history", params):
            if (
                parent.get("reply_count")
                and float(parent["ts"]) < float(oldest)
                and float(parent.get("latest_reply") or 0) >= float(oldest)
            ):
                registros.extend(self._replies_in_period(channel_id, parent, oldest, latest))
        return registros

    def _auth_data(self) -> dict[str, Any]:
        """Confere o token e garante que ele é do workspace configurado."""
        if self._auth is None:
            data = self._client.call("auth.test")
            if data.get("team_id") != self.settings.team_id:
                raise AcessoNegado(
                    f"Token do workspace {data.get('team_id')}, "
                    f"mas SLACK_TEAM_ID é {self.settings.team_id}."
                )
            self._auth = data
        return self._auth

    def _paginate(
        self, method: str, params: dict[str, Any], limit: int | None = None
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        cursor: str | None = None
        while limit is None or len(messages) < limit:
            page_size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - len(messages))
            page = {**params, "limit": page_size, **({"cursor": cursor} if cursor else {})}
            data = self._client.call(method, **page)
            messages.extend(data.get("messages", []))
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not data.get("has_more") or not cursor:
                break
        return messages

    def _user_name(self, user_id: str) -> str:
        if user_id not in self._user_names:
            try:
                user = self._client.call("users.info", user=user_id)["user"]
                profile = user.get("profile") or {}
                self._user_names[user_id] = (
                    profile.get("display_name")
                    or profile.get("real_name")
                    or user.get("name")
                    or user_id
                )
            except Exception:  # nome é cosmético; não derruba a leitura
                self._user_names[user_id] = user_id
        return self._user_names[user_id]

    def _permalink(self, channel_id: str, ts: str, thread_ts: str | None) -> str | None:
        base = (self._auth or {}).get("url")
        if not base:
            return None
        link = f"{base.rstrip('/')}/archives/{channel_id}/p{ts.replace('.', '')}"
        if thread_ts and thread_ts != ts:
            link += f"?thread_ts={thread_ts}&cid={channel_id}"
        return link

    def _to_registro(self, channel_id: str, message: dict[str, Any]) -> Registro:
        ts = message["ts"]
        thread_ts = message.get("thread_ts")
        user_id = message.get("user")
        autor = self._user_name(user_id) if user_id else message.get("username") or "bot"
        texto, mencionados = limpar_mencoes(message.get("text", ""), self._user_name)
        return Registro(
            id=f"slack:{channel_id}:{ts}",
            origem=Origem.slack,
            data=datetime.fromtimestamp(float(ts), tz=self.settings.tz),
            autor=autor,
            texto=texto,
            link=self._permalink(channel_id, ts, thread_ts),
            metadados={
                "canal": channel_id,
                "ts": ts,
                "thread_ts": thread_ts,
                "thread_id": thread_ts,  # nome que o Registro do núcleo usa (Registro.thread_id)
                "autor_id": user_id,
                "mencionados": mencionados,
                "respostas": message.get("reply_count", 0),
                "subtipo": message.get("subtype"),
            },
        )


def _normalizar(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().strip().lstrip("@").split())
