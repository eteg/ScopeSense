import type { Achado } from "./api/client";
import { GRAVIDADE, ORIGEM, PAPEL } from "./labels";

const campo = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;

/** Baixa os alertas visíveis como CSV (separador ";" abre direto no Excel em pt-BR). */
export function baixarCsv(achados: Achado[], pessoas: Record<string, string | null | undefined>) {
  const linhas = [
    ["Gravidade", "Tipo", "Título", "Cláusula", "Contrato", "Evidência", "Fonte", "Responsável", "Papel", "Status"],
    ...achados.map((a) => [
      GRAVIDADE[a.gravidade],
      a.tipo,
      a.titulo,
      a.combinado?.referencia,
      a.combinado?.trecho,
      a.execucao.map((c) => (c.autor ? `${c.autor}: ${c.trecho}` : c.trecho)).join(" | "),
      a.execucao.map((c) => c.referencia ?? ORIGEM[c.origem]).join(" | "),
      pessoas[a.papeis[0]],
      PAPEL[a.papeis[0]],
      a.status,
    ]),
  ];
  const texto = "﻿" + linhas.map((l) => l.map(campo).join(";")).join("\r\n");
  const url = URL.createObjectURL(new Blob([texto], { type: "text/csv;charset=utf-8" }));
  const link = Object.assign(document.createElement("a"), {
    href: url,
    download: `radar-alertas-${new Date().toISOString().slice(0, 10)}.csv`,
  });
  link.click();
  URL.revokeObjectURL(url);
}
