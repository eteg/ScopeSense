import type { Achado, Citacao, Decisao } from "../api/client";
import slackLogo from "../assets/slack.png";
import { GRAVIDADE, iniciais, ORIGEM, pessoaDoAchado, quando, STATUS_DECIDIDO } from "../labels";

type Props = {
  achado: Achado;
  pessoas: Record<string, string | null | undefined>;
  modoSelecao: boolean;
  selecionado: boolean;
  ocupado: boolean;
  onSelecionar: () => void;
  onDecidir: (decisao: Decisao) => void;
};

function fonte(citacoes: Citacao[]): string {
  const c = citacoes[citacoes.length - 1];
  return [c.referencia ?? ORIGEM[c.origem], quando(c.data)].filter(Boolean).join(", ");
}

export function AlertCard(p: Props) {
  const { achado } = p;
  const pendente = achado.status === "pendente";
  const critico = achado.gravidade === "critico";
  const pessoa = pessoaDoAchado(achado, p.pessoas);
  const classes = [
    "alerta",
    p.selecionado && "selecionado",
    critico && pendente && "critico",
    !pendente && "decidido",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={classes}>
      <div className="alerta-topo">
        {p.modoSelecao && pendente && (
          <input
            type="checkbox"
            checked={p.selecionado}
            onChange={p.onSelecionar}
            aria-label={`Incluir no envio: ${achado.titulo}`}
          />
        )}
        <span className={`chip chip-${achado.gravidade}`}>{GRAVIDADE[achado.gravidade]}</span>
        <b className="alerta-titulo">{achado.titulo}</b>
      </div>

      <div className="lados">
        {achado.combinado && (
          <div className="caixa">
            <div className="caixa-rotulo">CONTRATO · {achado.combinado.referencia}</div>
            <div className="caixa-texto">“{achado.combinado.trecho}”</div>
          </div>
        )}
        <div className="caixa">
          <div className="caixa-rotulo">EVIDÊNCIA · {fonte(achado.execucao)}</div>
          {achado.execucao.map((c, i) => (
            <div key={i} className="caixa-texto">
              “{c.autor && achado.execucao.length > 1 ? `${c.autor}: ` : ""}
              {c.trecho}”
              {c.link && (
                <>
                  {" "}
                  <a href={c.link} target="_blank" rel="noreferrer" className="abrir">
                    abrir
                  </a>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="alerta-rodape">
        <span className="pessoa">
          <span className="avatar avatar-32">{iniciais(pessoa.nome)}</span>
          <span>
            <b>{pessoa.nome ?? "Sem responsável definido"}</b>
            <span className="papel">{pessoa.papel}</span>
          </span>
        </span>

        {pendente && !p.modoSelecao && (
          <>
            <button
              type="button"
              className={critico ? "btn btn-primario" : "btn btn-texto"}
              disabled={p.ocupado}
              onClick={() => p.onDecidir("aprovado")}
            >
              <img src={slackLogo} alt="" className={critico ? "slack slack-branco" : "slack"} />
              Notificar por Slack
            </button>
            <button
              type="button"
              className="btn btn-texto btn-neutro"
              disabled={p.ocupado}
              onClick={() => p.onDecidir("nao_e_desvio")}
            >
              Não é desvio
            </button>
          </>
        )}
        {!pendente && achado.status !== "pendente" && (
          <span className="status-decidido">
            {STATUS_DECIDIDO[achado.status]}
            {achado.decidido_por && ` · ${achado.decidido_por}`}
          </span>
        )}
      </div>
    </article>
  );
}
