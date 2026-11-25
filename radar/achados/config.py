from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AchadosSettings(BaseSettings):
    """Variáveis RADAR_* do .env para o banco de achados."""

    model_config = SettingsConfigDict(
        env_prefix="RADAR_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Arquivo SQLite com achados e decisões. Fica fora do Git (.data/).
    db_path: str = ".data/radar.db"
    # PDFs enviados pela tela de Configurações. Também fora do Git.
    arquivos_dir: str = ".data/arquivos"
    # Nome do projeto monitorado; os achados novos são gravados com ele.
    projeto: str = "Projeto demo"
    cliente: str | None = None
    # Canal onde o relatório aprovado será publicado (a publicação ainda não existe).
    canal_slack: str | None = None
    # Premissa para o "custo evitado": horas estimadas x valor da hora.
    valor_hora: float = Field(default=200, ge=0)
    # Responsável por papel (nome como aparece no Slack). O papel decide quem recebe.
    # São só o valor inicial: depois de salvar na tela de Configurações, vale o banco.
    gestor: str | None = None
    comercial: str | None = None
    adm_contratos: str | None = None
