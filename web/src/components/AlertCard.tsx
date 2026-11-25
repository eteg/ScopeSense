import { type AcaoDecisao, aberto, type Alerta, type Papel } from "../api/client";
import { GRAVIDADE, iniciais, ORIGEM, pessoaDoAlerta, porcento, quando, STATUS } from "../labels";

type Props = {
  alerta: Alerta;
  pessoas: Partial<Record<Papel, string | null>>;
  modoSelecao: boolean;
  selecionado: boolean;
  ocupado: boolean;
  onSelecionar: () => void;
  onDecidir: (acao: AcaoDecisao) => void;
};

function fonte(a: Alerta): string {
  const e = a.evidencia;
  if (!e) return "registro " + a.id;
  const onde = e.canal ? `${ORIGEM[e.origem]} #${e.canal.replace(/^#/, "")}` : ORIGEM[e.origem];
  return [onde, quando(e.data)].filter(Boolean).join(", ");
}

export function AlertCard(p: Props) {
  const { alerta: a } = p;
  const pendente = aberto(a);
  const critico = a.gravidade === "critico";
  const pessoa = pessoaDoAlerta(a, p.pessoas);
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
            aria-label={`Incluir na aprovação: ${a.titulo}`}
          />
        )}
        <span className={`chip chip-${a.gravidade}`}>{GRAVIDADE[a.gravidade]}</span>
        <b className="alerta-titulo">{a.titulo}</b>
        {a.acao === "resumo" && <span className="chip chip-contorno">No resumo</span>}
        <span className="confianca" title="Confiança do modelo">
          {porcento(a.confianca)}
        </span>
      </div>

      <div className="lados">
        <div className="caixa">
          <div className="caixa-rotulo">CONTRATO · CL. {a.clausula}</div>
          <div className="caixa-texto">“{a.trecho_contrato}”</div>
        </div>
        <div className="caixa">
          <div className="caixa-rotulo">EVIDÊNCIA · {fonte(a)}</div>
          <div className="caixa-texto">
            “{a.evidencia?.autor ? `${a.evidencia.autor}: ` : ""}
            {a.trecho_evidencia}”
            {a.evidencia?.link && (
              <>
                {" "}
                <a href={a.evidencia.link} target="_blank" rel="noreferrer" className="abrir">
                  abrir
                </a>
              </>
            )}
          </div>
        </div>
      </div>
      <p className="justificativa">{a.justificativa}</p>

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
              onClick={() => p.onDecidir("aprovar")}
            >
              Aprovar
            </button>
            <button
              type="button"
              className="btn btn-texto btn-neutro"
              disabled={p.ocupado}
              onClick={() => p.onDecidir("descartar")}
            >
              Descartar
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
        {!pendente && (
          <span className="status-decidido">
            {STATUS[a.status] ?? a.status}
            {a.decisao && ` · ${a.decisao.quem}, ${quando(a.decisao.quando)}`}
          </span>
        )}
      </div>
    </article>
  );
}
