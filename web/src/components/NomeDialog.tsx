import { useEffect, useRef, useState } from "react";

type Props = {
  aberto: boolean;
  nomeAtual: string;
  onSalvar: (nome: string) => void;
  onFechar: () => void;
};

/** Pergunta quem está decidindo. Sem login na POC: o nome fica no navegador. */
export function NomeDialog({ aberto, nomeAtual, onSalvar, onFechar }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [nome, setNome] = useState(nomeAtual);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (aberto && !dlg.open) {
      setNome(nomeAtual);
      dlg.showModal();
    }
    if (!aberto && dlg.open) dlg.close();
  }, [aberto, nomeAtual]);

  return (
    <dialog ref={ref} className="dialogo" aria-labelledby="dlg-nome" onClose={onFechar}>
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault();
          if (nome.trim()) onSalvar(nome.trim());
        }}
      >
        <h2 id="dlg-nome">Quem está decidindo?</h2>
        <p>Seu nome fica registrado em cada alerta que você notificar ou descartar.</p>
        <label className="campo">
          <span>Seu nome</span>
          <input
            autoFocus
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            maxLength={120}
            placeholder="Ex.: Paulo Lima"
          />
        </label>
        <div className="dialogo-acoes">
          <button type="button" className="btn btn-texto" onClick={onFechar}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primario" disabled={!nome.trim()}>
            Continuar
          </button>
        </div>
      </form>
    </dialog>
  );
}
