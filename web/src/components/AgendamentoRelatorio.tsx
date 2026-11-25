import { useEffect, useMemo, useState } from "react";

import { Check } from "../icons";

// DEMONSTRAÇÃO (só frontend): o agendamento fica no navegador e não dispara nada.
// Quando existir o disparo de verdade, troca o localStorage por uma rota da API.

type Frequencia = "diario" | "semanal";
type Agendamento = {
  ativo: boolean;
  frequencia: Frequencia;
  dias: number[]; // 0 = domingo … 6 = sábado
  hora: string; // "09:00"
  periodoDias: number;
};

const CHAVE = "radar:agendamento-relatorio";
const PADRAO: Agendamento = {
  ativo: true,
  frequencia: "semanal",
  dias: [1, 4], // segunda e quinta
  hora: "09:00",
  periodoDias: 7,
};
const DIAS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const DIAS_LONGOS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

function ler(): Agendamento {
  try {
    const salvo = localStorage.getItem(CHAVE);
    return salvo ? { ...PADRAO, ...JSON.parse(salvo) } : PADRAO;
  } catch {
    return PADRAO;
  }
}

function proximoDisparo(a: Agendamento, agora = new Date()): Date | null {
  if (!a.ativo) return null;
  const [h, m] = a.hora.split(":").map(Number);
  const dias = a.frequencia === "diario" ? [0, 1, 2, 3, 4, 5, 6] : a.dias;
  if (!dias.length) return null;
  for (let i = 0; i < 8; i++) {
    const d = new Date(agora);
    d.setDate(agora.getDate() + i);
    d.setHours(h, m, 0, 0);
    if (dias.includes(d.getDay()) && d > agora) return d;
  }
  return null;
}

export function AgendamentoRelatorio({ canal }: { canal: string }) {
  const [salvo, setSalvo] = useState<Agendamento>(ler);
  const [form, setForm] = useState<Agendamento>(salvo);
  const [confirmado, setConfirmado] = useState(false);

  const mudou = JSON.stringify(form) !== JSON.stringify(salvo);
  const proximo = useMemo(() => proximoDisparo(salvo), [salvo]);

  useEffect(() => {
    if (!confirmado) return;
    const t = setTimeout(() => setConfirmado(false), 3000);
    return () => clearTimeout(t);
  }, [confirmado]);

  function salvar() {
    try {
      localStorage.setItem(CHAVE, JSON.stringify(form));
    } catch {
      /* armazenamento indisponível: vale só nesta sessão */
    }
    setSalvo(form);
    setConfirmado(true);
  }

  const alternarDia = (d: number) =>
    setForm((f) => ({
      ...f,
      dias: f.dias.includes(d) ? f.dias.filter((x) => x !== d) : [...f.dias, d].sort(),
    }));

  const quando = proximo
    ? `${DIAS_LONGOS[proximo.getDay()]}, ${proximo.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
      })} às ${proximo.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`
    : null;

  return (
    <section aria-labelledby="p-agenda" className="painel">
      <div className="agenda-topo">
        <div>
          <h2 id="p-agenda">Disparo automático do relatório</h2>
          <p className="painel-texto">
            O Radar gera o relatório sozinho e publica em {canal}, marcando cada responsável.
          </p>
        </div>
        <label className="interruptor">
          <input
            type="checkbox"
            checked={form.ativo}
            onChange={(e) => setForm((f) => ({ ...f, ativo: e.target.checked }))}
          />
          <span aria-hidden="true" className="interruptor-trilho" />
          <span>{form.ativo ? "Ligado" : "Desligado"}</span>
        </label>
      </div>

      <fieldset className="agenda-campos" disabled={!form.ativo}>
        <div className="linha-campos">
          <label className="campo-contorno">
            <span>Frequência</span>
            <select
              value={form.frequencia}
              onChange={(e) => setForm((f) => ({ ...f, frequencia: e.target.value as Frequencia }))}
            >
              <option value="diario">Todo dia</option>
              <option value="semanal">Em dias da semana</option>
            </select>
          </label>
          <label className="campo-contorno">
            <span>Horário</span>
            <input
              type="time"
              value={form.hora}
              onChange={(e) => setForm((f) => ({ ...f, hora: e.target.value || "09:00" }))}
            />
          </label>
          <label className="campo-contorno">
            <span>Período analisado</span>
            <select
              value={form.periodoDias}
              onChange={(e) => setForm((f) => ({ ...f, periodoDias: Number(e.target.value) }))}
            >
              <option value={1}>Último dia</option>
              <option value={7}>Últimos 7 dias</option>
              <option value={14}>Últimos 14 dias</option>
            </select>
          </label>
        </div>

        {form.frequencia === "semanal" && (
          <div className="agenda-dias" role="group" aria-label="Dias da semana">
            {DIAS.map((rotulo, d) => (
              <button
                key={rotulo}
                type="button"
                className={form.dias.includes(d) ? "chip-dia ativo" : "chip-dia"}
                aria-pressed={form.dias.includes(d)}
                onClick={() => alternarDia(d)}
              >
                {rotulo}
              </button>
            ))}
          </div>
        )}
      </fieldset>

      <div className="agenda-rodape">
        <span className="agenda-proximo">
          {quando ? (
            <>
              Próximo disparo: <b>{quando}</b>
            </>
          ) : (
            "Nenhum disparo agendado."
          )}
        </span>
        {confirmado && (
          <span className="selo selo-ok" role="status">
            <Check />
            Agendamento salvo
          </span>
        )}
        <button type="button" className="btn btn-primario" disabled={!mudou} onClick={salvar}>
          Salvar agendamento
        </button>
      </div>
      <p className="agenda-aviso">Demonstração: o disparo automático ainda não está ligado ao servidor.</p>
    </section>
  );
}
