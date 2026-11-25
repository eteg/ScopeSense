import type { ReactNode } from "react";

// Mostra o mrkdwn do Slack como ele vai aparecer: *negrito*, _itálico_, ~tachado~,
// > citação, <url|texto> e <@ID> (vira @Nome). Sem innerHTML: só nós do React.
const TOKEN = /(<@[A-Z0-9]+(?:\|[^>]*)?>|<https?:[^>|]+(?:\|[^>]+)?>|\*[^*\n]+\*|_[^_\n]+_|~[^~\n]+~)/g;

// O Slack recebe &, < e > escapados; na tela eles aparecem como caracteres normais.
const desfazerEntidades = (t: string) =>
  t
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/:repeat:/g, "🔁")
    .replace(/:satellite_antenna:/g, "📡");

function inline(texto: string, nomes: Record<string, string>, chave: string): ReactNode[] {
  return texto.split(TOKEN).map((parte, i) => {
    const k = `${chave}-${i}`;
    if (parte.startsWith("<@")) {
      const id = parte.slice(2, -1).split("|")[0];
      return (
        <span key={k} className="mrk-mencao" title={id}>
          @{nomes[id] ?? id}
        </span>
      );
    }
    if (parte.startsWith("<http")) {
      const [url, rotulo] = parte.slice(1, -1).split("|");
      return (
        <a key={k} href={url} target="_blank" rel="noreferrer">
          {rotulo ?? url}
        </a>
      );
    }
    if (parte.length > 2 && parte.startsWith("*") && parte.endsWith("*"))
      return <strong key={k}>{inline(parte.slice(1, -1), nomes, k)}</strong>;
    if (parte.length > 2 && parte.startsWith("_") && parte.endsWith("_"))
      return <em key={k}>{inline(parte.slice(1, -1), nomes, k)}</em>;
    if (parte.length > 2 && parte.startsWith("~") && parte.endsWith("~"))
      return <s key={k}>{parte.slice(1, -1)}</s>;
    return desfazerEntidades(parte);
  });
}

export function Mrkdwn({ texto, nomes }: { texto: string; nomes: Record<string, string> }) {
  return (
    <div className="mrk">
      {texto.split("\n").map((linha, i) =>
        linha.startsWith(">") ? (
          <blockquote key={i}>{inline(linha.replace(/^>\s?/, ""), nomes, `l${i}`)}</blockquote>
        ) : (
          <p key={i}>{linha ? inline(linha, nomes, `l${i}`) : " "}</p>
        ),
      )}
    </div>
  );
}
