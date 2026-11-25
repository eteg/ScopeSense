import { useEffect, useRef, useState } from "react";

import { NomeDialog } from "./components/NomeDialog";
import { TopBar } from "./components/TopBar";
import { Configuracoes } from "./pages/Configuracoes";
import { Conexoes } from "./pages/Conexoes";
import { Fila } from "./pages/Fila";

/** Pede o nome de quem decide e chama `depois` com ele. */
export type PedirNome = (depois?: (nome: string) => void) => void;

type Rota = "fila" | "configuracoes" | "conexoes";

function rotaAtual(): Rota {
  const h = window.location.hash;
  if (h.startsWith("#/configuracoes")) return "configuracoes";
  if (h.startsWith("#/conexoes")) return "conexoes";
  return "fila";
}

function useRota(): Rota {
  const [rota, setRota] = useState<Rota>(rotaAtual);
  useEffect(() => {
    const mudar = () => {
      setRota(rotaAtual());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", mudar);
    return () => window.removeEventListener("hashchange", mudar);
  }, []);
  return rota;
}

// Nome de quem decide: conveniência por navegador. Sem login na POC.
function useNome(): [string, (v: string) => void] {
  const [nome, setNome] = useState(() => {
    try {
      return localStorage.getItem("radar:decisor") ?? "";
    } catch {
      return "";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("radar:decisor", nome);
    } catch {
      /* armazenamento indisponível */
    }
  }, [nome]);
  return [nome, setNome];
}

export function App() {
  const rota = useRota();
  const [nome, setNome] = useNome();
  const [dialogo, setDialogo] = useState(false);
  const depois = useRef<((nome: string) => void) | null>(null);

  const pedirNome: PedirNome = (cb) => {
    depois.current = cb ?? null;
    setDialogo(true);
  };

  return (
    <div className="app">
      <TopBar nome={nome} onAvatar={() => pedirNome()} conexoes={rota === "conexoes"} />
      {rota === "configuracoes" ? (
        <Configuracoes />
      ) : rota === "conexoes" ? (
        <Conexoes />
      ) : (
        <Fila nome={nome} pedirNome={pedirNome} />
      )}
      <NomeDialog
        aberto={dialogo}
        nomeAtual={nome}
        onFechar={() => {
          setDialogo(false);
          depois.current = null;
        }}
        onSalvar={(n) => {
          setNome(n);
          setDialogo(false);
          depois.current?.(n);
          depois.current = null;
        }}
      />
    </div>
  );
}
