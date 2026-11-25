"""Adaptador do Slack para a porta `Fonte`."""

from datetime import UTC, datetime
from typing import Any

from radar.core.errors import AcessoNegado, ForaDoEscopo
from radar.core.models import Consulta, Origem, Registro
from radar.fontes.slack.config import SlackSettings
from radar.fontes.slack.readonly import ReadOnlySlackClient

# Mensagens de sistema que não são evidência do projeto.
IGNORED_SUBTYPES = frozenset({"channel_join", "channel_leave", "channel_purpose", "channel_topic"})
PAGE_SIZE = 200


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
        oldest = str(consulta.desde.timestamp()) if consulta.desde else None
        latest = str(consulta.ate.timestamp()) if consulta.ate else None

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
        if consulta.desde:  # respostas de thread antiga podem vir antes de `desde`
            registros = [r for r in registros if r.data >= consulta.desde]
        registros.sort(key=lambda r: r.data)
        return registros[-consulta.limite :]

    # --- leitura específica do Slack ---------------------------------------

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
        """Mensagens do canal em ordem cronológica (mais antiga primeiro)."""
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
                registros.extend(
                    self.thread_replies(channel_id, message["ts"], include_parent=False)
                )
        return registros

    def thread_replies(
        self, channel_id: str, thread_ts: str, *, include_parent: bool = True
    ) -> list[Registro]:
        self.check_channel(channel_id)
        self._auth_data()
        raw = self._paginate("conversations.replies", {"channel": channel_id, "ts": thread_ts})
        if not include_parent:
            raw = [m for m in raw if m.get("ts") != thread_ts]
        return [self._to_registro(channel_id, m) for m in raw]

    # --- internos ---------------------------------------------------------

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
        return Registro(
            id=f"slack:{channel_id}:{ts}",
            origem=Origem.slack,
            data=datetime.fromtimestamp(float(ts), tz=UTC),
            autor=autor,
            texto=message.get("text", ""),
            link=self._permalink(channel_id, ts, thread_ts),
            metadados={
                "canal": channel_id,
                "ts": ts,
                "thread_ts": thread_ts,
                "autor_id": user_id,
                "respostas": message.get("reply_count", 0),
                "subtipo": message.get("subtype"),
            },
        )
