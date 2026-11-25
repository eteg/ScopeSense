// Ícones de traço do design (inline, decorativos).
type P = { size?: number };
const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

export const Voltar = ({ size = 14 }: P) => (
  <svg {...base(size)} strokeWidth={2.2}>
    <path d="M15 6l-6 6 6 6" />
  </svg>
);
export const Play = ({ size = 18 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M8 5v14l11-7z" />
  </svg>
);
export const Baixar = ({ size = 16 }: P) => (
  <svg {...base(size)} strokeWidth={2}>
    <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
  </svg>
);
export const Seta = ({ size = 16 }: P) => (
  <svg {...base(size)} strokeWidth={2}>
    <path d="M7 10l5 5 5-5" />
  </svg>
);
export const Engrenagem = ({ size = 20 }: P) => (
  <svg {...base(size)} strokeWidth={1.8}>
    <path d="M12 15a3 3 0 1 0 0-6a3 3 0 1 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3a1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8a1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5a1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);
export const Mais = ({ size = 20 }: P) => (
  <svg {...base(size)} strokeWidth={2}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
export const Lixeira = ({ size = 20 }: P) => (
  <svg {...base(size)} strokeWidth={1.8}>
    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
  </svg>
);
export const Check = ({ size = 18 }: P) => (
  <svg {...base(size)} strokeWidth={2.4}>
    <path d="M5 12l5 5 9-10" />
  </svg>
);
export const Alerta = ({ size = 18 }: P) => (
  <svg {...base(size)} strokeWidth={2}>
    <path d="M12 8v5M12 16.5v.5M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </svg>
);
/** Ícone de linha a partir de um `d` (itens do menu "+"). */
export const Traco = ({ d, size = 20 }: P & { d: string }) => (
  <svg {...base(size)} strokeWidth={1.8}>
    <path d={d} />
  </svg>
);
