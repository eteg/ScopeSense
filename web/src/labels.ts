import type { Alerta, Gravidade, Origem, Papel } from "./api/client";

// Rótulos do design do MVP: Crítico, Médio e Baixo.
export const GRAVIDADE: Record<Gravidade, string> = {
  critico: "Crítico",
  medio: "Médio",
  baixo: "Baixo",
};

// Mesmos rótulos do Streamlit e do Slack (radar/ui/textos_app.py).
export const PAPEL: Record<Papel, string> = {
  gestor: "Gestor do projeto",
  comercial: "Comercial",
  administrativo_contratos: "Administrativo de contratos",
};

export const ORIGEM: Record<Origem, string> = {
  slack: "Slack",
  email: "E-mail",
  agenda: "Agenda",
  reuniao: "Reunião",
  documento: "Documento",
};

export const STATUS: Record<string, string> = {
  pendente: "Pendente",
  em_resumo: "Em resumo",
  aprovado: "Aprovado",
  descartado: "Descartado",
  nao_e_desvio: "Não é desvio · vira caso de teste",
};

const hora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
const diaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" });

function mesmoDia(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

/** "hoje 14:32", "ontem 18:00" ou "23/11 15:00". */
export function quando(iso?: string | null): string | null {
  if (!iso) return null;
  // SQLite grava "AAAA-MM-DD HH:MM:SS" em UTC (sem fuso).
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso.replace(" ", "T")}Z`);
  if (Number.isNaN(d.getTime())) return null;
  const hoje = new Date();
  const ontem = new Date(hoje);
  ontem.setDate(hoje.getDate() - 1);
  const dia = mesmoDia(d, hoje) ? "hoje" : mesmoDia(d, ontem) ? "ontem" : diaMes.format(d);
  return `${dia} ${hora.format(d)}`;
}

export function iniciais(nome?: string | null): string {
  if (!nome?.trim()) return "?";
  const partes = nome.trim().split(/\s+/);
  return ((partes[0][0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

export function pessoaDoAlerta(alerta: Alerta, pessoas: Partial<Record<Papel, string | null>>) {
  const papel = alerta.responsavel;
  return {
    papel: papel ? PAPEL[papel] : "Sem papel definido",
    nome: papel ? (pessoas[papel] ?? null) : null,
  };
}

export const porcento = (x: number) => `${Math.round(x * 100)}%`;
