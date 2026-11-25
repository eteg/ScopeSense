import type { Achado, Gravidade, Origem, Papel, Status } from "./api/client";

// Rótulos do design do MVP: Crítico, Médio e Baixo.
export const GRAVIDADE: Record<Gravidade, string> = {
  critico: "Crítico",
  atencao: "Médio",
  observacao: "Baixo",
};

export const PAPEL: Record<Papel, string> = {
  gestor: "Gestor do projeto",
  comercial: "Comercial",
  adm_contratos: "Administrativo de contratos",
};

export const ORIGEM: Record<Origem, string> = {
  slack: "Slack",
  email: "E-mail",
  agenda: "Agenda",
  reuniao: "Reunião",
  documento: "Documento",
};

export const STATUS_DECIDIDO: Record<Exclude<Status, "pendente">, string> = {
  aprovado: "Aprovado para envio no Slack",
  nao_e_desvio: "Não é desvio · vira caso de teste",
  descartado: "Descartado",
};

const hora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
const diaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" });

function mesmoDia(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

/** "hoje 14:32", "ontem 18:00" ou "23/11 15:00". */
export function quando(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  const hoje = new Date();
  const ontem = new Date(hoje);
  ontem.setDate(hoje.getDate() - 1);
  const dia = mesmoDia(d, hoje) ? "hoje" : mesmoDia(d, ontem) ? "ontem" : diaMes.format(d);
  return `${dia} ${hora.format(d)}`;
}

/** "25 NOV" */
export function diaCurto(iso: string): string {
  const d = new Date(iso);
  const mes = d.toLocaleDateString("pt-BR", { month: "short" }).replace(".", "");
  return `${d.getDate()} ${mes}`.toUpperCase();
}

export function iniciais(nome?: string | null): string {
  if (!nome?.trim()) return "?";
  const partes = nome.trim().split(/\s+/);
  return ((partes[0][0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

export function pessoaDoAchado(achado: Achado, pessoas: Record<string, string | null | undefined>) {
  const papel = achado.papeis[0];
  return { papel: PAPEL[papel], nome: pessoas[papel] ?? null };
}

const reais = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

/** 19200 -> "R$ 19,2 mil" */
export function custo(valor: number): string {
  if (valor >= 1_000_000) return `R$ ${reais.format(valor / 1_000_000)} mi`;
  if (valor >= 1000) return `R$ ${reais.format(valor / 1000)} mil`;
  return `R$ ${reais.format(valor)}`;
}
