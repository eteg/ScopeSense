// Cliente da API do Radar. Os tipos vêm do OpenAPI do FastAPI (npm run gen:api),
// então o frontend usa os mesmos modelos do backend.
import type { components } from "./schema";

type S = components["schemas"];
export type Achado = S["Achado"];
export type Analise = S["Analise"];
export type Projeto = S["Projeto"];
export type Citacao = S["Citacao"];
export type Decisao = S["Decisao"];
export type Status = S["Status"];
export type Categoria = S["Categoria"];
export type Gravidade = S["Gravidade"];
export type Papel = S["Papel"];
export type Origem = S["Origem"];
export type Pessoa = S["Pessoa"];
export type Arquivo = S["Arquivo"];
export type SlackConexao = S["SlackConexao"];
export type ConfigPedido = S["ConfigPedido"];

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

export const api = {
  projeto: () => request<Projeto>("/projeto"),
  achados: () => request<Achado[]>("/achados"),
  // 404 quando o Radar ainda não rodou: a tela esconde o resumo.
  ultimaAnalise: () =>
    request<Analise>("/analises/ultima").catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }),
  decidir: (id: number, decisao: Decisao, decidido_por: string) =>
    request<Achado>(`/achados/${id}/decisao`, {
      method: "POST",
      body: JSON.stringify({ decisao, decidido_por }),
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
  removerArquivo: (id: string) =>
    request<void>(`/projeto/arquivos/${encodeURIComponent(id)}`, { method: "DELETE" }),
  desfazer: (id: number, por: string) =>
    request<Achado>(`/achados/${id}/decisao?por=${encodeURIComponent(por)}`, {
      method: "DELETE",
    }),
};
