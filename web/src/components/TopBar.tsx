import etegLogo from "../assets/eteg-logo.png";
import { iniciais } from "../labels";

export function TopBar({
  nome,
  onAvatar,
  conexoes = false,
}: {
  nome: string;
  onAvatar: () => void;
  conexoes?: boolean;
}) {
  return (
    <div className="barra">
      <div className="container barra-interna">
        <a href="#/" className="marca" aria-label="Radar de Desvios: voltar para a fila">
          <img src={etegLogo} alt="ETEG Technology" className="logo" />
          <span className="divisor" />
          <span className="produto">Radar de Desvios</span>
        </a>
        <a
          href="#/conexoes"
          className={conexoes ? "nav-link ativo" : "nav-link"}
          aria-current={conexoes ? "page" : undefined}
        >
          Conexões
        </a>
        <button
          type="button"
          className="avatar avatar-36 avatar-botao"
          aria-label={nome ? `Decidindo como ${nome}. Trocar nome` : "Informar seu nome"}
          title={nome || "Informar seu nome"}
          onClick={onAvatar}
        >
          {iniciais(nome)}
        </button>
      </div>
    </div>
  );
}
