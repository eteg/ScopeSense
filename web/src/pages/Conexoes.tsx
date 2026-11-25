import { useEffect, useMemo, useRef, useState } from "react";

import slackLogo from "../assets/slack.png";
import { Check, Mais, Voltar } from "../icons";

// TELA DE DEMONSTRAÇÃO (100% simulada): nenhuma conexão aqui é real. O estado fica
// no navegador. As fontes de verdade do Radar continuam configuradas no .env.

type Categoria = "Comunicação" | "Documentos" | "Gestão de projetos" | "Código" | "Personalizado";

type Servidor = {
  id: string;
  nome: string;
  descricao: string;
  categoria: Categoria;
  cor: string; // cor do monograma (quando não há logo)
  conta?: string;
  escopo?: string;
  liberadas?: number;
  total?: number;
  ferramentas?: string[];
  ultimaLeitura?: string;
};

const CONECTADOS_INICIAIS: Servidor[] = [
  {
    id: "slack",
    nome: "Slack",
    descricao: "Mensagens e threads dos canais do projeto",
    categoria: "Comunicação",
    cor: "#4A154B",
    conta: "eteg-team.slack.com",
    escopo: "#proj-smartfit",
    liberadas: 6,
    total: 18,
    ferramentas: [
      "slack_read_channel",
      "slack_read_thread",
      "slack_list_channels",
      "slack_read_user_profile",
      "slack_list_channel_members",
      "slack_get_reactions",
    ],
    ultimaLeitura: "há 2 min",
  },
  {
    id: "drive",
    nome: "Google Drive",
    descricao: "Contrato, aditivos, propostas e atas",
    categoria: "Documentos",
    cor: "#1A73E8",
    conta: "Pasta “Projeto SmartFit”",
    escopo: "1 pasta e subpastas",
    liberadas: 5,
    total: 12,
    ferramentas: [
      "search_files",
      "read_file_content",
      "get_file_metadata",
      "list_recent_files",
      "download_file_content",
    ],
    ultimaLeitura: "há 6 min",
  },
  {
    id: "gmail",
    nome: "Gmail",
    descricao: "E-mails com o cliente e a equipe do projeto",
    categoria: "Comunicação",
    cor: "#EA4335",
    conta: "projetos@eteg.com.br",
    escopo: "Cliente + termo “SmartFit”",
    liberadas: 4,
    total: 21,
    ferramentas: ["search_threads", "get_thread", "get_message", "list_labels"],
    ultimaLeitura: "há 4 min",
  },
];

const DISPONIVEIS_INICIAIS: Servidor[] = [
  { id: "calendar", nome: "Google Calendar", descricao: "Reuniões e marcos do cronograma", categoria: "Documentos", cor: "#1A73E8" },
  { id: "meet", nome: "Google Meet", descricao: "Transcrições das reuniões com o cliente", categoria: "Comunicação", cor: "#00897B" },
  { id: "teams", nome: "Microsoft Teams", descricao: "Chats e reuniões de clientes que usam Teams", categoria: "Comunicação", cor: "#5059C9" },
  { id: "outlook", nome: "Outlook", descricao: "E-mails de clientes no Microsoft 365", categoria: "Comunicação", cor: "#0F6CBD" },
  { id: "jira", nome: "Jira", descricao: "Tarefas, bugs reabertos e escopo das sprints", categoria: "Gestão de projetos", cor: "#1868DB" },
  { id: "clickup", nome: "ClickUp", descricao: "Tarefas e prazos do projeto", categoria: "Gestão de projetos", cor: "#7B68EE" },
  { id: "confluence", nome: "Confluence", descricao: "Requisitos e decisões documentadas", categoria: "Documentos", cor: "#1868DB" },
  { id: "notion", nome: "Notion", descricao: "Atas, especificações e combinados", categoria: "Documentos", cor: "#191C20" },
  { id: "github", nome: "GitHub", descricao: "Entregas, PRs e o que foi para produção", categoria: "Código", cor: "#24292F" },
];

const CATEGORIAS: ("Todas" | Categoria)[] = [
  "Todas",
  "Comunicação",
  "Documentos",
  "Gestão de projetos",
  "Código",
];

const CHAVE = "radar:conexoes-demo-v2";

type Estado = { conectados: Servidor[]; disponiveis: Servidor[] };

function ler(): Estado {
  try {
    const salvo = localStorage.getItem(CHAVE);
    if (salvo) return JSON.parse(salvo) as Estado;
  } catch {
    /* sem armazenamento: começa do padrão */
  }
  return { conectados: CONECTADOS_INICIAIS, disponiveis: DISPONIVEIS_INICIAIS };
}

function Logo({ s }: { s: Servidor }) {
  if (s.id === "slack") return <img src={slackLogo} alt="" className="cx-logo-img" />;
  if (s.id === "gmail")
    return (
      <svg viewBox="0 0 24 24" className="cx-logo-img" aria-hidden="true">
        <path d="M3 6.5V18h4v-8l5 3.8L17 10v8h4V6.5l-2-1.5-7 5.2L5 5z" fill="#EA4335" />
        <path d="M3 6.5 7 10V18H4a1 1 0 0 1-1-1z" fill="#4285F4" />
        <path d="M21 6.5 17 10V18h3a1 1 0 0 0 1-1z" fill="#34A853" />
        <path d="M17 10V5.6L19 5l2 1.5z" fill="#FBBC04" />
        <path d="M7 10V5.6L5 5 3 6.5z" fill="#C5221F" />
      </svg>
    );
  if (s.id === "drive")
    return (
      <svg viewBox="0 0 24 24" className="cx-logo-img" aria-hidden="true">
        <path d="M8.3 3h7.4l6.1 10.5h-7.4z" fill="#FFBA00" />
        <path d="M2.2 13.5 5.9 20l6.1-10.5L8.3 3z" fill="#0066DA" />
        <path d="M5.9 20h12.2l3.7-6.5H9.6z" fill="#00AC47" />
      </svg>
    );
  const iniciais = s.nome
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2);
  return (
    <span className="cx-monograma" style={{ background: s.cor }} aria-hidden="true">
      {iniciais}
    </span>
  );
}

export function Conexoes() {
  const [estado, setEstado] = useState<Estado>(ler);
  const [busca, setBusca] = useState("");
  const [categoria, setCategoria] = useState<(typeof CATEGORIAS)[number]>("Todas");
  const [conectando, setConectando] = useState<string | null>(null);
  const [aberto, setAberto] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [dialogo, setDialogo] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE, JSON.stringify(estado));
    } catch {
      /* vale só nesta sessão */
    }
  }, [estado]);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), 3500);
    return () => clearTimeout(t);
  }, [aviso]);

  const totalFerramentas = estado.conectados.reduce((t, s) => t + (s.liberadas ?? 0), 0);
  const disponiveis = useMemo(
    () =>
      estado.disponiveis.filter(
        (s) =>
          (categoria === "Todas" || s.categoria === categoria) &&
          `${s.nome} ${s.descricao}`.toLowerCase().includes(busca.trim().toLowerCase()),
      ),
    [estado.disponiveis, categoria, busca],
  );

  function conectar(s: Servidor) {
    setConectando(s.id);
    setTimeout(() => {
      setEstado((e) => ({
        conectados: [
          ...e.conectados,
          {
            ...s,
            conta: s.conta ?? "Conta da ETEG",
            escopo: s.escopo ?? "Só o projeto SmartFit",
            liberadas: s.liberadas ?? 3 + (s.nome.length % 4),
            total: s.total ?? 10 + (s.nome.length % 9),
            ferramentas: s.ferramentas ?? ["search", "read", "list"],
            ultimaLeitura: "agora",
          },
        ],
        disponiveis: e.disponiveis.filter((x) => x.id !== s.id),
      }));
      setConectando(null);
      setAviso(`${s.nome} conectado. O Radar já pode ler essa fonte.`);
    }, 1600);
  }

  function desconectar(s: Servidor) {
    setEstado((e) => ({
      conectados: e.conectados.filter((x) => x.id !== s.id),
      disponiveis: [s, ...e.disponiveis],
    }));
    setAviso(`${s.nome} desconectado.`);
  }

  return (
    <>
      <header className="cabecalho">
        <div className="container cabecalho-interno">
          <div className="titulo-bloco">
            <a href="#/" className="migalha">
              <Voltar />
              FILA DE ALERTAS
            </a>
            <h1>Conexões</h1>
            <p className="sub-titulo">
              Fontes que o Radar lê por MCP (Model Context Protocol). Todas em modo somente
              leitura.
            </p>
          </div>
          <button type="button" className="btn btn-primario" onClick={() => setDialogo(true)}>
            <Mais size={18} />
            Adicionar servidor MCP
          </button>
        </div>
      </header>

      <main className="container conteudo">
        <section aria-label="Resumo das conexões" className="impacto">
          <div className="metrica">
            <div className="metrica-rotulo">Fontes conectadas</div>
            <div className="metrica-valor">{estado.conectados.length}</div>
            <div className="metrica-sub">todas funcionando</div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Ferramentas liberadas</div>
            <div className="metrica-valor">{totalFerramentas}</div>
            <div className="metrica-sub">só de leitura, escritas bloqueadas</div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Última leitura</div>
            <div className="metrica-valor">2 min</div>
            <div className="metrica-sub">no Slack do projeto</div>
          </div>
        </section>

        <section aria-labelledby="cx-conectados">
          <div className="cx-secao-topo">
            <h2 id="cx-conectados">Conectados</h2>
            <span className="cx-contagem">{estado.conectados.length}</span>
          </div>
          <div className="cx-grade">
            {estado.conectados.map((s) => (
              <article key={s.id} className="cx-card">
                <div className="cx-card-topo">
                  <span className="cx-logo">
                    <Logo s={s} />
                  </span>
                  <span className="cx-nome">
                    <b>{s.nome}</b>
                    <span>{s.descricao}</span>
                  </span>
                  <span className="cx-status">
                    <span className="cx-ponto" aria-hidden="true" />
                    Conectado
                  </span>
                </div>
                <dl className="cx-dados">
                  <div>
                    <dt>Conta</dt>
                    <dd>{s.conta}</dd>
                  </div>
                  <div>
                    <dt>Escopo</dt>
                    <dd>{s.escopo}</dd>
                  </div>
                  <div>
                    <dt>Ferramentas</dt>
                    <dd>
                      {s.liberadas} liberadas de {s.total}
                    </dd>
                  </div>
                  <div>
                    <dt>Última leitura</dt>
                    <dd>{s.ultimaLeitura}</dd>
                  </div>
                </dl>
                <span className="chip chip-azul cx-chip">Somente leitura</span>
                {aberto === s.id && (
                  <ul className="cx-ferramentas" aria-label={`Ferramentas de ${s.nome}`}>
                    {(s.ferramentas ?? []).map((f) => (
                      <li key={f}>
                        <Check size={14} />
                        <code>{f}</code>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="cx-acoes">
                  <button
                    type="button"
                    className="btn btn-texto"
                    aria-expanded={aberto === s.id}
                    onClick={() => setAberto(aberto === s.id ? null : s.id)}
                  >
                    {aberto === s.id ? "Esconder ferramentas" : "Ver ferramentas"}
                  </button>
                  <button type="button" className="btn btn-texto btn-neutro" onClick={() => desconectar(s)}>
                    Desconectar
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section aria-labelledby="cx-disponiveis">
          <div className="cx-secao-topo cx-secao-topo-filtros">
            <h2 id="cx-disponiveis">Disponíveis para conectar</h2>
            <label className="cx-busca">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true">
                <path d="M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14zM20 20l-4-4" />
              </svg>
              <input
                type="search"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar servidor MCP"
                aria-label="Buscar servidor MCP"
              />
            </label>
          </div>
          <div className="cx-categorias">
            {CATEGORIAS.map((c) => (
              <button
                key={c}
                type="button"
                className={categoria === c ? "btn-pequeno filtro ativo" : "btn-pequeno filtro"}
                aria-pressed={categoria === c}
                onClick={() => setCategoria(c)}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="cx-grade cx-grade-disponiveis">
            {disponiveis.map((s) => (
              <article key={s.id} className="cx-card cx-card-disponivel">
                <div className="cx-card-topo">
                  <span className="cx-logo">
                    <Logo s={s} />
                  </span>
                  <span className="cx-nome">
                    <b>{s.nome}</b>
                    <span>{s.descricao}</span>
                  </span>
                </div>
                <div className="cx-acoes">
                  <span className="cx-categoria">{s.categoria}</span>
                  <button
                    type="button"
                    className="btn btn-primario cx-conectar"
                    disabled={conectando !== null}
                    onClick={() => conectar(s)}
                  >
                    {conectando === s.id ? (
                      <>
                        <span className="girando cx-girando" aria-hidden="true" />
                        Conectando…
                      </>
                    ) : (
                      "Conectar"
                    )}
                  </button>
                </div>
              </article>
            ))}
            {disponiveis.length === 0 && (
              <p className="vazio cx-vazio">Nenhum servidor com esse filtro.</p>
            )}
          </div>
        </section>
        <p className="cx-nota">
          Demonstração: as conexões desta tela são simuladas e ficam só neste navegador.
        </p>
      </main>

      {aviso && (
        <div role="status" className="aviso cx-aviso">
          <span>{aviso}</span>
        </div>
      )}

      <NovoServidor
        aberto={dialogo}
        onFechar={() => setDialogo(false)}
        onConectar={(nome, url) => {
          setDialogo(false);
          conectar({
            id: `custom-${Date.now()}`,
            nome,
            descricao: url,
            categoria: "Personalizado",
            cor: "#44474E",
          });
        }}
      />
    </>
  );
}

function NovoServidor({
  aberto,
  onFechar,
  onConectar,
}: {
  aberto: boolean;
  onFechar: () => void;
  onConectar: (nome: string, url: string) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [nome, setNome] = useState("");
  const [url, setUrl] = useState("https://");
  const [auth, setAuth] = useState("oauth");

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (aberto && !dlg.open) {
      setNome("");
      setUrl("https://");
      dlg.showModal();
    }
    if (!aberto && dlg.open) dlg.close();
  }, [aberto]);

  const valido = nome.trim().length > 1 && /^https:\/\/[^\s.]+\.[^\s]+/.test(url.trim());

  return (
    <dialog ref={ref} className="dialogo" aria-labelledby="dlg-mcp" onClose={onFechar}>
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault();
          if (valido) onConectar(nome.trim(), url.trim());
        }}
      >
        <h2 id="dlg-mcp">Adicionar servidor MCP</h2>
        <p>Informe o endereço do servidor. O Radar só libera as ferramentas de leitura.</p>
        <div className="cx-form">
          <label className="campo-contorno">
            <span>Nome</span>
            <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: CRM da ETEG" autoFocus />
          </label>
          <label className="campo-contorno">
            <span>URL do servidor</span>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://mcp.exemplo.com/mcp" />
          </label>
          <label className="campo-contorno">
            <span>Autenticação</span>
            <select value={auth} onChange={(e) => setAuth(e.target.value)}>
              <option value="oauth">OAuth (entrar com a conta)</option>
              <option value="token">Token de acesso</option>
              <option value="nenhuma">Sem autenticação</option>
            </select>
          </label>
        </div>
        <div className="dialogo-acoes">
          <button type="button" className="btn btn-texto" onClick={onFechar}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primario" disabled={!valido}>
            Conectar
          </button>
        </div>
      </form>
    </dialog>
  );
}
