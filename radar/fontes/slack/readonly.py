"""Cliente da Web API do Slack que só aceita métodos de leitura.

Segunda trava além dos escopos do token: mesmo que alguém dê escopo de escrita
ao app por engano, este cliente recusa qualquer método fora da lista.
"""

import time
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from radar.core.errors import AcessoNegado, EscritaBloqueada, FalhaNaFonte, NaoEncontrado

READ_ONLY_METHODS: frozenset[str] = frozenset(
    {
        "auth.test",
        "conversations.info",
        "conversations.list",  # achar o ID de um canal pelo nome (tela de Configurações)
        "conversations.history",
        "conversations.replies",
        "users.info",
        "users.lookupByEmail",  # achar o ID de quem marcar a partir do e-mail do papel
        "users.list",  # achar o ID de quem marcar no relatório, pelo nome do setup
    }
)

# Erros do Slack que significam falta de permissão, não falha do serviço.
_ACCESS_ERRORS = frozenset(
    {"not_in_channel", "channel_not_found", "missing_scope", "invalid_auth", "not_authed",
     "account_inactive", "token_revoked", "no_permission"}
)  # fmt: skip
_NOT_FOUND_ERRORS = frozenset({"users_not_found", "user_not_found", "thread_not_found"})


# Rede instável: a resposta às vezes chega cortada (IncompleteRead) ou a conexão cai.
# Toda leitura tenta de novo antes de desistir. Erro do Slack (permissão etc.) não repete.
TENTATIVAS = 5
ESPERA_S = 1.5  # espera 1,5 s, 3 s, 4,5 s, 6 s entre as tentativas


class ReadOnlySlackClient:
    def __init__(self, token: str, client: WebClient | None = None) -> None:
        self._client = client or WebClient(token=token, timeout=60)

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        if method not in READ_ONLY_METHODS:
            raise EscritaBloqueada(f"Método Slack '{method}' bloqueado: o Radar só faz leitura.")
        try:
            response = self._com_retentativa(method, params)
        except SlackApiError as exc:
            error = exc.response.get("error")
            if error in _NOT_FOUND_ERRORS:
                raise NaoEncontrado(
                    f"Slack não encontrou o item pedido em '{method}': {error}."
                ) from exc
            if error in _ACCESS_ERRORS:
                raise AcessoNegado(f"Slack recusou '{method}': {error}.") from exc
            raise FalhaNaFonte(f"Slack respondeu erro em '{method}': {error}.") from exc
        except Exception as exc:
            raise FalhaNaFonte(
                f"Falha ao falar com o Slack em '{method}' ({TENTATIVAS} tentativas): {exc}"
            ) from exc
        data: dict[str, Any] = dict(response.data)  # type: ignore[arg-type]
        if method == "auth.test":  # o Slack informa os escopos do token no cabeçalho
            header = {k.lower(): v for k, v in (response.headers or {}).items()}
            raw = header.get("x-oauth-scopes") or ""
            data["scopes"] = sorted(s.strip() for s in raw.split(",") if s.strip())
        return data

    def _com_retentativa(self, method: str, params: dict[str, Any]):
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                return self._client.api_call(method, http_verb="GET", params=params)
            except SlackApiError:
                raise  # o Slack respondeu: repetir não muda nada
            except Exception:
                if tentativa == TENTATIVAS:
                    raise
                time.sleep(ESPERA_S * tentativa)
        raise AssertionError("inalcançável")
