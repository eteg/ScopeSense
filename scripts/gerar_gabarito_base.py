"""Gera `data/gabarito.json` pré-preenchido com TODOS os ids lidos pelo `FileSource` (G-03).

Cada linha: {"registro_id", "e_desvio": false, "tipo": "nenhum", "responsavel": null,
"clausula": null, "nota": ""}. Nunca digite ids à mão: eles são hashes.

    python scripts/gerar_gabarito_base.py                     # só o esqueleto (tudo false)
    python scripts/gerar_gabarito_base.py --rotular-slack     # + rótulos do export do Slack

`--rotular-slack` marca os 3 desvios do Slack (1, 2 e 3) e as 5 iscas (com o motivo em `nota`),
procurando cada mensagem pelo texto. Os desvios do PDF (3, via documentos) e da reunião (4)
entram quando os parsers de .pdf e .vtt existirem (veja data/slack_export.anotacoes.md).
Rodar de novo regenera o arquivo do zero.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from radar.core.models import Consulta, Origem, Registro  # noqa: E402
from radar.fontes.arquivos import FileSource  # noqa: E402

ROTEAMENTO_PADRAO = {
    "escopo_extra": "gestor",
    "prazo_sla": "comercial",
    "terceiro_sem_documento": "administrativo_contratos",
    "promessa_fora_do_contrato": "administrativo_contratos",
}

# (trecho único do texto, tipo, cláusula, nota). `tipo` "nenhum" = isca ou contexto.
ROTULOS_SLACK: list[tuple[str, str, str | None, str]] = [
    (
        "a gente faz, sem problema",
        "escopo_extra",
        "2.2",
        "DESVIO 1: o cliente pede o módulo de relatórios e a equipe aceita; a cláusula 2.2 "
        "exclui relatórios e a 5 exige aditivo assinado",
    ),
    (
        "só fica pronta em 12/02",
        "prazo_sla",
        "3.1",
        "DESVIO 2: integração com o CRM (M3, 29/01) só em 12/02, 14 dias depois; aviso informal "
        "não altera o marco (3.2)",
    ),
    (
        "o João da Nimbus começa amanhã no cliente",
        "terceiro_sem_documento",
        "6.1",
        "DESVIO 3: ASO do João venceu em 10/11/2026 e falta a guia de FGTS de 01/2027 "
        "(6.1 e 6.4)",
    ),
    (
        "o aditivo do módulo de integração foi assinado",
        "nenhum",
        None,
        "ISCA 1: módulo extra com aditivo já assinado (cláusula 5 cumprida)",
    ),
    (
        "passa de 25/01 para 28/01",
        "nenhum",
        None,
        "ISCA 2: prazo remarcado com aceite formal e escrito do cliente (3.2)",
    ),
    (
        "não está no escopo do projeto. Se quiserem",
        "nenhum",
        None,
        "ISCA 3: pedido do cliente recusado educadamente, nada foi prometido (5.3)",
    ),
    (
        "É só configuração da fila do módulo de atendimento",
        "nenhum",
        None,
        "ISCA 4: conversa sobre o módulo de atendimento, que está no escopo (2.1 a)",
    ),
    (
        "A Carla da Nimbus começa amanhã",
        "nenhum",
        None,
        "ISCA 5: os documentos da Carla estão em dia",
    ),
    (
        "mudar a ordem das colunas",
        "nenhum",
        None,
        "Contexto da ISCA 4: pedido dentro do módulo de atendimento",
    ),
    (
        "incluir um módulo de relatórios com painéis",
        "nenhum",
        None,
        "Contexto do DESVIO 1: o pedido, sozinho, não obriga ninguém",
    ),
    (
        "módulo extra de integração com o estoque",
        "nenhum",
        None,
        "Contexto da ISCA 1: pergunta sobre módulo que já tem aditivo",
    ),
    (
        "aplicativo de celular para abrir chamados",
        "nenhum",
        None,
        "Contexto da ISCA 3: pedido que foi recusado",
    ),
]


def linha_base(registro_id: str) -> dict[str, Any]:
    return {
        "registro_id": registro_id,
        "e_desvio": False,
        "tipo": "nenhum",
        "responsavel": None,
        "clausula": None,
        "nota": "",
    }


def carregar_registros(pasta: Path) -> list[Registro]:
    return FileSource(pasta).fetch(Consulta(limite=1000))


def gerar_base(registros: list[Registro]) -> list[dict[str, Any]]:
    return [linha_base(r.id) for r in registros]


def _roteamento(pasta: Path) -> dict[str, str]:
    projeto = pasta / "projeto_alfa.json"
    if projeto.is_file():
        dados = json.loads(projeto.read_text(encoding="utf-8"))
        return dados.get("roteamento") or ROTEAMENTO_PADRAO
    return ROTEAMENTO_PADRAO


def rotular_slack(
    linhas: list[dict[str, Any]],
    registros: list[Registro],
    roteamento: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Preenche os rótulos das mensagens do Slack. Cada trecho deve casar com 1 mensagem."""
    roteamento = roteamento or ROTEAMENTO_PADRAO
    slack = [r for r in registros if r.origem == Origem.slack]
    por_id = {linha["registro_id"]: linha for linha in linhas}
    for trecho, tipo, clausula, nota in ROTULOS_SLACK:
        achados = [r for r in slack if trecho in r.texto]
        if len(achados) != 1:
            raise SystemExit(
                f"Rótulo '{trecho}': esperava 1 mensagem do Slack, achei {len(achados)}."
            )
        linha = por_id[achados[0].id]
        linha["e_desvio"] = tipo != "nenhum"
        linha["tipo"] = tipo
        linha["responsavel"] = roteamento[tipo] if tipo != "nenhum" else None
        linha["clausula"] = clausula
        linha["nota"] = nota
    return linhas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pasta", default=str(RAIZ / "data"), help="pasta de dados (FileSource)")
    ap.add_argument("--saida", default=None, help="padrão: <pasta>/gabarito.json")
    ap.add_argument("--rotular-slack", action="store_true", help="rotula desvios e iscas do Slack")
    args = ap.parse_args(argv)

    pasta = Path(args.pasta)
    saida = Path(args.saida) if args.saida else pasta / "gabarito.json"
    registros = carregar_registros(pasta)
    linhas = gerar_base(registros)
    if args.rotular_slack:
        linhas = rotular_slack(linhas, registros, _roteamento(pasta))

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(linhas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    desvios = sum(1 for linha in linhas if linha["e_desvio"])
    print(f"{len(linhas)} registros em {saida} ({desvios} desvios rotulados)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
