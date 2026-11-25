"""Registro de fontes: o único lugar que liga uma Origem ao seu adaptador.

Para incluir um canal novo (Gmail, Calendar, Meet):
1. crie ``radar/fontes/<canal>/`` com uma classe que implemente ``Fonte``
   e uma função ``create()`` que leia a configuração do .env;
2. acrescente a fábrica em ``FACTORIES`` abaixo.
O pipeline e a rota genérica ``/fontes/{origem}/registros`` passam a enxergá-lo.
"""

from collections.abc import Callable
from typing import Any

from radar.core.errors import FonteNaoConfigurada
from radar.core.models import Origem
from radar.core.ports import Fonte
from radar.fontes import gmail, slack

FACTORIES: dict[Origem, Callable[[], Fonte]] = {
    Origem.slack: slack.create,
    Origem.email: gmail.create,
}


class FonteRegistry:
    def __init__(self, factories: dict[Origem, Callable[[], Fonte]] | None = None) -> None:
        self._factories = FACTORIES if factories is None else factories
        self._instances: dict[Origem, Fonte] = {}

    def get(self, origem: Origem) -> Fonte:
        if origem not in self._instances:
            factory = self._factories.get(origem)
            if factory is None:
                raise FonteNaoConfigurada(f"A fonte '{origem}' ainda não foi implementada.")
            self._instances[origem] = factory()
        return self._instances[origem]

    def available(self) -> list[dict[str, Any]]:
        """Fontes implementadas e se estão configuradas (sem chamar o serviço externo)."""
        result = []
        for origem in self._factories:
            try:
                self.get(origem)
                result.append({"origem": origem, "configurada": True, "motivo": None})
            except FonteNaoConfigurada as exc:
                result.append({"origem": origem, "configurada": False, "motivo": str(exc)})
        return result

    def all_configured(self) -> list[Fonte]:
        fontes = []
        for origem in self._factories:
            try:
                fontes.append(self.get(origem))
            except FonteNaoConfigurada:
                continue
        return fontes
