"""Regras da configuração do projeto, sem FastAPI."""

from collections.abc import Callable

from radar.achados.config import AchadosSettings
from radar.achados.models import Papel
from radar.projeto.models import CanalSlack, ConfigPedido, Pessoa, Projeto, ProjetoConfig

Resolver = Callable[[list[str]], list[dict[str, str]]]


def config_inicial(settings: AchadosSettings, canais_env: list[str]) -> ProjetoConfig:
    """Antes da primeira gravação, a configuração vem do .env."""
    pessoas = [
        Pessoa(nome=nome, papel=papel)
        for papel, nome in (
            (Papel.gestor, settings.gestor),
            (Papel.comercial, settings.comercial),
            (Papel.adm_contratos, settings.adm_contratos),
        )
        if nome
    ]
    return ProjetoConfig(canais_slack=[CanalSlack(id=c) for c in canais_env], pessoas=pessoas)


def montar_projeto(settings: AchadosSettings, config: ProjetoConfig) -> Projeto:
    primeiro_canal = next((c.nome for c in config.canais_slack if c.nome), None)
    pessoas: dict[Papel, str | None] = {papel: None for papel in Papel}
    for p in config.pessoas:
        pessoas[p.papel] = pessoas[p.papel] or p.nome
    return Projeto(
        nome=settings.projeto,
        cliente=settings.cliente,
        canal_slack=settings.canal_slack or (f"#{primeiro_canal}" if primeiro_canal else None),
        valor_hora=settings.valor_hora,
        canais_slack=config.canais_slack,
        envolvidos=config.pessoas,
        pessoas=pessoas,
    )


def aplicar_pedido(
    atual: ProjetoConfig, pedido: ConfigPedido, resolver: Callable[[], Resolver]
) -> ProjetoConfig:
    """Monta a nova configuração. Só consulta o Slack para canais que ainda não conhece.

    `resolver` é chamado só quando precisa: assim salvar pessoas funciona mesmo
    sem o Slack configurado.
    """
    conhecidos: dict[str, CanalSlack] = {}
    for c in atual.canais_slack:
        conhecidos[c.id] = c
        if c.nome:
            conhecidos[f"#{c.nome.lower()}"] = c

    canais: list[CanalSlack] = []
    novos: list[str] = []
    for ref in (r.strip() for r in pedido.canais_slack):
        if not ref:
            continue
        chave = ref.lower() if ref.startswith("#") else ref
        if chave in conhecidos:
            canais.append(conhecidos[chave])
        else:
            novos.append(ref)
    if novos:
        canais += [CanalSlack(**c) for c in resolver()(novos)]

    unicos = list({c.id: c for c in canais}.values())
    pessoas = [p for p in pedido.pessoas if p.nome.strip()]
    return ProjetoConfig(canais_slack=unicos, pessoas=pessoas)
