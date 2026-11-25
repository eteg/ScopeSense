"""Regras da configuração do projeto, sem FastAPI.

O ponto de partida é o `data/projeto_alfa.json` da demo (nome, cliente, canais e
pessoas por papel). Depois que a tela de Configurações salva, vale o banco.
"""

import json
from collections.abc import Callable
from pathlib import Path

from radar.core.models import Papel
from radar.projeto.models import CanalSlack, ConfigPedido, Pessoa, Projeto, ProjetoConfig

Resolver = Callable[[list[str]], list[dict[str, str]]]


def ler_projeto_json(caminho: str | Path) -> dict:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def config_inicial(projeto_json: dict, canais_env: list[str]) -> ProjetoConfig:
    """Antes da primeira gravação: pessoas e canais do JSON do projeto (+ SLACK_CHANNEL_IDS)."""
    pessoas = []
    for papel, dados in (projeto_json.get("papeis") or {}).items():
        if papel in Papel.__members__ and dados.get("nome"):
            pessoas.append(Pessoa(nome=dados["nome"], papel=Papel(papel)))
    canais = [CanalSlack(nome=nome) for nome in (projeto_json.get("canais") or {})]
    canais += [CanalSlack(id=c) for c in canais_env if not c.startswith("C0000")]
    return ProjetoConfig(canais_slack=canais, pessoas=pessoas)


def montar_projeto(projeto_json: dict, config: ProjetoConfig) -> Projeto:
    info = projeto_json.get("projeto") or {}
    pessoas: dict[Papel, str | None] = {papel: None for papel in Papel}
    for p in config.pessoas:
        pessoas[p.papel] = pessoas[p.papel] or p.nome
    return Projeto(
        nome=info.get("nome") or "Projeto",
        cliente=info.get("cliente"),
        canais_slack=config.canais_slack,
        envolvidos=config.pessoas,
        pessoas=pessoas,
    )


def _chaves(canal: CanalSlack) -> list[str]:
    chaves = [canal.id] if canal.id else []
    if canal.nome:
        chaves.append(f"#{canal.nome.lower()}")
    return chaves


def aplicar_pedido(
    atual: ProjetoConfig, pedido: ConfigPedido, resolver: Callable[[], Resolver]
) -> ProjetoConfig:
    """Monta a nova configuração. Só consulta o Slack para canais que ainda não conhece.

    `resolver` é chamado só quando precisa: assim salvar pessoas funciona mesmo
    sem o Slack configurado.
    """
    conhecidos = {chave: c for c in atual.canais_slack for chave in _chaves(c)}

    canais: list[CanalSlack] = []
    novos: list[str] = []
    for ref in (r.strip() for r in pedido.canais_slack):
        if not ref:
            continue
        chave = ref.lower() if ref.startswith("#") else ref
        if chave in conhecidos:
            canais.append(conhecidos[chave])
        elif not ref.startswith("#") and f"#{ref.lower()}" in conhecidos:
            canais.append(conhecidos[f"#{ref.lower()}"])
        else:
            novos.append(ref)
    if novos:
        canais += [CanalSlack(**c) for c in resolver()(novos)]

    unicos: dict[str, CanalSlack] = {}
    for c in canais:
        unicos.setdefault(c.id or f"#{c.nome}", c)
    pessoas = [p for p in pedido.pessoas if p.nome.strip()]
    return ProjetoConfig(canais_slack=list(unicos.values()), pessoas=pessoas)
