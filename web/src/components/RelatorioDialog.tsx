import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, type Relatorio } from "../api/client";
import type { PedirNome } from "../App";
import { PAPEL } from "../labels";
import { Mrkdwn } from "../mrkdwn";

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

/** Gerar relatório → revisar a prévia → publicar no canal do projeto. */
export function RelatorioDialog({ aberto, onFechar, nome, pedirNome }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [dias, setDias] = useState(7);
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);

  const gerar = useMutation({ mutationFn: () => api.gerarRelatorio(dias), onSuccess: setRelatorio });
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
            <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
              {PERIODOS.map((p) => (
                <option key={p.dias} value={p.dias}>
                  {p.rotulo}
                </option>
              ))}
            </select>
          </label>
          {gerar.isPending && (
            <p className="carregando" role="status">
              Lendo o Slack, os e-mails e o contrato e escrevendo o relatório… leva de 1 a 2 minutos.
            </p>
          )}
          {gerar.isError && (
            <p className="erro" role="alert">
              {gerar.error.message}
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
                    ? `Resposta na thread · para ${m.para ?? "(ninguém cadastrado)"} · ${PAPEL[m.papel as keyof typeof PAPEL] ?? m.papel}`
                    : `Mensagem principal no canal ${canal}`}
                </div>
                <Mrkdwn texto={m.texto} nomes={nomes} />
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
