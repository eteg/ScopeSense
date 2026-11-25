from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class SlackSettings(BaseSettings):
    """Variáveis SLACK_* do .env (veja .env.example)."""

    model_config = SettingsConfigDict(
        env_prefix="SLACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Workspace (grupo) que o Radar pode ler. Tokens de outro workspace são recusados.
    team_id: str = Field(min_length=1)
    # Token de usuário (xoxp-) com escopos só de leitura.
    user_token: str = Field(min_length=1, repr=False)
    # Canais do projeto monitorado. Só eles podem ser lidos.
    channel_ids: Annotated[list[str], NoDecode] = Field(min_length=1)
    mcp_url: str = "https://mcp.slack.com/mcp"
    # Fuso do projeto. As datas dos Registros saem nele (e não em UTC), para que
    # "madrugada" e "fim de semana" façam sentido. Vale para todas as fontes.
    timezone: str = Field(default="America/Sao_Paulo", validation_alias="RADAR_TIMEZONE")
    # Quantos dias antes do início do período procurar threads que receberam
    # respostas dentro do período (a raiz é antiga, mas a conversa é nova).
    thread_lookback_days: int = Field(default=30, ge=0, le=365)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"fuso inválido: {value}") from exc
        return value

    @field_validator("channel_ids", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
