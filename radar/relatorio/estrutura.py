"""Relatório estruturado (o modelo devolve dados, o código monta o Slack).

O modelo preenche `RelatorioEstruturado` (saída validada por schema). Daqui saem:
- as mensagens do Slack em Block Kit: resumo + uma por responsável, cada ponto com
  a barra colorida da severidade e o botão "Ver evidência";
- o texto simples (fallback) que o Slack usa em notificações e a tela usa na prévia.

As marcações (`<@ID>`) só o código escreve: o modelo nunca vê nem escolhe IDs.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field

Severidade = Literal["critico", "medio", "baixo"]
PapelNome = Literal["gestor", "comercial", "administrativo_contratos"]


class Acao(BaseModel):
    papel: PapelNome
    o_que_fazer: str = Field(description="Ação objetiva para esse papel, com prazo (uma frase)")


class Ponto(BaseModel):
    severidade: Severidade
    titulo: str = Field(description="Explica a divergência sozinho, até ~90 caracteres")
    categoria: str = Field(description='Ex.: "Fora do escopo", "Prazo", "Documento de terceiro"')
    por_que_importa: str = Field(description="Consequência concreta, uma frase curta")
    clausula: str | None = Field(default=None, description='Ex.: "2.2"; nulo se não há cláusula')
    fonte: str = Field(description='Onde apareceu, curto: "Slack, Rafa Freitas, 25/11"')
    link_evidencia: str | None = Field(
        default=None, description="Link do registro (copiado dos dados), ou nulo"
    )
    recorrente_desde: str | None = Field(default=None, description='"DD/MM" se já apareceu')
    acoes: list[Acao] = Field(description="Uma ação por papel envolvido")


class RelatorioEstruturado(BaseModel):
    sem_contrato: bool = Field(description="True se não há contrato nos arquivos do projeto")
    historia: str = Field(description="Duas ou três frases simples: o que mais preocupa e por quê")
    pontos: list[Ponto]


# --- apresentação -------------------------------------------------------------------------

EMOJI = {"critico": "🔴", "medio": "🟠", "baixo": "🟡"}
COR = {"critico": "#BA1A1A", "medio": "#E08A1E", "baixo": "#C9A400"}
ROTULO_SEV = {"critico": "Críticos", "medio": "Atenção", "baixo": "Acompanhar"}
ROTULO_PAPEL = {
    "gestor": "Gestor do projeto",
    "comercial": "Comercial",
    "administrativo_contratos": "Administrativo de contratos",
}
ORDEM = {"critico": 0, "medio": 1, "baixo": 2}


def esc(texto: str) -> str:
    """Texto do modelo no Slack: escapa &, < e > (impede marcações e links injetados)."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _link_ok(link: str | None) -> str | None:
    return link if link and re.match(r"^https://", link) else None


def contagem(r: RelatorioEstruturado) -> dict[str, int]:
    return {s: sum(1 for p in r.pontos if p.severidade == s) for s in ("critico", "medio", "baixo")}


def mensagens(
    r: RelatorioEstruturado,
    *,
    projeto: str,
    periodo: str,
    fontes: str,
    pessoas: dict[str, tuple[str, str | None]],  # papel -> (nome, slack_id)
) -> list[dict]:
    """Resumo + uma mensagem por responsável, prontas para `chat.postMessage`.

    Cada item: {"papel", "text" (fallback/prévia), "blocks", "attachments"}.
    """
    n = contagem(r)
    por_papel: dict[str, list[tuple[Ponto, str]]] = {}
    for ponto in sorted(r.pontos, key=lambda p: ORDEM[p.severidade]):
        for acao in ponto.acoes:
            por_papel.setdefault(acao.papel, []).append((ponto, acao.o_que_fazer))

    ordem_papel = list(ROTULO_PAPEL)  # gestor, comercial, administrativo
    por_papel = dict(sorted(por_papel.items(), key=lambda kv: ordem_papel.index(kv[0])))

    def criticos_txt(n: int) -> str:
        return f"{n} {'crítico' if n == 1 else 'críticos'}"

    def nome(papel: str) -> str:
        return pessoas.get(papel, (ROTULO_PAPEL.get(papel, papel), None))[0]

    def marca(papel: str) -> str:
        nome_p, sid = pessoas.get(papel, (ROTULO_PAPEL.get(papel, papel), None))
        return f"<@{sid}>" if sid else f"*{esc(nome_p)}* (não encontrei no Slack)"

    # 1. resumo
    quem = [
        f"• *{esc(nome(papel))}* ({ROTULO_PAPEL[papel]}): "
        f"{len(itens)} {'ponto' if len(itens) == 1 else 'pontos'}"
        + (f", {criticos_txt(sum(1 for p, _ in itens if p.severidade == 'critico'))}"
           if any(p.severidade == "critico" for p, _ in itens) else "")  # fmt: skip
        for papel, itens in por_papel.items()
    ]
    titulo = f"📡 Radar de Desvios · {projeto}"
    if r.sem_contrato:
        historia = esc(r.historia) or "Não encontrei o contrato do projeto."
    else:
        historia = esc(r.historia)
    blocos_resumo: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": titulo[:150], "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{periodo} · {fontes}"}]},
    ]
    if r.pontos:
        blocos_resumo.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"{EMOJI[s]} *{ROTULO_SEV[s]}*\n{n[s]}"}
                for s in ("critico", "medio", "baixo")
            ],
        })  # fmt: skip
    blocos_resumo.append({"type": "section", "text": {"type": "mrkdwn", "text": historia}})
    if quem:
        blocos_resumo += [
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn",
                                         "text": "*Quem precisa agir*\n" + "\n".join(quem)}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text":
                "Cada pessoa recebe uma mensagem a seguir. Usem a thread de cada uma para discutir."}]},
        ]  # fmt: skip
    resumo_txt = (
        f"{titulo}\n{periodo}\n"
        + (f"🔴 {n['critico']} · 🟠 {n['medio']} · 🟡 {n['baixo']}\n" if r.pontos else "")
        + r.historia
    )
    saida = [{"papel": None, "text": resumo_txt, "blocks": blocos_resumo, "attachments": []}]

    # 2. uma por responsável
    for papel, itens in por_papel.items():
        criticos = sum(1 for p, _ in itens if p.severidade == "critico")
        cabeca = (
            f"{marca(papel)} *{len(itens)} {'ponto precisa' if len(itens) == 1 else 'pontos precisam'}"
            " de você*"
        )
        anexos = []
        for i, (p, fazer) in enumerate(itens):
            detalhe = " · ".join(
                x for x in (esc(p.categoria), f"cl. {esc(p.clausula)}" if p.clausula else None,
                            esc(p.fonte),
                            f":repeat: desde {esc(p.recorrente_desde)}" if p.recorrente_desde else None)
                if x
            )  # fmt: skip
            secao: dict = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{EMOJI[p.severidade]} {esc(p.titulo)}*\n*O que fazer:* {esc(fazer)}",
                },
            }
            link = _link_ok(p.link_evidencia)
            if link:
                secao["accessory"] = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Ver evidência"},
                    "url": link,
                    "action_id": f"ver_evidencia_{i}",
                }
            anexos.append({
                "color": COR[p.severidade],
                "blocks": [
                    secao,
                    {"type": "context", "elements": [
                        {"type": "mrkdwn", "text": f"{detalhe}\n_{esc(p.por_que_importa)}_"}]},
                ],
            })  # fmt: skip
        texto = (
            f"{marca(papel)} {len(itens)} {'ponto' if len(itens) == 1 else 'pontos'} do Radar "
            f"de Desvios ({projeto}) para você"
            + (f", {criticos_txt(criticos)}" if criticos else "")
        )
        saida.append({
            "papel": papel,
            "text": texto,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": cabeca}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text":
                    f"{esc(projeto)} · {periodo}"
                    + (f" · {criticos} {'crítico' if criticos == 1 else 'críticos'}" if criticos else "")}]},
            ],
            "attachments": anexos,
        })  # fmt: skip
    return saida
