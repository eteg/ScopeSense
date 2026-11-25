"""Gera a credencial do Gmail com refresh token (só leitura). Rodar uma vez:

    python -m radar.fontes.gmail.autorizar

Pré-requisito: um cliente OAuth do tipo "App para computador" (Desktop) no
Google Cloud, com a Gmail API ativada, salvo em GMAIL_CLIENT_SECRET_FILE.
Abre o navegador, você entra com a conta que será monitorada e aprova o
acesso de leitura. O token fica em GMAIL_TOKEN_FILE (fora do Git).

Não precisa de GMAIL_PARTICIPANTS nem do filtro do projeto: só da credencial.
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from pydantic import ValidationError

from radar.config_errors import describe_validation_error
from radar.fontes.gmail.config import GMAIL_SCOPES, GmailAuthSettings


def main() -> int:
    try:
        settings = GmailAuthSettings()
    except ValidationError as exc:
        print(f"Configuração inválida no .env: {describe_validation_error(exc, 'GMAIL_')}")
        return 1
    if not settings.client_secret_file.exists():
        print(
            f"Arquivo do cliente OAuth não encontrado: {settings.client_secret_file}\n"
            "Baixe o JSON do cliente OAuth (Desktop) no Google Cloud e salve nesse caminho."
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(settings.client_secret_file), GMAIL_SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    settings.token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.token_file.write_text(creds.to_json())
    settings.token_file.chmod(0o600)
    print(f"Credencial salva em {settings.token_file} (escopo: {', '.join(GMAIL_SCOPES)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
