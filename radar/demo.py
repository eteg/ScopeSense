"""Demo SEM o modelo: monta a Fila com os 4 desvios do gabarito.

Lê os dados sintéticos de `data/` (Slack, reunião, e-mails e PDFs do terceiro),
grava os registros no SQLite e cria um alerta para cada desvio de
`data/gabarito.json`, com o texto da cláusula esperada. Serve para ver as telas
sem chave da Anthropic. Com a chave, rode o pipeline de verdade
(`python scripts/classificar_demo.py`): ele grava no mesmo banco.

Os alertas daqui são a RESPOSTA ESPERADA, não a saída do modelo; por isso a
justificativa começa com "[gabarito]".

Uso:
    python -m radar.demo            # acrescenta (idempotente)
    python -m radar.demo --limpar   # apaga o banco e os PDFs enviados antes
"""

import argparse
import json
import shutil
from pathlib import Path

from radar import config, db
from radar.contrato import carregar_contrato
from radar.core.models import Acao, Alerta, TipoDesvio
from radar.documentos import carregar_documentos
from radar.fontes.arquivos import FileSource
from radar.roteamento import rotear_alerta

CONFIANCA_DEMO = 0.9
MAX_TRECHO = 400


def _curto(texto: str, limite: int = MAX_TRECHO) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def popular(pasta_dados: str | Path = "data", *, caminho: str | Path | None = None) -> int:
    """Grava registros e os alertas do gabarito. Devolve quantos alertas criou."""
    pasta = Path(pasta_dados)
    caminho = caminho or config.DATABASE_PATH
    db.init_db(caminho)

    registros = {r.id: r for r in FileSource(pasta).fetch()}
    for r in registros.values():
        db.salvar_registro(r, caminho=caminho)
    db.salvar_documentos(carregar_documentos(pasta / "documentos"), caminho=caminho)

    clausulas = {c["numero"]: c for c in carregar_contrato(pasta / "contrato_alfa.md")}
    gabarito = json.loads((pasta / "gabarito.json").read_text(encoding="utf-8"))

    criados = 0
    for item in gabarito:
        if not item.get("e_desvio"):
            continue
        registro = registros.get(item["registro_id"])
        if registro is None:
            continue  # o gabarito cita um registro que os dados não têm mais
        clausula = clausulas.get(item["clausula"], {})
        nota = item.get("nota", "").split(":", 1)[-1].strip()
        alerta = Alerta(
            registro_id=registro.id,
            tipo=TipoDesvio(item["tipo"]),
            confianca=CONFIANCA_DEMO,
            clausula=item["clausula"],
            trecho_contrato=_curto(clausula.get("texto", "")) or "(cláusula não encontrada)",
            trecho_evidencia=_curto(registro.texto),
            justificativa=_curto(f"[gabarito] {nota}", 300),
        )
        alerta, acao = rotear_alerta(alerta)
        if acao == Acao.descartar:
            continue
        db.salvar_alerta(alerta, acao, "pendente" if acao == Acao.postar else "em_resumo",
                         caminho=caminho)  # fmt: skip
        criados += 1
    return criados


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limpar", action="store_true", help="apaga o banco e os PDFs enviados")
    parser.add_argument("--dados", default="data", help="pasta dos dados sintéticos")
    args = parser.parse_args()

    if args.limpar:
        for sufixo in ("", "-wal", "-shm"):
            Path(config.DATABASE_PATH + sufixo).unlink(missing_ok=True)
        shutil.rmtree(config.UPLOADS_DIR, ignore_errors=True)
    n = popular(args.dados)
    lidos = db.contar_registros()
    print(f"{n} alertas do gabarito e {sum(lidos.values())} registros gravados em "
          f"{config.DATABASE_PATH}: {lidos}")  # fmt: skip


if __name__ == "__main__":
    main()
