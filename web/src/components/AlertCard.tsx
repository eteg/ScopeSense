import type { Alerta } from "../api/client";
import slackLogo from "../assets/slack.png";
import { dia, GRAVIDADE } from "../labels";

type Props = {
  alerta: Alerta;
  modo: "divergencia" | "pendencia";
  modoSelecao: boolean;
  selecionado: boolean;
  ocupado: boolean;
  onSelecionar: () => void;
  onAbrir: () => void;
  onNotificar: () => void;
  onNaoE: () => void;
  onResolver: () => void;
};

/** Cartão compacto do design: severidade e título à esquerda, ações à direita. */
export function AlertCard(p: Props) {
  const { alerta: a } = p;
  const critico = a.gravidade === "critico";
  const classes = [
    "alerta",
    "alerta-compacto",
    p.selecionado && "selecionado",
    critico && p.modo === "divergencia" && "critico",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={classes}>
      {p.modoSelecao && p.modo === "divergencia" && (
        <input
          type="checkbox"
          checked={p.selecionado}
          onChange={p.onSelecionar}
          aria-label={`Incluir no envio: ${a.titulo}`}
        />
      )}
      <button
        type="button"
        className="alerta-abrir"
        onClick={p.onAbrir}
        aria-label={`Ver detalhes: ${a.titulo}`}
      >
        <span className="alerta-cabeca">
          <span className={`chip chip-${a.gravidade}`}>{GRAVIDADE[a.gravidade]}</span>
          <span className="alerta-categoria">{a.categoria}</span>
        </span>
        <span className="alerta-titulo">{a.titulo}</span>
      </button>

      <span className="alerta-acoes">
        {p.modo === "pendencia" && (
          <>
            <span className="alerta-notificado">
              Notificado por Slack · {dia(a.decisao?.quando) ?? "hoje"}
            </span>
            <button type="button" className="btn btn-contorno" onClick={p.onResolver}>
              Marcar como resolvida
            </button>
          </>
        )}
        {p.modo === "divergencia" && !p.modoSelecao && (
          <>
            <button
              type="button"
              className="btn btn-texto btn-neutro"
              disabled={p.ocupado}
              onClick={p.onNaoE}
            >
              Não é divergência
            </button>
            <button
              type="button"
              className={critico ? "btn btn-primario" : "btn btn-texto"}
              disabled={p.ocupado}
              onClick={p.onNotificar}
            >
              <img src={slackLogo} alt="" className={critico ? "slack slack-branco" : "slack slack-16"} />
              Notificar por Slack
            </button>
          </>
        )}
      </span>
    </article>
  );
}
