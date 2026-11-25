import type { Alerta, Papel } from "./api/client";
import { GRAVIDADE, ORIGEM, PAPEL, STATUS } from "./labels";

const campo = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;

/** Baixa os alertas visíveis como CSV (separador ";" abre direto no Excel em pt-BR). */
export function baixarCsv(alertas: Alerta[], pessoas: Partial<Record<Papel, string | null>>) {
  const linhas = [
    ["Gravidade", "Título", "Cláusula", "Contrato", "Evidência", "Origem", "Autor", "Data",
     "Responsável", "Papel", "Confiança", "Justificativa", "Status"],
    ...alertas.map((a) => [
      GRAVIDADE[a.gravidade],
      a.titulo,
      a.clausula,
      a.trecho_contrato,
      a.trecho_evidencia,
      a.evidencia ? ORIGEM[a.evidencia.origem] : "",
      a.evidencia?.autor,
      a.evidencia?.data,
      a.responsavel ? pessoas[a.responsavel] : "",
      a.responsavel ? PAPEL[a.responsavel] : "",
      a.confianca,
      a.justificativa,
      STATUS[a.status] ?? a.status,
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
