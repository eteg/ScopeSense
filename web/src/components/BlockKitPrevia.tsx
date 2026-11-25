import { Mrkdwn } from "../mrkdwn";

// Prévia de uma mensagem Block Kit do Slack, com só os blocos que o Radar usa:
// header, section (texto, fields, botão), context, divider e attachments com cor.
type Texto = { type: string; text: string };
type Bloco = {
  type: string;
  text?: Texto;
  fields?: Texto[];
  elements?: Texto[];
  accessory?: { type: string; text?: Texto; url?: string };
};
type Mensagem = { text?: string; blocks?: Bloco[]; attachments?: { color?: string; blocks?: Bloco[] }[] };

function BlocoView({ b, nomes }: { b: Bloco; nomes: Record<string, string> }) {
  if (b.type === "header") return <div className="bk-header">{b.text?.text}</div>;
  if (b.type === "divider") return <hr className="bk-divider" />;
  if (b.type === "context")
    return (
      <div className="bk-context">
        {(b.elements ?? []).map((e, i) => (
          <Mrkdwn key={i} texto={e.text} nomes={nomes} />
        ))}
      </div>
    );
  if (b.type === "section")
    return (
      <div className="bk-section">
        <div className="bk-section-texto">
          {b.text && <Mrkdwn texto={b.text.text} nomes={nomes} />}
          {b.fields && (
            <div className="bk-fields">
              {b.fields.map((f, i) => (
                <Mrkdwn key={i} texto={f.text} nomes={nomes} />
              ))}
            </div>
          )}
        </div>
        {b.accessory?.type === "button" && b.accessory.url && (
          <a className="bk-botao" href={b.accessory.url} target="_blank" rel="noreferrer">
            {b.accessory.text?.text}
          </a>
        )}
      </div>
    );
  return null;
}

export function BlockKitPrevia({ mensagem, nomes }: { mensagem: Mensagem; nomes: Record<string, string> }) {
  return (
    <div className="bk">
      {(mensagem.blocks ?? []).map((b, i) => (
        <BlocoView key={i} b={b} nomes={nomes} />
      ))}
      {(mensagem.attachments ?? []).map((a, i) => (
        <div key={i} className="bk-anexo" style={{ borderLeftColor: a.color ?? "#ccc" }}>
          {(a.blocks ?? []).map((b, j) => (
            <BlocoView key={j} b={b} nomes={nomes} />
          ))}
        </div>
      ))}
    </div>
  );
}
