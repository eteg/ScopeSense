import type { EtapaRelatorio } from "../api/client";
import slackLogo from "../assets/slack.png";
import { Alerta, Check } from "../icons";

// Ícone de cada etapa (inline, decorativos). Slack usa o logo do app.
const tracos: Record<string, string> = {
  contrato: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  pessoas: "M9 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8zM2 21c0-3.9 3.1-7 7-7s7 3.1 7 7M16 3.1a4 4 0 0 1 0 7.8M22 21c0-3.2-2-5.9-5-6.7",
  analise: "M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8zM5 2l.6 1.4L7 4l-1.4.6L5 6l-.6-1.4L3 4l1.4-.6z",
};

function IconeEtapa({ chave }: { chave: string }) {
  if (chave === "slack") return <img src={slackLogo} alt="" className="etapa-logo" />;
  if (chave === "gmail")
    return (
      <svg viewBox="0 0 24 24" className="etapa-logo" aria-hidden="true">
        <path d="M3 6.5V18h4v-8l5 3.8L17 10v8h4V6.5l-2-1.5-7 5.2L5 5z" fill="#EA4335" />
        <path d="M3 6.5 7 10V18H4a1 1 0 0 1-1-1z" fill="#4285F4" />
        <path d="M21 6.5 17 10V18h3a1 1 0 0 0 1-1z" fill="#34A853" />
        <path d="M17 10V5.6L19 5l2 1.5z" fill="#FBBC04" />
        <path d="M7 10V5.6L5 5 3 6.5z" fill="#C5221F" />
      </svg>
    );
  return (
    <svg
      viewBox="0 0 24 24"
      className="etapa-logo etapa-traco"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={tracos[chave] ?? "M12 12h.01"} />
    </svg>
  );
}

const ESPERA: Record<string, string> = {
  slack: "Aguardando…",
  gmail: "Aguardando…",
  contrato: "Aguardando…",
  pessoas: "Aguardando…",
  analise: "Aguardando a leitura das fontes…",
};

/** Lista das etapas da geração: o que está sendo lido agora e o que já foi encontrado. */
export function ProgressoRelatorio({ etapas }: { etapas: EtapaRelatorio[] }) {
  return (
    <ol className="etapas" aria-live="polite">
      {etapas.map((e) => (
        <li key={e.chave} className={`etapa etapa-${e.status}`}>
          <span className="etapa-icone">
            <IconeEtapa chave={e.chave} />
          </span>
          <span className="etapa-texto">
            <b>{e.titulo}</b>
            <span>{e.detalhe ?? ESPERA[e.chave] ?? "Aguardando…"}</span>
          </span>
          <span className="etapa-status" aria-label={e.status}>
            {e.status === "andamento" && <span className="girando" aria-hidden="true" />}
            {e.status === "ok" && <Check />}
            {e.status === "erro" && <Alerta />}
          </span>
        </li>
      ))}
    </ol>
  );
}
