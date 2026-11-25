import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { type Achado, api, type Decisao } from "../api/client";
import slackLogo from "../assets/slack.png";
import { AlertCard } from "../components/AlertCard";
import { baixarCsv } from "../csv";
import { Baixar, Engrenagem, Play, Seta, Voltar } from "../icons";
import { custo, diaCurto, quando } from "../labels";
import type { PedirNome } from "../App";

type Filtro = "pendentes" | "todos";
type Pendente = { ids: number[]; decisao: Decisao };
type Aviso = { texto: string; ids: number[] } | null;

export function Fila({ nome, pedirNome }: { nome: string; pedirNome: PedirNome }) {
  const qc = useQueryClient();
  const projeto = useQuery({ queryKey: ["projeto"], queryFn: api.projeto });
  const achados = useQuery({ queryKey: ["achados"], queryFn: api.achados });
  const analise = useQuery({ queryKey: ["analise"], queryFn: api.ultimaAnalise });

  const [filtro, setFiltro] = useState<Filtro>("pendentes");
  const [modoSelecao, setModoSelecao] = useState(false);
  const [selecao, setSelecao] = useState<Set<number>>(new Set());
  const [aviso, setAviso] = useState<Aviso>(null);

  const pessoas = projeto.data?.pessoas ?? {};
  const canal = projeto.data?.canal_slack ?? "canal do projeto";
  const todos = achados.data ?? [];
  const pendentes = todos.filter((a) => a.status === "pendente");
  const visiveis = filtro === "pendentes" ? pendentes : todos;

  const impacto = useMemo(() => {
    const validos = todos.filter((a) => a.status !== "nao_e_desvio");
    const horas = validos.reduce((t, a) => t + (a.horas_estimadas ?? 0), 0);
    return {
      desvios: validos.filter((a) => a.categoria === "desvio").length,
      criticos: pendentes.filter((a) => a.gravidade === "critico").length,
      medios: pendentes.filter((a) => a.gravidade === "atencao").length,
      horas,
      custo: horas * (projeto.data?.valor_hora ?? 0),
    };
  }, [todos, pendentes, projeto.data]);

  const lidos = Object.entries(analise.data?.registros_lidos ?? {});
  const totalLidos = lidos.reduce((t, [, n]) => t + n, 0);

  const decidir = useMutation({
    mutationFn: async ({ ids, decisao, por }: Pendente & { por: string }) => {
      for (const id of ids) await api.decidir(id, decisao, por);
      return { ids, decisao };
    },
    onSuccess: ({ ids, decisao }) => {
      const n = ids.length;
      const plural = n === 1 ? "alerta" : "alertas";
      setAviso({
        ids,
        texto:
          decisao === "aprovado"
            ? n > 1
              ? `Relatório com ${n} ${plural} aprovado para ${canal}`
              : `Alerta aprovado para ${canal}`
            : `${n} ${plural} marcado${n > 1 ? "s" : ""} como “não é desvio”`,
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["achados"] }),
  });

  const desfazer = useMutation({
    mutationFn: async (ids: number[]) => {
      for (const id of ids) await api.desfazer(id, nome);
    },
    onSuccess: () => setAviso(null),
    onSettled: () => qc.invalidateQueries({ queryKey: ["achados"] }),
  });

  function pedirDecisao(p: Pendente) {
    if (!nome.trim()) {
      // a decisão segue com o nome que a pessoa acabou de informar
      pedirNome((n) => decidir.mutate({ ...p, por: n }));
      return;
    }
    decidir.mutate({ ...p, por: nome.trim() });
  }

  function enviarLote() {
    const ids = pendentes.filter((a) => selecao.has(a.id)).map((a) => a.id);
    if (!ids.length) return;
    pedirDecisao({ ids, decisao: "aprovado" });
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
          </div>
          {analise.data && (
            <span className="ultima">
              Última análise: {quando(analise.data.executada_em)} ·{" "}
              {Math.round(analise.data.duracao_s)} s
            </span>
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
            className="btn btn-primario"
            title="Recarrega os alertas. O detector com LLM ainda não está ligado."
            onClick={() => qc.invalidateQueries()}
          >
            <Play />
            Rodar análise
          </button>
        </div>
      </header>

      <main className="container conteudo">
        {achados.isError && (
          <p className="erro" role="alert">
            Não consegui falar com a API: {achados.error.message}. O backend está rodando na porta
            8000?
          </p>
        )}

        {analise.data && (
          <section aria-labelledby="dia-h" className="resumo-dia">
            <div className="resumo-topo">
              <h2 id="dia-h">RESUMO DO DIA · {diaCurto(analise.data.executada_em)}</h2>
              <span>{lidos.map(([k, n]) => `${n} ${k}`).join(" · ")}</span>
            </div>
            <p>{analise.data.resumo}</p>
          </section>
        )}

        <section aria-label="Impacto" className="impacto">
          <div className="metrica">
            <div className="metrica-rotulo">Desvios encontrados</div>
            <div className="metrica-valor">{impacto.desvios}</div>
            <div className="metrica-sub">
              {totalLidos ? `em ${totalLidos} registros lidos` : "na última análise"}
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Alertas críticos</div>
            <div className="metrica-valor">{impacto.criticos}</div>
            <div className="metrica-sub">
              e {impacto.medios} {impacto.medios === 1 ? "alerta médio" : "alertas médios"}
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Horas evitadas</div>
            <div className="metrica-valor">{impacto.horas} h</div>
            <div className="metrica-sub">de trabalho fora do contrato</div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Custo evitado</div>
            <div className="metrica-valor">{custo(impacto.custo)}</div>
            <div className="metrica-sub">
              premissa de {custo(projeto.data?.valor_hora ?? 0)} por hora
            </div>
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
                <img src={slackLogo} alt="" className="slack slack-16" />
                Enviar alertas em lote
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
            {achados.isPending && <p className="vazio">Carregando alertas…</p>}
            {achados.isSuccess && visiveis.length === 0 && (
              <p className="vazio">Nenhum alerta pendente. Tudo dentro do combinado.</p>
            )}
            {visiveis.map((a: Achado) => (
              <AlertCard
                key={a.id}
                achado={a}
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
                onDecidir={(decisao) => pedirDecisao({ ids: [a.id], decisao })}
              />
            ))}
          </div>

          {decidir.isError && (
            <p className="erro" role="alert">
              Não foi possível registrar: {decidir.error.message}
            </p>
          )}

          {modoSelecao && (
            <div role="region" aria-label="Enviar relatório" className="barra-lote">
              <span className="lote-contagem">
                {nSel === 0
                  ? "Marque os alertas para enviar"
                  : nSel === 1
                    ? "1 alerta selecionado"
                    : `${nSel} alertas selecionados`}
              </span>
              <span className="suave">Enviar para</span>
              <span className="destino">
                {canal}
                <Seta />
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
                onClick={enviarLote}
              >
                <img src={slackLogo} alt="" className="slack slack-branco" />
                Enviar por Slack
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

    </>
  );
}
