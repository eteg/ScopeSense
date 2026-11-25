from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class SlackSettings(BaseSettings):
    """Variáveis SLACK_* do .env (veja .env.example)."""

    model_config = SettingsConfigDict(
        env_prefix="SLACK_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Workspace (grupo) que o Radar pode ler. Tokens de outro workspace são recusados.
    team_id: str = Field(min_length=1)
    # Token de usuário (xoxp-) com escopos só de leitura.
    user_token: str = Field(min_length=1, repr=False)
    # Canais do projeto monitorado. Só eles podem ser lidos.
    channel_ids: Annotated[list[str], NoDecode] = Field(min_length=1)
    mcp_url: str = "https://mcp.slack.com/mcp"

    @field_validator("channel_ids", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
