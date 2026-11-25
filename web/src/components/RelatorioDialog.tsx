import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, type Relatorio, type TarefaRelatorio } from "../api/client";
import type { PedirNome } from "../App";
import { dolares, PAPEL, reais, tokens } from "../labels";
import { Mrkdwn } from "../mrkdwn";
import { BlockKitPrevia } from "./BlockKitPrevia";
import { ProgressoRelatorio } from "./ProgressoRelatorio";

type Props = { aberto: boolean; onFechar: () => void; nome: string; pedirNome: PedirNome };

const PERIODOS = [
  { dias: 1, rotulo: "Último dia" },
  { dias: 7, rotulo: "Últimos 7 dias" },
  { dias: 14, rotulo: "Últimos 14 dias" },
  { dias: 30, rotulo: "Últimos 30 dias" },
];

const ROTULO_FONTE: Record<string, string> = {
  mensagens_slack: "mensagens no Slack",
  threads_slack: "threads",
  emails: "e-mails",
  arquivos: "arquivos enviados",
  anexos_gmail: "PDFs anexados aos e-mails",
};

/** Inicia a geração em segundo plano e acompanha as etapas a cada segundo. */
function useGeracao(dias: number, onPronto: (r: Relatorio) => void) {
  const [tarefa, setTarefa] = useState<TarefaRelatorio | null>(null);
  const [rodando, setRodando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const pronto = useRef(onPronto);
  pronto.current = onPronto;

  useEffect(() => {
    if (!tarefa || tarefa.concluida) return;
    const id = tarefa.id;
    const t = setInterval(async () => {
      try {
        const atual = await api.tarefaRelatorio(id);
        setTarefa(atual);
        if (atual.concluida) {
          setRodando(false);
          if (atual.relatorio) pronto.current(atual.relatorio);
          else setErro(atual.erro ?? "A geração falhou.");
        }
      } catch (e) {
        setRodando(false);
        setErro(e instanceof Error ? e.message : String(e));
      }
    }, 1000);
    return () => clearInterval(t);
  }, [tarefa]);

  return {
    isPending: rodando,
    isError: erro !== null,
    error: { message: erro ?? "" },
    etapas: tarefa?.etapas ?? null,
    mutate: () => {
      setErro(null);
      setRodando(true);
      api
        .iniciarRelatorio(dias)
        .then(setTarefa)
        .catch((e: unknown) => {
          setRodando(false);
          setErro(e instanceof Error ? e.message : String(e));
        });
    },
    reset: () => {
      setTarefa(null);
      setErro(null);
      setRodando(false);
    },
  };
}

/** Gerar relatório → revisar a prévia → publicar no canal do projeto. */
export function RelatorioDialog({ aberto, onFechar, nome, pedirNome }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [dias, setDias] = useState(7);
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);

  const qc = useQueryClient();
  const historico = useQuery({ queryKey: ["relatorios"], queryFn: api.relatorios, enabled: aberto });
  const gerar = useGeracao(dias, (r) => {
    setRelatorio(r);
    qc.invalidateQueries({ queryKey: ["relatorios"] });
  });
  const publicar = useMutation({
    mutationFn: (quem: string) => api.publicarRelatorio(relatorio!.id, quem),
    onSuccess: setRelatorio,
  });

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (aberto && !dlg.open) dlg.showModal();
    if (!aberto && dlg.open) dlg.close();
  }, [aberto]);

  function fechar() {
    if (gerar.isPending || publicar.isPending) return;
    setRelatorio(null);
    gerar.reset();
    publicar.reset();
    onFechar();
  }

  const nomes = Object.fromEntries(
    (relatorio?.pessoas ?? []).filter((p) => p.slack_id).map((p) => [p.slack_id!, p.nome]),
  );
  const canal = relatorio?.canal_nome ? `#${relatorio.canal_nome}` : "canal do projeto";

  return (
    <dialog
      ref={ref}
      className="dialogo dialogo-largo"
      aria-labelledby="dlg-rel"
      onClose={fechar}
      onCancel={(e) => {
        if (gerar.isPending || publicar.isPending) e.preventDefault();
      }}
    >
      <h2 id="dlg-rel">Relatório do projeto</h2>

      {!relatorio && (
        <>
          <p>
            O Radar lê as threads do canal do projeto no Slack, os e-mails do projeto, o contrato
            (PDFs anexados aos e-mails e enviados nas Configurações) e escreve o relatório de
            desvios e problemas.
            Você revisa antes de publicar.
          </p>
          <label className="campo campo-contorno-azul">
            <span>Período</span>
            <select
              value={dias}
              disabled={gerar.isPending}
              onChange={(e) => setDias(Number(e.target.value))}
            >
              {PERIODOS.map((p) => (
                <option key={p.dias} value={p.dias}>
                  {p.rotulo}
                </option>
              ))}
            </select>
          </label>
          {gerar.etapas && (
            <ProgressoRelatorio
              etapas={
                gerar.isError
                  ? gerar.etapas.map((e) => (e.status === "andamento" ? { ...e, status: "erro" } : e))
                  : gerar.etapas
              }
            />
          )}
          {gerar.isError && (
            <p className="erro" role="alert">
              {gerar.error.message}
            </p>
          )}
          {historico.data && historico.data.relatorios.length > 0 && (
            <p className="rel-gasto">
              Até agora: {historico.data.relatorios.length}{" "}
              {historico.data.relatorios.length === 1 ? "relatório gerado" : "relatórios gerados"}
              {historico.data.total_brl > 0 && <> · {reais(historico.data.total_brl)} em IA</>}
              {historico.data.sem_custo > 0 && (
                <span className="aviso-suave">
                  {" "}
                  ({historico.data.sem_custo} sem custo registrado, gerados antes do cálculo)
                </span>
              )}
            </p>
          )}
          <div className="dialogo-acoes">
            <button type="button" className="btn btn-texto" onClick={fechar} disabled={gerar.isPending}>
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn-primario"
              disabled={gerar.isPending}
              onClick={() => gerar.mutate()}
            >
              {gerar.isPending ? "Gerando…" : "Gerar relatório"}
            </button>
          </div>
        </>
      )}

      {relatorio && (
        <>
          <p className="rel-fontes">
            {Object.entries(relatorio.fontes)
              .map(([k, n]) => `${n} ${ROTULO_FONTE[k] ?? k}`)
              .join(" · ")}
          </p>
          {relatorio.custo && relatorio.custo.brl !== null && relatorio.custo.usd !== null && (
            <div className="rel-custo">
              <span className="rel-custo-valor">
                Custo desta geração: <b>{reais(relatorio.custo.brl)}</b>
                <span className="aviso-suave"> ({dolares(relatorio.custo.usd)})</span>
              </span>
              <span className="rel-custo-detalhe">
                {tokens(relatorio.custo.tokens.entrada)} tokens lidos ·{" "}
                {tokens(relatorio.custo.tokens.saida)} escritos (
                {tokens(relatorio.custo.tokens.raciocinio)} de raciocínio) · {relatorio.custo.modelo} · US$ 1 ={" "}
                {reais(relatorio.custo.cotacao_usd_brl)} ({relatorio.custo.cotacao_origem})
              </span>
            </div>
          )}
          {relatorio.avisos.map((a) => (
            <p key={a} className="erro erro-pequeno">
              {a}
            </p>
          ))}
          <div className="rel-pessoas">
            {relatorio.pessoas.length === 0 && (
              <span className="aviso-suave">
                Ninguém cadastrado nas Configurações: o relatório não marca ninguém.
              </span>
            )}
            {relatorio.pessoas.map((p) => (
              <span key={p.nome + p.papel} className={p.slack_id ? "chip chip-azul" : "chip chip-medio"}>
                {p.nome} · {PAPEL[p.papel as keyof typeof PAPEL] ?? p.papel}
                {!p.slack_id && " · não achei no Slack"}
              </span>
            ))}
          </div>

          <div className="rel-previa" aria-label="Prévia do relatório">
            {relatorio.mensagens.map((m, i) => (
              <div key={i} className="rel-mensagem">
                <div className="rel-thread">
                  {m.papel
                    ? `Mensagem ${i + 1} no canal ${canal} · para ${m.para ?? "(ninguém cadastrado)"} · ${PAPEL[m.papel as keyof typeof PAPEL] ?? m.papel}`
                    : `Mensagem ${i + 1} no canal ${canal} · resumo`}
                </div>
                {relatorio.slack?.[i] ? (
                  <BlockKitPrevia mensagem={relatorio.slack[i]} nomes={nomes} />
                ) : (
                  <Mrkdwn texto={m.texto} nomes={nomes} />
                )}
              </div>
            ))}
          </div>

          {publicar.isError && (
            <p className="erro" role="alert">
              {publicar.error.message}
            </p>
          )}

          <div className="dialogo-acoes">
            {relatorio.publicado_em ? (
              <>
                <span className="publicado">
                  Publicado em {canal} por {relatorio.publicado_por}.
                </span>
                {relatorio.slack_link && (
                  <a className="btn btn-texto" href={relatorio.slack_link} target="_blank" rel="noreferrer">
                    Ver no Slack
                  </a>
                )}
                <button type="button" className="btn btn-primario" onClick={fechar}>
                  Fechar
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-texto"
                  disabled={publicar.isPending}
                  onClick={() => {
                    setRelatorio(null);
                    gerar.reset();
                  }}
                >
                  Gerar de novo
                </button>
                <button
                  type="button"
                  className="btn btn-primario"
                  disabled={publicar.isPending}
                  onClick={() =>
                    nome.trim() ? publicar.mutate(nome.trim()) : pedirNome((n) => publicar.mutate(n))
                  }
                >
                  {publicar.isPending ? "Publicando…" : `Publicar em ${canal}`}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </dialog>
  );
}
