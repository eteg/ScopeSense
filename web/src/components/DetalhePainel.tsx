import { useEffect } from "react";

import { aberto, type Alerta, type Papel } from "../api/client";
import slackLogo from "../assets/slack.png";
import { dia, GRAVIDADE, ORIGEM, PAPEL, quando, SEVERIDADE } from "../labels";

type Props = {
  alerta: Alerta | null;
  pessoas: Partial<Record<Papel, string | null>>;
  ocupado: boolean;
  onFechar: () => void;
  onNotificar: () => void;
  onNaoE: () => void;
};

/** Painel lateral com o detalhe da divergência (abre ao clicar no cartão). */
export function DetalhePainel({ alerta: a, pessoas, ocupado, onFechar, onNotificar, onNaoE }: Props) {
  useEffect(() => {
    if (!a) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onFechar();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [a, onFechar]);

  if (!a) return null;
  const e = a.evidencia;
  const onde = e
    ? [e.canal ? `${ORIGEM[e.origem]} #${e.canal.replace(/^#/, "")}` : ORIGEM[e.origem], e.autor, quando(e.data)]
        .filter(Boolean)
        .join(" · ")
    : `Registro ${a.id}`;
  const pessoa = a.responsavel ? (pessoas[a.responsavel] ?? null) : null;
  const bruto = a.justificativa.replace("[gabarito]", "").trim();
  const identificado = bruto.charAt(0).toUpperCase() + bruto.slice(1);

  return (
    <>
      <div className="painel-fundo" onClick={onFechar} aria-hidden="true" />
      <aside className="painel-detalhe" role="dialog" aria-modal="true" aria-labelledby="det-h">
        <div className="detalhe-topo">
          <span className={`chip chip-${a.gravidade}`}>{GRAVIDADE[a.gravidade]}</span>
          <span className="alerta-categoria">{a.categoria}</span>
          <button type="button" className="btn-fechar" onClick={onFechar} aria-label="Fechar">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <h2 id="det-h">{a.titulo}</h2>

        <div className="detalhe-rotulo">O QUE FOI IDENTIFICADO</div>
        <p className="detalhe-texto">{identificado}</p>

        <div className="detalhe-rotulo">O QUE O CONTRATO DIZ · CL. {a.clausula}</div>
        <div className="detalhe-caixa">“{a.trecho_contrato.replace(/\*\*/g, "")}”</div>

        <div className="detalhe-rotulo">ONDE APARECEU · {onde}</div>
        <div className="detalhe-caixa">
          “{a.trecho_evidencia}”
          {e?.link && (
            <>
              {" "}
              <a href={e.link} target="_blank" rel="noreferrer" className="abrir">
                abrir
              </a>
            </>
          )}
        </div>

        <div className="detalhe-grade">
          <div className="detalhe-quadro">
            <div className="detalhe-quadro-rotulo">Severidade</div>
            <div className="detalhe-quadro-valor">
              <span className={`chip chip-${a.gravidade}`}>{GRAVIDADE[a.gravidade]}</span>
            </div>
            <div className="detalhe-quadro-sub">{SEVERIDADE[a.gravidade]}</div>
          </div>
          <div className="detalhe-quadro">
            <div className="detalhe-quadro-rotulo">Responsável</div>
            <div className="detalhe-quadro-valor">{pessoa ?? "Ninguém cadastrado"}</div>
            <div className="detalhe-quadro-sub">{a.responsavel ? PAPEL[a.responsavel] : "Sem papel definido"}</div>
          </div>
        </div>

        <div className="detalhe-acoes">
          {aberto(a) ? (
            <>
              <button type="button" className="btn btn-contorno btn-neutro" disabled={ocupado} onClick={onNaoE}>
                Não é divergência
              </button>
              <button type="button" className="btn btn-primario" disabled={ocupado} onClick={onNotificar}>
                <img src={slackLogo} alt="" className="slack slack-branco" />
                Notificar por Slack
              </button>
            </>
          ) : (
            <span className="alerta-notificado">
              {a.status === "aprovado"
                ? `Notificado por Slack · ${dia(a.decisao?.quando) ?? "hoje"}${a.decisao ? ` · ${a.decisao.quem}` : ""}`
                : "Marcado como não é divergência"}
            </span>
          )}
        </div>
      </aside>
    </>
  );
}
