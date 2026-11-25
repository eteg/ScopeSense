"""Geração do relatório em segundo plano, com o progresso de cada etapa.

Em memória (uma API local, poucas tarefas): se a API reiniciar, a tarefa some e a
tela pede para gerar de novo. O relatório pronto fica no SQLite como sempre.
"""

import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

ETAPAS = [
    ("slack", "Slack"),
    ("gmail", "Gmail"),
    ("contrato", "Contrato"),
    ("pessoas", "Responsáveis"),
    ("analise", "Análise com IA"),
]


@dataclass
class Etapa:
    chave: str
    titulo: str
    status: str = "pendente"  # pendente | andamento | ok | erro
    detalhe: str | None = None


@dataclass
class Tarefa:
    id: str
    etapas: list[Etapa] = field(default_factory=lambda: [Etapa(c, t) for c, t in ETAPAS])
    relatorio_id: int | None = None
    erro: str | None = None

    @property
    def concluida(self) -> bool:
        return self.relatorio_id is not None or self.erro is not None

    def para_dict(self) -> dict:
        return {**asdict(self), "concluida": self.concluida}


_tarefas: dict[str, Tarefa] = {}
_trava = threading.Lock()


def iniciar(trabalho: Callable[[Callable[[str, str, str | None], None]], int]) -> Tarefa:
    """Roda `trabalho(etapa)` numa thread; `etapa(chave, status, detalhe)` atualiza a tarefa."""
    tarefa = Tarefa(id=uuid.uuid4().hex)
    with _trava:
        _tarefas[tarefa.id] = tarefa

    def etapa(chave: str, status: str, detalhe: str | None) -> None:
        with _trava:
            for e in tarefa.etapas:
                if e.chave == chave:
                    e.status, e.detalhe = status, detalhe

    def rodar() -> None:
        try:
            relatorio_id = trabalho(etapa)
            with _trava:
                tarefa.relatorio_id = relatorio_id
        except Exception as exc:  # noqa: BLE001 - o erro vai para a tela, não derruba a API
            with _trava:
                for e in tarefa.etapas:
                    if e.status == "andamento":
                        e.status, e.detalhe = "erro", str(exc)
                tarefa.erro = str(exc)

    threading.Thread(target=rodar, daemon=True, name=f"relatorio-{tarefa.id[:8]}").start()
    return tarefa


def obter(tarefa_id: str) -> Tarefa | None:
    with _trava:
        return _tarefas.get(tarefa_id)
