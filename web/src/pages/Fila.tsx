import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { aberto, type Alerta, api } from "../api/client";
import type { PedirNome } from "../App";
import slackLogo from "../assets/slack.png";
import { AlertCard } from "../components/AlertCard";
import { DetalhePainel } from "../components/DetalhePainel";
import { RelatorioDialog } from "../components/RelatorioDialog";
import { baixarCsv } from "../csv";
import { Baixar, Engrenagem, Play, Voltar } from "../icons";
import { ORIGEM, quando } from "../labels";

type Aba = "divergencias" | "pendencias";
// Aviso no rodapé. `desfazer` só existe quando dá para voltar atrás (o Slack não volta).
type Aviso = { texto: string; desfazer?: () => void } | null;

// "Marcar como resolvida" é só da tela (demonstração): fica guardado no navegador.
const CHAVE_RESOLVIDAS = "radar:pendencias-resolvidas";
function lerResolvidas(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(CHAVE_RESOLVIDAS) ?? "[]"));
  } catch {
    return new Set();
  }
}
function gravarResolvidas(ids: Set<string>) {
  try {
    localStorage.setItem(CHAVE_RESOLVIDAS, JSON.stringify([...ids]));
  } catch {
    /* armazenamento indisponível: vale só nesta sessão */
  }
}

export function Fila({ nome, pedirNome }: { nome: string; pedirNome: PedirNome }) {
  const qc = useQueryClient();
  const projeto = useQuery({ queryKey: ["projeto"], queryFn: api.projeto });
  const alertas = useQuery({ queryKey: ["alertas"], queryFn: api.alertas });
  const resumo = useQuery({ queryKey: ["resumo"], queryFn: api.resumo });

  const [aba, setAba] = useState<Aba>("divergencias");
  const [modoSelecao, setModoSelecao] = useState(false);
  const [selecao, setSelecao] = useState<Set<string>>(new Set());
  const [aviso, setAviso] = useState<Aviso>(null);
  const [relatorioAberto, setRelatorioAberto] = useState(false);
  const [detalheId, setDetalheId] = useState<string | null>(null);
  const [resolvidas, setResolvidas] = useState<Set<string>>(lerResolvidas);

  useEffect(() => gravarResolvidas(resolvidas), [resolvidas]);

  const pessoas = projeto.data?.pessoas ?? {};
  const canalCfg = projeto.data?.canais_slack.find((c) => c.id);
  const canal = canalCfg?.nome ? `#${canalCfg.nome}` : "canal do projeto";
  const todos = alertas.data ?? [];
  const divergencias = todos.filter(aberto);
  const pendencias = todos.filter((a) => a.status === "aprovado" && !resolvidas.has(a.id));
  const visiveis = aba === "divergencias" ? divergencias : pendencias;
  const detalhe = todos.find((a) => a.id === detalheId) ?? null;

  const impacto = useMemo(() => {
    const lidos = Object.values(resumo.data?.registros_lidos ?? {}).reduce((t, n) => t + n, 0);
    return {
      divergencias: todos.filter((a) => a.status !== "nao_e_desvio").length,
      lidos,
      criticos: divergencias.filter((a) => a.gravidade === "critico").length,
      medios: divergencias.filter((a) => a.gravidade === "medio").length,
      notificadas: todos.filter((a) => a.status === "aprovado").length,
      falsos: todos.filter((a) => a.status === "nao_e_desvio").length,
    };
  }, [todos, divergencias, resumo.data]);

  const lidosPorOrigem = Object.entries(resumo.data?.registros_lidos ?? {})
    .map(([origem, n]) => `${n} ${ORIGEM[origem as keyof typeof ORIGEM] ?? origem}`)
    .join(" · ");

  const atualizar = () => qc.invalidateQueries({ queryKey: ["alertas"] });

  // Notificar: posta no Slack (uma mensagem por alerta) e o alerta vai para Pendências.
  const notificar = useMutation({
    mutationFn: async ({ ids, quem }: { ids: string[]; quem: string }) => {
      for (const id of ids) await api.notificar(id, quem);
      return ids;
    },
    onSuccess: (ids) =>
      setAviso({
        texto:
          ids.length === 1
            ? `Alerta enviado para ${canal}`
            : `${ids.length} alertas enviados para ${canal}`,
      }),
    onSettled: atualizar,
  });

  const desfazer = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) await api.desfazer(id, nome || "?");
    },
    onSuccess: () => setAviso(null),
    onSettled: atualizar,
  });

  const naoE = useMutation({
    mutationFn: ({ id, quem }: { id: string; quem: string }) => api.decidir(id, "nao_e_desvio", quem),
    onSuccess: (_r, { id }) =>
      setAviso({
        texto: "Alerta tirado da fila: não é divergência",
        desfazer: () => desfazer.mutate([id]),
      }),
    onSettled: atualizar,
  });

  const comNome = useCallback(
    (acao: (quem: string) => void) => {
      if (nome.trim()) acao(nome.trim());
      else pedirNome(acao); // segue com o nome que a pessoa acabou de informar
    },
    [nome, pedirNome],
  );

  function enviarLote() {
    const ids = divergencias.filter((a) => selecao.has(a.id)).map((a) => a.id);
    if (!ids.length) return;
    comNome((quem) => notificar.mutate({ ids, quem }));
    setSelecao(new Set());
    setModoSelecao(false);
  }

  function resolver(id: string) {
    setResolvidas((r) => new Set(r).add(id));
    setAviso({
      texto: "Pendência marcada como resolvida",
      desfazer: () => {
        setResolvidas((r) => {
          const n = new Set(r);
          n.delete(id);
          return n;
        });
        setAviso(null);
      },
    });
  }

  const ocupado = notificar.isPending || naoE.isPending;
  const nSel = divergencias.filter((a) => selecao.has(a.id)).length;
  const tudoSelecionado = nSel === divergencias.length && divergencias.length > 0;
  const fecharDetalhe = useCallback(() => setDetalheId(null), []);

  return (
    <>
      <header className="cabecalho">
        <div className="container cabecalho-interno">
          <div className="titulo-bloco">
            <span className="migalha">
              <Voltar />
              PROJETOS
            </span>
            <h1>{projeto.data?.nome ?? "Projeto"}</h1>
            {projeto.data?.cliente && <p className="sub-titulo">{projeto.data.cliente}</p>}
          </div>
          {resumo.data?.ultimo_alerta_em && (
            <span className="ultima">Último alerta: {quando(resumo.data.ultimo_alerta_em)}</span>
          )}
          <a
            href="#/configuracoes"
            className="btn-icone"
            aria-label="Configurações do projeto"
            title="Configurações do projeto"
          >
            <Engrenagem />
          </a>
          <button
            type="button"
            className="btn btn-texto"
            title="Recarrega os alertas. Quem analisa é o bot do Slack ou o script do pipeline."
            onClick={() => qc.invalidateQueries()}
          >
            Atualizar
          </button>
          <button type="button" className="btn btn-primario" onClick={() => setRelatorioAberto(true)}>
            <Play />
            Gerar relatório
          </button>
        </div>
      </header>

      <main className="container conteudo">
        {alertas.isError && (
          <p className="erro" role="alert">
            Não consegui falar com a API: {alertas.error.message}. O backend está rodando na porta
            8000?
          </p>
        )}

        <section aria-label="Impacto" className="impacto">
          <div className="metrica">
            <div className="metrica-rotulo">Divergências encontradas</div>
            <div className="metrica-valor">{impacto.divergencias}</div>
            <div className="metrica-sub" title={lidosPorOrigem}>
              {impacto.lidos ? `em ${impacto.lidos} registros lidos` : "nenhum registro lido ainda"}
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Divergências críticas</div>
            <div className="metrica-valor">{impacto.criticos}</div>
            <div className="metrica-sub">
              e {impacto.medios} {impacto.medios === 1 ? "média" : "médias"} na fila
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Aguardando revisão</div>
            <div className="metrica-valor">{divergencias.length}</div>
            <div className="metrica-sub">
              {impacto.notificadas} {impacto.notificadas === 1 ? "notificada" : "notificadas"} por Slack
            </div>
          </div>
          <div className="metrica">
            <div className="metrica-rotulo">Não é divergência</div>
            <div className="metrica-valor">{impacto.falsos}</div>
            <div className="metrica-sub">falsos positivos que viram casos de teste</div>
          </div>
        </section>

        <section aria-labelledby="fila-h">
          <div role="tablist" aria-label="Alertas" className="abas-fila">
            <button
              type="button"
              role="tab"
              aria-selected={aba === "divergencias"}
              className={aba === "divergencias" ? "aba ativa" : "aba"}
              onClick={() => setAba("divergencias")}
            >
              Divergências <span className="aba-contador">{divergencias.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={aba === "pendencias"}
              className={aba === "pendencias" ? "aba ativa" : "aba"}
              onClick={() => {
                setAba("pendencias");
                setModoSelecao(false);
                setSelecao(new Set());
              }}
            >
              Pendências <span className="aba-contador">{pendencias.length}</span>
            </button>
          </div>

          <div className="fila-topo fila-topo-titulo">
            <div className="fila-titulo">
              <h2 id="fila-h">
                {aba === "divergencias"
                  ? divergencias.length === 1
                    ? "Foi encontrada 1 divergência"
                    : `Foram encontradas ${divergencias.length} divergências`
                  : pendencias.length === 1
                    ? "1 pendência notificada"
                    : `${pendencias.length} pendências notificadas`}
              </h2>
              <p>
                {aba === "divergencias"
                  ? "Pontos em que conversas no Slack, e-mails ou reuniões não batem com o contrato. Revise cada um e notifique o responsável pelo Slack."
                  : "Divergências que já foram enviadas ao responsável pelo Slack e ainda aguardam solução."}
              </p>
            </div>
            <div className="fila-acoes">
              {aba === "divergencias" &&
                (!modoSelecao ? (
                  <button
                    type="button"
                    className="btn-pequeno btn-contorno-azul"
                    disabled={!divergencias.length}
                    onClick={() => {
                      setModoSelecao(true);
                      setAviso(null);
                    }}
                  >
                    <img src={slackLogo} alt="" className="slack slack-16" />
                    Enviar alertas em lote
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-pequeno btn-texto"
                    onClick={() =>
                      setSelecao(tudoSelecionado ? new Set() : new Set(divergencias.map((a) => a.id)))
                    }
                  >
                    {tudoSelecionado ? "Desmarcar todos" : "Selecionar todos"}
                  </button>
                ))}
              <button
                type="button"
                className="btn-pequeno filtro"
                disabled={!visiveis.length}
                onClick={() => baixarCsv(visiveis, pessoas)}
              >
                <Baixar />
                Baixar CSV
              </button>
            </div>
          </div>

          <div className="lista lista-compacta">
            {alertas.isPending && <p className="vazio">Carregando alertas…</p>}
            {alertas.isSuccess && visiveis.length === 0 && (
              <p className="vazio">
                {aba === "divergencias"
                  ? "Nenhuma divergência nova. Gere o relatório ou rode a análise para buscar de novo."
                  : "Nenhuma pendência aberta."}
              </p>
            )}
            {visiveis.map((a: Alerta) => (
              <AlertCard
                key={a.id}
                alerta={a}
                modo={aba === "divergencias" ? "divergencia" : "pendencia"}
                modoSelecao={modoSelecao}
                selecionado={selecao.has(a.id)}
                ocupado={ocupado}
                onSelecionar={() => {
                  const n = new Set(selecao);
                  if (n.has(a.id)) n.delete(a.id);
                  else n.add(a.id);
                  setSelecao(n);
                }}
                onAbrir={() => setDetalheId(a.id)}
                onNotificar={() => comNome((quem) => notificar.mutate({ ids: [a.id], quem }))}
                onNaoE={() => comNome((quem) => naoE.mutate({ id: a.id, quem }))}
                onResolver={() => resolver(a.id)}
              />
            ))}
          </div>

          {(notificar.isError || naoE.isError) && (
            <p className="erro" role="alert">
              Não foi possível concluir: {(notificar.error ?? naoE.error)?.message}
            </p>
          )}
          {notificar.isPending && (
            <p className="carregando" role="status">
              Enviando para {canal}…
            </p>
          )}

          {modoSelecao && (
            <div role="region" aria-label="Enviar alertas em lote" className="barra-lote">
              <span className="lote-contagem">
                {nSel === 0
                  ? "Marque os alertas para enviar"
                  : nSel === 1
                    ? "1 alerta selecionado"
                    : `${nSel} alertas selecionados`}
              </span>
              <span className="suave">Enviar para</span>
              <span className="destino">{canal}</span>
              <span className="espaco" />
              <button
                type="button"
                className="btn btn-texto btn-neutro"
                onClick={() => {
                  setModoSelecao(false);
                  setSelecao(new Set());
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn-primario"
                disabled={nSel === 0 || ocupado}
                onClick={enviarLote}
              >
                <img src={slackLogo} alt="" className="slack slack-branco" />
                Enviar por Slack
              </button>
            </div>
          )}

          {aviso && !modoSelecao && (
            <div role="status" className="aviso">
              <span>{aviso.texto}</span>
              {aviso.desfazer && (
                <button type="button" disabled={desfazer.isPending} onClick={aviso.desfazer}>
                  Desfazer
                </button>
              )}
            </div>
          )}
        </section>
      </main>
      <DetalhePainel
        alerta={detalhe}
        pessoas={pessoas}
        ocupado={ocupado}
        onFechar={fecharDetalhe}
        onNaoE={() => {
          if (!detalhe) return;
          const id = detalhe.id;
          setDetalheId(null);
          comNome((quem) => naoE.mutate({ id, quem }));
        }}
        onNotificar={() => {
          if (!detalhe) return;
          const id = detalhe.id;
          setDetalheId(null);
          comNome((quem) => notificar.mutate({ ids: [id], quem }));
        }}
      />
      <RelatorioDialog
        aberto={relatorioAberto}
        onFechar={() => setRelatorioAberto(false)}
        nome={nome}
        pedirNome={pedirNome}
      />
    </>
  );
}
