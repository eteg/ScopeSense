import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, type Papel, type Pessoa } from "../api/client";
import { Alerta, Check, Lixeira, Mais, Traco, Voltar } from "../icons";
import { PAPEL } from "../labels";

type ItemMenu = {
  id: "pc" | "drive" | "gmail" | "meet";
  rotulo: string;
  dica: string;
  icone: string;
  divisor?: boolean;
};

// Menu do botão "+", como no design. Drive, Gmail e Meet ainda não têm conector.
const MENU: ItemMenu[] = [
  { id: "pc", rotulo: "Enviar arquivo", dica: "PDF do computador", icone: "M12 16V4M7 9l5-5 5 5M5 20h14" },
  { id: "drive", rotulo: "Buscar no Drive", dica: "Contratos, propostas, aditivos", icone: "M3 6h6l2 2h10v11H3z", divisor: true },
  { id: "gmail", rotulo: "Buscar no Gmail", dica: "E-mails do projeto", icone: "M3 6h18v12H3zM3 7l9 6 9-6" },
  { id: "meet", rotulo: "Buscar no Meet", dica: "Transcrições de reunião", icone: "M3 7h12v10H3zM15 10l6-3v10l-6-3" },
];

const PAPEIS = Object.keys(PAPEL) as Papel[];

const CATEGORIAS = [
  { chip: "chip-critico", rotulo: "Crítico", texto: "Risco legal ou trabalhista, ou entrega de algo que o contrato não prevê." },
  { chip: "chip-medio", rotulo: "Médio", texto: "Mudança de prazo ou SLA, ou promessa feita fora do contrato." },
  { chip: "chip-baixo", rotulo: "Baixo", texto: "Ajuste pequeno, já coberto pelo contrato." },
];

type Linha = { chave: number; nome: string; papel: Papel };
let proximaChave = 1;
const linha = (p?: Pessoa): Linha => ({
  chave: proximaChave++,
  nome: p?.nome ?? "",
  papel: p?.papel ?? "gestor",
});

export function Configuracoes() {
  const qc = useQueryClient();
  const projeto = useQuery({ queryKey: ["projeto"], queryFn: api.projeto });
  const arquivos = useQuery({ queryKey: ["arquivos"], queryFn: api.arquivos });
  const slack = useQuery({ queryKey: ["slack"], queryFn: api.slack, staleTime: 60_000 });

  const [canais, setCanais] = useState("");
  const [pessoas, setPessoas] = useState<Linha[]>([]);
  const [carregado, setCarregado] = useState(false);
  const [menuAberto, setMenuAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const inputArquivo = useRef<HTMLInputElement>(null);
  const barraArquivos = useRef<HTMLDivElement>(null);

  // Preenche o formulário uma vez, quando o projeto chega.
  useEffect(() => {
    if (!projeto.data || carregado) return;
    setCanais(
      projeto.data.canais_slack
        .map((c) => (c.nome ? `#${c.nome}` : (c.id ?? "")))
        .filter(Boolean)
        .join(", "),
    );
    setPessoas(projeto.data.envolvidos.length ? projeto.data.envolvidos.map(linha) : [linha()]);
    setCarregado(true);
  }, [projeto.data, carregado]);

  // Fecha o menu "+" com clique fora ou Esc.
  useEffect(() => {
    if (!menuAberto) return;
    const fora = (e: MouseEvent) => {
      if (!barraArquivos.current?.contains(e.target as Node)) setMenuAberto(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setMenuAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [menuAberto]);

  const enviar = useMutation({
    mutationFn: async (lista: File[]) => {
      for (const f of lista) await api.enviarArquivo(f);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["arquivos"] }),
  });

  const remover = useMutation({
    mutationFn: api.removerArquivo,
    onSettled: () => qc.invalidateQueries({ queryKey: ["arquivos"] }),
  });

  const salvar = useMutation({
    mutationFn: () =>
      api.salvarConfig({
        canais_slack: canais.split(",").map((c) => c.trim()).filter(Boolean),
        pessoas: pessoas
          .filter((p) => p.nome.trim())
          .map((p) => ({ nome: p.nome.trim(), papel: p.papel })),
      }),
    onSuccess: (dados) => {
      qc.setQueryData(["projeto"], dados);
      window.location.hash = "#/";
    },
  });

  const atualizar = (chave: number, campo: Partial<Linha>) =>
    setPessoas((ps) => ps.map((p) => (p.chave === chave ? { ...p, ...campo } : p)));

  const lista = (arquivos.data ?? []).filter((a) =>
    a.nome.toLowerCase().includes(busca.trim().toLowerCase()),
  );

  return (
    <>
      <header className="cabecalho">
        <div className="container cabecalho-interno">
          <div className="titulo-bloco">
            <a href="#/" className="migalha">
              <Voltar />
              {(projeto.data?.nome ?? "Projeto").toUpperCase()}
            </a>
            <h1>Configurações do projeto</h1>
          </div>
        </div>
      </header>

      <main className="container conteudo">
        <section aria-labelledby="p1" className="painel">
          <h2 id="p1">Contrato e arquivos</h2>
          <p className="painel-texto">
            Use o botão + para buscar no Google ou enviar um arquivo do computador.
          </p>
          <div className="barra-arquivos" ref={barraArquivos}>
            <button
              type="button"
              className="btn-mais"
              aria-label="Adicionar fonte"
              aria-haspopup="menu"
              aria-expanded={menuAberto}
              disabled={enviar.isPending}
              onClick={() => setMenuAberto((v) => !v)}
            >
              <Mais />
            </button>
            <input
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder={
                enviar.isPending ? "Enviando…" : "Adicione contrato, e-mails, reuniões ou PDFs"
              }
              aria-label="Buscar arquivos"
            />
            <input
              ref={inputArquivo}
              type="file"
              accept="application/pdf,.pdf"
              multiple
              hidden
              onChange={(e) => {
                const escolhidos = Array.from(e.target.files ?? []);
                if (escolhidos.length) enviar.mutate(escolhidos);
                e.target.value = "";
              }}
            />
            {menuAberto && (
              <div role="menu" className="menu">
                {MENU.map((m) => (
                  <div key={m.id}>
                    {m.divisor && <div className="menu-divisor" />}
                    <button
                      type="button"
                      role="menuitem"
                      className="menu-item"
                      disabled={m.id !== "pc"}
                      onClick={() => {
                        setMenuAberto(false);
                        inputArquivo.current?.click();
                      }}
                    >
                      <span className="menu-icone">
                        <Traco d={m.icone} />
                      </span>
                      <span>
                        <span className="menu-rotulo">{m.rotulo}</span>
                        <span className="menu-dica">
                          {m.id === "pc" ? m.dica : `${m.dica} · em breve`}
                        </span>
                      </span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {(enviar.isError || remover.isError) && (
            <p className="erro erro-pequeno" role="alert">
              {(enviar.error ?? remover.error)?.message}
            </p>
          )}

          {arquivos.isSuccess && arquivos.data.length === 0 ? (
            <div className="arquivos-vazio">
              Nenhum arquivo ainda. Comece pelo contrato e depois traga e-mails, reuniões e
              documentos de terceiros.
            </div>
          ) : (
            lista.length > 0 && (
              <div className="arquivos">
                {lista.map((a) => (
                  <div key={a.id} className="arquivo">
                    <span className="arquivo-nome">{a.nome}</span>
                    <span className="arquivo-origem">{a.origem}</span>
                    <span className="chip chip-azul">{a.tipo}</span>
                    <button
                      type="button"
                      className="btn-lixeira"
                      aria-label={`Remover ${a.nome}`}
                      title="Remover"
                      disabled={remover.isPending}
                      onClick={() => remover.mutate(a.id)}
                    >
                      <Lixeira />
                    </button>
                  </div>
                ))}
              </div>
            )
          )}
        </section>

        <section aria-labelledby="p2" className="painel">
          <h2 id="p2" className="painel-titulo-solto">
            Slack
          </h2>
          <div className="linha-campos">
            <label className="campo-contorno">
              <span>Canais lidos</span>
              <input
                type="text"
                value={canais}
                onChange={(e) => setCanais(e.target.value)}
                placeholder="Ex.: #projeto-alfa"
              />
            </label>
            <div className="selo-slack">
              {slack.isPending && <span className="selo selo-neutro">Verificando o Slack…</span>}
              {slack.data?.conectado && (
                <span className="selo selo-ok" title={slack.data.workspace ?? undefined}>
                  <Check />
                  Slack conectado
                </span>
              )}
              {slack.data && !slack.data.conectado && (
                <span className="selo selo-erro" title={slack.data.motivo ?? undefined}>
                  <Alerta />
                  Slack não conectado
                </span>
              )}
            </div>
          </div>
          {slack.data && !slack.data.conectado && slack.data.motivo && (
            <p className="painel-texto painel-texto-baixo">{slack.data.motivo}</p>
          )}
        </section>

        <section aria-labelledby="p3" className="painel">
          <h2 id="p3">Pessoas envolvidas</h2>
          <p className="painel-texto">
            Adicione quem acompanha o projeto e o papel de cada pessoa. O Radar usa o papel para
            decidir quem recebe cada desvio.
          </p>
          <div className="pessoas">
            {pessoas.map((p) => (
              <div key={p.chave} className="pessoa-linha">
                <label className="campo-contorno campo-arroba">
                  <span>Pessoa no Slack</span>
                  <i aria-hidden="true">@</i>
                  <input
                    type="text"
                    value={p.nome}
                    onChange={(e) => atualizar(p.chave, { nome: e.target.value })}
                    placeholder="Mariana Costa"
                    maxLength={120}
                  />
                </label>
                <label className="campo-contorno">
                  <span>Papel no projeto</span>
                  <select
                    value={p.papel}
                    onChange={(e) => atualizar(p.chave, { papel: e.target.value as Papel })}
                  >
                    {PAPEIS.map((papel) => (
                      <option key={papel} value={papel}>
                        {PAPEL[papel]}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="btn-lixeira btn-lixeira-40"
                  aria-label="Remover pessoa"
                  title="Remover"
                  onClick={() => setPessoas((ps) => ps.filter((x) => x.chave !== p.chave))}
                >
                  <Lixeira />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="btn btn-texto btn-adicionar"
            onClick={() => setPessoas((ps) => [...ps, linha()])}
          >
            <Mais size={18} />
            Adicionar pessoa
          </button>
        </section>

        <section aria-labelledby="p4" className="painel">
          <h2 id="p4" className="painel-titulo-categorias">
            Categorias
          </h2>
          <dl className="categorias">
            {CATEGORIAS.map((c) => (
              <div key={c.rotulo}>
                <dt>
                  <span className={`chip ${c.chip}`}>{c.rotulo}</span>
                </dt>
                <dd>{c.texto}</dd>
              </div>
            ))}
          </dl>
        </section>

        {salvar.isError && (
          <p className="erro" role="alert">
            Não foi possível salvar: {salvar.error.message}
          </p>
        )}
        <div className="acoes-rodape">
          <button
            type="button"
            className="btn btn-primario"
            disabled={!carregado || salvar.isPending}
            onClick={() => salvar.mutate()}
          >
            {salvar.isPending ? "Salvando…" : "Salvar alterações"}
          </button>
        </div>
      </main>
    </>
  );
}
