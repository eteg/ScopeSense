import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { type AcaoDecisao, aberto, type Alerta, api } from "../api/client";
import type { PedirNome } from "../App";
import { AlertCard } from "../components/AlertCard";
import { RelatorioDialog } from "../components/RelatorioDialog";
import { baixarCsv } from "../csv";
import { Baixar, Engrenagem, Play, Voltar } from "../icons";
import { ORIGEM, quando } from "../labels";

type Filtro = "pendentes" | "todos";
type Pedido = { ids: string[]; acao: AcaoDecisao };
type Aviso = { texto: string; ids: string[] } | null;

const TEXTO_ACAO: Record<AcaoDecisao, string> = {
  aprovar: "aprovado",
  descartar: "descartado",
  nao_e_desvio: "marcado como “não é desvio”",
};

export function Fila({ nome, pedirNome }: { nome: string; pedirNome: PedirNome }) {
  const qc = useQueryClient();
  const projeto = useQuery({ queryKey: ["projeto"], queryFn: api.projeto });
  const alertas = useQuery({ queryKey: ["alertas"], queryFn: api.alertas });
  const resumo = useQuery({ queryKey: ["resumo"], queryFn: api.resumo });

  const [filtro, setFiltro] = useState<Filtro>("pendentes");
  const [modoSelecao, setModoSelecao] = useState(false);
  const [selecao, setSelecao] = useState<Set<string>>(new Set());
  const [aviso, setAviso] = useState<Aviso>(null);
  const [relatorioAberto, setRelatorioAberto] = useState(false);

  const pessoas = projeto.data?.pessoas ?? {};
  const todos = alertas.data ?? [];
  const pendentes = todos.filter(aberto);
  const visiveis = filtro === "pendentes" ? pendentes : todos;

  const impacto = useMemo(() => {
    const lidos = Object.values(resumo.data?.registros_lidos ?? {}).reduce((t, n) => t + n, 0);
    return {
      desvios: todos.filter((a) => a.status !== "nao_e_desvio").length,
      lidos,
      criticos: pendentes.filter((a) => a.gravidade === "critico").length,
      medios: pendentes.filter((a) => a.gravidade === "medio").length,
      aprovados: todos.filter((a) => a.status === "aprovado").length,
      falsos: todos.filter((a) => a.status === "nao_e_desvio").length,
    };
  }, [todos, pendentes, resumo.data]);

  const lidosPorOrigem = Object.entries(resumo.data?.registros_lidos ?? {})
    .map(([origem, n]) => `${n} ${ORIGEM[origem as keyof typeof ORIGEM] ?? origem}`)
    .join(" · ");

  const decidir = useMutation({
    mutationFn: async ({ ids, acao, quem }: Pedido & { quem: string }) => {
      for (const id of ids) await api.decidir(id, acao, quem);
      return { ids, acao };
    },
    onSuccess: ({ ids, acao }) => {
      const n = ids.length;
      setAviso({
        ids,
        texto: n === 1 ? `Alerta ${TEXTO_ACAO[acao]}` : `${n} alertas: ${TEXTO_ACAO[acao]}`,
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["alertas"] }),
  });

  const desfazer = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) await api.desfazer(id, nome || "?");
    },
    onSuccess: () => setAviso(null),
    onSettled: () => qc.invalidateQueries({ queryKey: ["alertas"] }),
  });

  function pedirDecisao(p: Pedido) {
    if (!nome.trim()) {
      // a decisão segue com o nome que a pessoa acabou de informar
      pedirNome((n) => decidir.mutate({ ...p, quem: n }));
      return;
    }
    decidir.mutate({ ...p, quem: nome.trim() });
  }

  function aprovarLote() {
    const ids = pendentes.filter((a) => selecao.has(a.id)).map((a) => a.id);
    if (!ids.length) return;
    pedirDecisao({ ids, acao: "aprovar" });
    setSelecao(new Set());
    setModoSelecao(false);
  }

  const nSel = pendentes.filter((a) => selecao.has(a.id)).length;
  const tudoSelecionado = nSel === pendentes.length && pendentes.length > 0;

  return (
    <>
      <header className="cabecalho">
        <div className="container cabecalho-interno">
          <div className="titulo-bloco">
            <span className="migalha">
              <Voltar />
              PROJETOS
            </span>
            <h1>{projeto.data?.nome ?? "Projeto"}</h1>
            {projeto.data?.cliente && <p className="sub-titulo">{projeto.data.cliente}</p>}
          </div>
          {resumo.data?.ultimo_alerta_em && (
            <span className="ultima">Último alerta: {quando(resumo.data.ultimo_alerta_em)}</span>
          )}
          <a
            href="#/configuracoes"
            className="btn-icone"
            aria-label="Configurações do projeto"
            title="Configurações do projeto"
          >
            <Engrenagem />
          </a>
          <button
            type="button"
            className="btn btn-texto"
            title="Recarrega os alertas. Quem analisa é o bot do Slack ou o script do pipeline."
            onClick={() => qc.invalidateQueries()}
          >
            Atualizar
          </button>
          <button type="button" className="btn btn-primario" onClick={() => setRelatorioAberto(true)}>
            <Play />
            Gerar relatório
          </button>
        </div>
      </header>

      <main className="container conteudo">
        {alertas.isError && (
          <p className="erro" role="alert">
            Não consegui falar com a API: {alertas.error.message}. O backend está rodando na porta
            8000?
          </p>
        )}

        <section aria-label="Impacto" className="impacto">
          <div className="metrica">
            <div className="metrica-rotulo">Desvios encontrados</div>
            <div className="metrica-valor">{impacto.desvios}</div>
            <div className="metrica-sub" title={lidosPorOrigem}>
              {impacto.lidos ? `em ${impacto.lidos} registros lidos` : "nenhum registro lido ainda"}
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Alertas críticos</div>
            <div className="metrica-valor">{impacto.criticos}</div>
            <div className="metrica-sub">
              e {impacto.medios} {impacto.medios === 1 ? "alerta médio" : "alertas médios"}{" "}
              pendentes
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Aguardando decisão</div>
            <div className="metrica-valor">{pendentes.length}</div>
            <div className="metrica-sub">
              {impacto.aprovados} {impacto.aprovados === 1 ? "aprovado" : "aprovados"} até agora
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Não é desvio</div>
            <div className="metrica-valor">{impacto.falsos}</div>
            <div className="metrica-sub">falsos positivos que viram casos de teste</div>
          </div>
        </section>

        <section aria-labelledby="fila-h">
          <div className="fila-topo">
            <h2 id="fila-h">Fila de alertas</h2>
            {!modoSelecao ? (
              <button
                type="button"
                className="btn-pequeno btn-contorno-azul"
                disabled={!pendentes.length}
                onClick={() => {
                  setModoSelecao(true);
                  setFiltro("pendentes");
                  setAviso(null);
                }}
              >
                Aprovar em lote
              </button>
            ) : (
              <button
                type="button"
                className="btn-pequeno btn-texto"
                onClick={() =>
                  setSelecao(tudoSelecionado ? new Set() : new Set(pendentes.map((a) => a.id)))
                }
              >
                {tudoSelecionado ? "Desmarcar todos" : "Selecionar todos"}
              </button>
            )}
            <button
              type="button"
              className={filtro === "pendentes" ? "btn-pequeno filtro ativo" : "btn-pequeno filtro"}
              aria-pressed={filtro === "pendentes"}
              onClick={() => setFiltro("pendentes")}
            >
              Pendentes ({pendentes.length})
            </button>
            <button
              type="button"
              className={filtro === "todos" ? "btn-pequeno filtro ativo" : "btn-pequeno filtro"}
              aria-pressed={filtro === "todos"}
              disabled={modoSelecao}
              onClick={() => setFiltro("todos")}
            >
              Todos
            </button>
            <button
              type="button"
              className="btn-pequeno filtro"
              disabled={!visiveis.length}
              onClick={() => baixarCsv(visiveis, pessoas)}
            >
              <Baixar />
              Baixar CSV
            </button>
          </div>

          <div className="lista">
            {alertas.isPending && <p className="vazio">Carregando alertas…</p>}
            {alertas.isSuccess && todos.length === 0 && (
              <p className="vazio">
                Nenhum alerta ainda. Rode <code>python -m radar.demo</code> para ver os desvios do
                gabarito, ou o pipeline com a chave do modelo.
              </p>
            )}
            {alertas.isSuccess && todos.length > 0 && visiveis.length === 0 && (
              <p className="vazio">Nenhum alerta pendente. Tudo dentro do combinado.</p>
            )}
            {visiveis.map((a: Alerta) => (
              <AlertCard
                key={a.id}
                alerta={a}
                pessoas={pessoas}
                modoSelecao={modoSelecao}
                selecionado={selecao.has(a.id)}
                ocupado={decidir.isPending}
                onSelecionar={() => {
                  const n = new Set(selecao);
                  if (n.has(a.id)) n.delete(a.id);
                  else n.add(a.id);
                  setSelecao(n);
                }}
                onDecidir={(acao) => pedirDecisao({ ids: [a.id], acao })}
              />
            ))}
          </div>

          {decidir.isError && (
            <p className="erro" role="alert">
              Não foi possível registrar: {decidir.error.message}
            </p>
          )}

          {modoSelecao && (
            <div role="region" aria-label="Aprovar em lote" className="barra-lote">
              <span className="lote-contagem">
                {nSel === 0
                  ? "Marque os alertas para aprovar"
                  : nSel === 1
                    ? "1 alerta selecionado"
                    : `${nSel} alertas selecionados`}
              </span>
              <span className="espaco" />
              <button
                type="button"
                className="btn btn-texto btn-neutro"
                onClick={() => {
                  setModoSelecao(false);
                  setSelecao(new Set());
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn-primario"
                disabled={nSel === 0 || decidir.isPending}
                onClick={aprovarLote}
              >
                Aprovar selecionados
              </button>
            </div>
          )}

          {aviso && !modoSelecao && (
            <div role="status" className="aviso">
              <span>{aviso.texto}</span>
              <button
                type="button"
                disabled={desfazer.isPending}
                onClick={() => desfazer.mutate(aviso.ids)}
              >
                Desfazer
              </button>
            </div>
          )}
        </section>
      </main>
      <RelatorioDialog
        aberto={relatorioAberto}
        onFechar={() => setRelatorioAberto(false)}
        nome={nome}
        pedirNome={pedirNome}
      />
    </>
  );
}
