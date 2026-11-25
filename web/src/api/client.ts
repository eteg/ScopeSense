// Cliente da API do Radar. Os tipos vêm do OpenAPI do FastAPI (npm run gen:api),
// então o frontend usa os mesmos modelos do backend.
import type { components } from "./schema";

type S = components["schemas"];
export type Alerta = S["AlertaTela"];
export type Resumo = S["Resumo"];
export type Projeto = S["Projeto"];
export type Gravidade = S["Gravidade"];
export type Papel = S["Papel"];
export type Origem = S["Origem"];
export type Pessoa = S["Pessoa"];
export type Arquivo = S["Arquivo"];
export type SlackConexao = S["SlackConexao"];
export type ConfigPedido = S["ConfigPedido"];
export type AcaoDecisao = S["DecisaoPedido"]["acao"];
export type Relatorio = S["Relatorio"];
export type TarefaRelatorio = S["TarefaTela"];
export type EtapaRelatorio = S["EtapaTela"];

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* corpo sem JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const id = (alertaId: string) => encodeURIComponent(alertaId);

export const api = {
  projeto: () => request<Projeto>("/projeto"),
  alertas: () => request<Alerta[]>("/alertas"),
  resumo: () => request<Resumo>("/alertas/resumo"),
  decidir: (alertaId: string, acao: AcaoDecisao, quem: string) =>
    request<Alerta>(`/alertas/${id(alertaId)}/decisao`, {
      method: "POST",
      body: JSON.stringify({ acao, quem }),
    }),
  desfazer: (alertaId: string, quem: string) =>
    request<Alerta>(`/alertas/${id(alertaId)}/decisao?quem=${encodeURIComponent(quem)}`, {
      method: "DELETE",
    }),
  iniciarRelatorio: (dias: number) =>
    request<TarefaRelatorio>("/relatorios/tarefas", { method: "POST", body: JSON.stringify({ dias }) }),
  tarefaRelatorio: (id: string) => request<TarefaRelatorio>(`/relatorios/tarefas/${encodeURIComponent(id)}`),
  publicarRelatorio: (relatorioId: number, quem: string) =>
    request<Relatorio>(`/relatorios/${relatorioId}/publicar`, {
      method: "POST",
      body: JSON.stringify({ quem }),
    }),
  salvarConfig: (pedido: ConfigPedido) =>
    request<Projeto>("/projeto/config", { method: "PUT", body: JSON.stringify(pedido) }),
  slack: () => request<SlackConexao>("/projeto/slack"),
  arquivos: () => request<Arquivo[]>("/projeto/arquivos"),
  enviarArquivo: (arquivo: File) =>
    request<Arquivo>(`/projeto/arquivos?nome=${encodeURIComponent(arquivo.name)}`, {
      method: "POST",
      body: arquivo,
      headers: { "content-type": "application/pdf" },
    }),
  removerArquivo: (arquivoId: string) =>
    request<void>(`/projeto/arquivos/${encodeURIComponent(arquivoId)}`, { method: "DELETE" }),
};

/** Ainda espera decisão (o alerta postado ou o que ficou no resumo). */
export const aberto = (a: Alerta) => a.status === "pendente" || a.status === "em_resumo";
