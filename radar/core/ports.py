"""Contrato (porta) que todo canal implementa. O pipeline só conhece este contrato."""

from typing import Any, Protocol, runtime_checkable

from radar.core.models import Consulta, Origem, Registro


@runtime_checkable
class Fonte(Protocol):
    """Uma fonte de evidências do projeto (Slack, Gmail, Calendar, Meet...).

    Regras para quem implementa:
    - só LEITURA; nunca envia, altera ou apaga nada no canal;
    - só devolve o que pertence ao projeto monitorado (canais, envolvidos, marcadores);
    - traduz erros do SDK do canal para os erros de ``radar.core.errors``.
    """

    origem: Origem

    def status(self) -> dict[str, Any]:
        """Confere a conexão (conta, workspace, escopo configurado)."""
        ...

    def fetch(self, consulta: Consulta) -> list[Registro]:
        """Registros do projeto em ordem cronológica."""
        ...
