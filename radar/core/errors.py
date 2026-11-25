"""Erros comuns a todas as fontes. A API traduz cada um para um status HTTP."""


class RadarError(Exception):
    """Base dos erros do Radar."""


class FonteNaoConfigurada(RadarError):
    """A fonte não tem configuração no .env."""


class AcessoNegado(RadarError, PermissionError):
    """Pedido fora do que o Radar pode ler (conta errada, sem permissão)."""


class EscritaBloqueada(AcessoNegado):
    """Tentativa de operação que não é leitura. O Radar só lê."""


class ForaDoEscopo(AcessoNegado):
    """Pedido fora do projeto monitorado (canal, caixa ou agenda não configurados)."""


class FalhaNaFonte(RadarError):
    """O serviço externo (Slack, Google...) respondeu erro ou não respondeu."""


class SaidaInvalida(RadarError):
    """O modelo não devolveu JSON válido para o schema, mesmo após as novas tentativas."""
