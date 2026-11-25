"""R-08: eval do Radar. Precisão, recall e alarmes falsos contra `data/gabarito.json`.

ATENCAO: rodar o eval CHAMA O MODELO (custa). Itere com `--limite N` e rode completo só quando
o prompt estiver pronto. O eval roda `radar.pipeline.analisar` (sem a pausa de aprovação) com
`MODO_DEMO` desligado, para o cache da demo não mascarar o código atual.

Uso:
    python eval/rodar_eval.py --versao v1-prompt-a --limite 10
    python eval/rodar_eval.py --versao v2-prompt-b
    python eval/rodar_eval.py --comparar eval/resultados/A.json eval/resultados/B.json
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar import config, db, llm  # noqa: E402
from radar.core.models import Acao, Alerta, Registro  # noqa: E402
from radar.fontes.arquivos import FileSource, contexto_de  # noqa: E402
from radar.roteamento import decidir_acao  # noqa: E402

FUSO = ZoneInfo("America/Sao_Paulo")
PASTA_RESULTADOS = Path(__file__).resolve().parent / "resultados"
PREFIXO_ISCA = "ISCA"

Analisar = Callable[[Registro, Sequence[Registro]], Alerta | None]


def _gerou_alerta(alerta: Alerta | None) -> bool:
    """Só conta como alerta o que seria POSTADO no grupo (resumo e descarte não contam)."""
    return alerta is not None and decidir_acao(alerta) == Acao.postar


def e_isca(linha: Mapping) -> bool:
    return str(linha.get("nota") or "").upper().startswith(PREFIXO_ISCA)


def _numero_da_clausula(texto: str | None) -> str:
    """"Cláusula 2.2" e "2.2" valem o mesmo."""
    achado = re.search(r"\d+(?:\.\d+)*", texto or "")
    return achado.group(0) if achado else (texto or "").strip()


def clausulas_aceitas(linha: Mapping) -> set[str]:
    brutas = linha.get("clausulas_aceitas") or [linha.get("clausula")]
    return {_numero_da_clausula(str(c)) for c in brutas if c}


def _razao(parte: int, total: int) -> float:
    return parte / total if total else 0.0


def calcular_metricas(
    gabarito: Sequence[Mapping],
    alertas: Mapping[str, Alerta | None],
    erros: Iterable[str] = (),
) -> dict:
    """Funções puras: compara o que `analisar` devolveu com o gabarito.

    `gabarito` traz só as linhas avaliadas; `alertas` mapeia `registro_id` para o `Alerta` (ou
    `None`); `erros` são os ids em que `analisar` falhou (contam como "sem alerta").
    """
    erros = set(erros)
    desvios = iscas = gerados = certos = 0
    detectados = tipo_ok = resp_ok = clausula_ok = 0
    falsos_iscas = falsos_gerais = 0
    detalhes = []

    for linha in gabarito:
        rid = linha["registro_id"]
        alerta = alertas.get(rid)
        gerou = _gerou_alerta(alerta)
        desvio = bool(linha.get("e_desvio"))
        isca = e_isca(linha)
        desvios += desvio
        iscas += isca
        gerados += gerou
        if gerou and desvio:
            certos += 1
            detectados += 1
            tipo_ok += alerta.tipo.value == linha.get("tipo")
            resp_ok += (alerta.responsavel.value if alerta.responsavel else None) == (
                linha.get("responsavel") or None
            )
            clausula_ok += _numero_da_clausula(alerta.clausula) in clausulas_aceitas(linha)
        if gerou and not desvio:
            falsos_gerais += 1
            falsos_iscas += isca
        detalhes.append(
            {
                "registro_id": rid,
                "e_desvio": desvio,
                "isca": isca,
                "tipo_esperado": linha.get("tipo"),
                "alerta": gerou,
                "tipo": alerta.tipo.value if alerta else None,
                "responsavel": alerta.responsavel.value if alerta and alerta.responsavel else None,
                "clausula": alerta.clausula if alerta else None,
                "confianca": alerta.confianca if alerta else None,
                "erro": rid in erros,
            }
        )

    return {
        "registros_avaliados": len(gabarito),
        "desvios": desvios,
        "iscas": iscas,
        "alertas": gerados,
        "alertas_certos": certos,
        "desvios_detectados": detectados,
        "precisao": _razao(certos, gerados),
        "recall": _razao(detectados, desvios),
        "acertos_tipo": tipo_ok,
        "acerto_tipo": _razao(tipo_ok, detectados),
        "acertos_responsavel": resp_ok,
        "acerto_responsavel": _razao(resp_ok, detectados),
        "acertos_clausula": clausula_ok,
        "acerto_clausula": _razao(clausula_ok, detectados),
        "alarmes_falsos_iscas": falsos_iscas,
        "alarmes_falsos_gerais": falsos_gerais,
        "erros": len(erros),
        "detalhes": detalhes,
    }


def metricas_do_modelo(antes: Mapping[str, int], depois: Mapping[str, int]) -> dict:
    """Saídas válidas e novas tentativas da rodada (diferença dos `CONTADORES` de `llm`)."""
    chamadas = depois["chamadas"] - antes["chamadas"]
    invalidas = depois["invalidas"] - antes["invalidas"]
    return {
        "chamadas_modelo": chamadas,
        "saidas_validas": chamadas - invalidas,
        "saidas_invalidas": invalidas,
        "taxa_saidas_validas": _razao(chamadas - invalidas, chamadas),
        "novas_tentativas": depois["retentativas"] - antes["retentativas"],
    }


@contextmanager
def _sem_cache():
    """`MODO_DEMO` desligado durante a rodada: o cache não pode mascarar o código atual."""
    anterior = config.MODO_DEMO
    config.MODO_DEMO = False
    try:
        yield
    finally:
        config.MODO_DEMO = anterior


def carregar_gabarito(caminho: str | Path) -> list[dict]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def rodar(
    pasta: str | Path = "data",
    *,
    analisar: Analisar | None = None,
    versao: str = "",
    limite: int | None = None,
    gabarito: str | Path | None = None,
    registros: list[Registro] | None = None,
    agora: datetime | None = None,
) -> dict:
    """Roda o eval e devolve as métricas. `analisar` é injetável (os testes usam um falso)."""
    if analisar is None:
        from radar.pipeline import analisar  # preguiçoso: carrega RAG e modelos só se preciso

    pasta = Path(pasta)
    linhas = {g["registro_id"]: g for g in carregar_gabarito(gabarito or pasta / "gabarito.json")}
    todos = registros if registros is not None else FileSource(pasta).fetch()
    avaliar = [r for r in todos if r.id in linhas]
    if limite is not None:
        avaliar = avaliar[:limite]

    alertas: dict[str, Alerta | None] = {}
    erros: list[str] = []
    antes = dict(llm.CONTADORES)
    inicio = time.perf_counter()
    with _sem_cache():
        for registro in avaliar:
            try:
                alertas[registro.id] = analisar(registro, contexto_de(todos, registro))
            except Exception as erro:  # noqa: BLE001 - um registro com erro não derruba a rodada
                erros.append(registro.id)
                alertas[registro.id] = None
                print(f"  erro em {registro.id}: {erro}", file=sys.stderr)
    tempo = time.perf_counter() - inicio

    metricas = calcular_metricas([linhas[r.id] for r in avaliar], alertas, erros)
    metricas.update(metricas_do_modelo(antes, llm.CONTADORES))
    metricas.update(
        {
            "versao": versao,
            "data": (agora or datetime.now(FUSO)).isoformat(timespec="seconds"),
            "modelos": {"principal": config.MODELO_PRINCIPAL, "triagem": config.MODELO_TRIAGEM},
            "limite": limite,
            "sem_gabarito": len(todos) - len([r for r in todos if r.id in linhas]),
            "tempo_total_s": round(tempo, 2),
        }
    )
    return metricas


# --- apresentação (tabela, .md, comparação) ---------------------------------------------


def _pct(parte: int, total: int) -> str:
    return f"{_razao(parte, total):.0%} ({parte}/{total})"


def linhas_da_tabela(m: Mapping) -> list[tuple[str, str, str]]:
    """(rótulo, valor, meta) de cada métrica."""
    return [
        ("Registros avaliados", str(m["registros_avaliados"]), ""),
        ("Precisão (alertas que são desvio)", _pct(m["alertas_certos"], m["alertas"]), ""),
        ("Recall (desvios detectados)", _pct(m["desvios_detectados"], m["desvios"]), "4 de 4"),
        ("Acerto de tipo (nos detectados)", _pct(m["acertos_tipo"], m["desvios_detectados"]), ""),
        (
            "Acerto de responsável (nos detectados)",
            _pct(m["acertos_responsavel"], m["desvios_detectados"]),
            "",
        ),
        (
            "Acerto de cláusula (nos detectados)",
            _pct(m["acertos_clausula"], m["desvios_detectados"]),
            "",
        ),
        ("Alarmes falsos nas iscas", f"{m['alarmes_falsos_iscas']} de {m['iscas']}", "no máximo 1"),
        ("Alarmes falsos gerais", str(m["alarmes_falsos_gerais"]), ""),
        ("Saídas válidas do modelo", _pct(m["saidas_validas"], m["chamadas_modelo"]), "100%"),
        ("Novas tentativas (saída inválida)", str(m["novas_tentativas"]), ""),
        ("Erros do pipeline", str(m["erros"]), "0"),
        ("Tempo total", f"{m['tempo_total_s']:.1f} s", ""),
    ]


def formatar_tabela(m: Mapping) -> str:
    linhas = linhas_da_tabela(m)
    larg = max(len(r[0]) for r in linhas)
    cab = f"Eval {m.get('versao') or '(sem versão)'}  {m.get('data', '')}"
    saida = [cab, "-" * len(cab)]
    saida += [f"{r:<{larg}}  {v:<12} {meta}".rstrip() for r, v, meta in linhas]
    return "\n".join(saida)


def formatar_markdown(m: Mapping) -> str:
    saida = [
        f"# Eval do Radar: {m.get('versao') or '(sem versão)'}",
        "",
        f"Data: {m.get('data', '')}. Modelo principal: `{m['modelos']['principal']}`.",
        "",
        "| Métrica | Valor | Meta |",
        "|---|---|---|",
    ]
    saida += [f"| {r} | {v} | {meta} |" for r, v, meta in linhas_da_tabela(m)]
    erros = [d for d in m["detalhes"] if (d["e_desvio"] and not d["alerta"]) or d["erro"]]
    falsos = [d for d in m["detalhes"] if d["alerta"] and not d["e_desvio"]]
    for titulo, itens in (("Desvios perdidos ou com erro", erros), ("Alarmes falsos", falsos)):
        if itens:
            saida += ["", f"## {titulo}", ""]
            saida += [f"- `{d['registro_id']}` (esperado: {d['tipo_esperado']})" for d in itens]
    return "\n".join(saida) + "\n"


def _nome_livre(pasta: Path, base: str) -> str:
    nome, n = base, 1
    while (pasta / f"{nome}.json").exists():
        n += 1
        nome = f"{base}-{n}"
    return nome


def salvar_relatorio(
    m: Mapping, pasta: str | Path = PASTA_RESULTADOS, agora: datetime | None = None
) -> tuple[Path, Path]:
    """Grava `AAAA-MM-DD_HHMM.json` e `.md` na pasta. Devolve os dois caminhos."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    nome = _nome_livre(pasta, (agora or datetime.now(FUSO)).strftime("%Y-%m-%d_%H%M"))
    arq_json, arq_md = pasta / f"{nome}.json", pasta / f"{nome}.md"
    arq_json.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    arq_md.write_text(formatar_markdown(m), encoding="utf-8")
    return arq_json, arq_md


def gravar_no_banco(m: Mapping, caminho: str | Path | None = None) -> int:
    """Guarda a rodada em `eval_execucoes` (sem os detalhes por registro)."""
    db.init_db(caminho)
    resumo = {k: v for k, v in m.items() if k != "detalhes"}
    return db.salvar_eval(m.get("versao") or "", resumo, caminho=caminho)


_COMPARAVEIS = [
    ("precisao", "Precisão", "pct"),
    ("recall", "Recall", "pct"),
    ("acerto_tipo", "Acerto de tipo", "pct"),
    ("acerto_responsavel", "Acerto de responsável", "pct"),
    ("acerto_clausula", "Acerto de cláusula", "pct"),
    ("alarmes_falsos_iscas", "Alarmes falsos nas iscas", "int"),
    ("alarmes_falsos_gerais", "Alarmes falsos gerais", "int"),
    ("novas_tentativas", "Novas tentativas", "int"),
    ("erros", "Erros do pipeline", "int"),
    ("tempo_total_s", "Tempo total (s)", "seg"),
]


def _fmt(valor: float | None, tipo: str) -> str:
    if valor is None:
        return "n/d"
    return {"pct": f"{valor:.0%}", "int": str(int(valor)), "seg": f"{valor:.1f}"}[tipo]


def comparar(antes: Mapping, depois: Mapping) -> str:
    """Tabela "antes x depois" de duas rodadas (evidência de que o prompt melhorou)."""
    ra, rd = antes.get("versao") or "antes", depois.get("versao") or "depois"
    linhas = [("Métrica", ra, rd, "Variação")]
    for chave, rotulo, tipo in _COMPARAVEIS:
        a, d = antes.get(chave), depois.get(chave)
        if a is None or d is None:
            variacao = ""
        elif tipo == "pct":
            variacao = f"{(d - a) * 100:+.0f} pp"
        else:
            variacao = f"{d - a:+.1f}" if tipo == "seg" else f"{int(d - a):+d}"
        linhas.append((rotulo, _fmt(a, tipo), _fmt(d, tipo), variacao))
    larguras = [max(len(linha[i]) for linha in linhas) for i in range(4)]
    saida = [
        "  ".join(c.ljust(larguras[i]) for i, c in enumerate(linha)).rstrip() for linha in linhas
    ]
    saida.insert(1, "-" * len(saida[0]))
    return "\n".join(saida)


# --- linha de comando ----------------------------------------------------------------------


def _argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Eval do Radar contra data/gabarito.json. ATENÇÃO: chama o modelo (custa). "
            "Itere com --limite e rode completo só com o prompt pronto."
        )
    )
    p.add_argument("--versao", default="", help='rótulo da rodada, ex.: "v1-prompt-a"')
    p.add_argument("--limite", type=int, help="avalia só os N primeiros registros (barato)")
    p.add_argument("--sem-db", action="store_true", help="não grava em eval_execucoes (SQLite)")
    p.add_argument("--pasta", default="data", help="pasta de dados (padrão: data)")
    p.add_argument("--saida", default=str(PASTA_RESULTADOS), help="pasta dos relatórios")
    p.add_argument(
        "--comparar", nargs=2, metavar=("A.json", "B.json"), help="compara duas rodadas salvas"
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None, *, analisar: Analisar | None = None) -> int:
    args = _argumentos(argv)
    if args.comparar:
        a, b = (json.loads(Path(c).read_text(encoding="utf-8")) for c in args.comparar)
        print(comparar(a, b))
        return 0

    agora = datetime.now(FUSO)
    m = rodar(
        args.pasta, analisar=analisar, versao=args.versao, limite=args.limite, agora=agora
    )
    print(formatar_tabela(m))
    arq_json, arq_md = salvar_relatorio(m, args.saida, agora)
    print(f"\nSalvo em {arq_json} e {arq_md}")
    if not args.sem_db:
        print(f"Gravado no banco (eval_execucoes id {gravar_no_banco(m)})")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
