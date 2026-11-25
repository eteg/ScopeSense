"""Lógica pura da tela do Streamlit (sem `import streamlit`), para testar sem navegador.

`app.py` só desenha; aqui ficam montar o registro simulado, interpretar o resultado do grafo,
traduzir erros, formatar rótulos e contar o resumo do histórico.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from radar.core.models import Decisao, Origem, Registro
from radar.fontes.arquivos import gerar_id
from radar.ui import tema, textos, textos_app

FUSO = ZoneInfo("America/Sao_Paulo")

# Tipo do modelo -> chave usada em `textos.TITULO_DESVIO` e `tema.EMOJI_DESVIO`.
_CHAVE_DO_TIPO = {
    "escopo_extra": "escopo",
    "prazo_sla": "prazo",
    "terceiro_sem_documento": "documento",
    "promessa_fora_do_contrato": "promessa",
}

# (valor de `Decisao.acao`, rótulo do botão)
BOTOES_DECISAO = (
    ("aprovar", tema.ROTULO_APROVAR),
    ("descartar", tema.ROTULO_DESCARTAR),
    ("nao_e_desvio", tema.ROTULO_NAO_E_DESVIO),
)

STATUS_FILTRO = tuple(textos_app.ROTULO_STATUS_POR_VALOR)
PAPEL_FILTRO = tuple(textos_app.ROTULO_PAPEL_POR_VALOR)

MAX_ERROS_SEGUIDOS = 5  # o histórico para se o modelo está fora do ar (evita 40 erros iguais)


def _valor(x: Any) -> str:
    return str(getattr(x, "value", x))


# --- rótulos -----------------------------------------------------------------------------


def titulo_do_tipo(tipo: Any) -> str:
    chave = _CHAVE_DO_TIPO.get(_valor(tipo))
    return textos.TITULO_DESVIO.get(chave, _valor(tipo)) if chave else _valor(tipo)


def emoji_do_tipo(tipo: Any) -> str:
    chave = _CHAVE_DO_TIPO.get(_valor(tipo))
    return tema.EMOJI_DESVIO.get(chave, "") if chave else ""


def rotulo_status(status: str) -> str:
    return textos_app.ROTULO_STATUS_POR_VALOR.get(status, status)


def rotulo_papel(papel: Any) -> str:
    if papel is None:
        return textos_app.SEM_RESPONSAVEL
    return textos_app.ROTULO_PAPEL_POR_VALOR.get(_valor(papel), _valor(papel))


def rotulo_origem(origem: Any) -> str:
    return textos_app.ROTULO_ORIGEM_POR_VALOR.get(_valor(origem), _valor(origem))


def formatar_data(data: datetime | str | None) -> str:
    """dd/mm/aaaa HH:MM no fuso America/Sao_Paulo (data sem fuso é tratada como já estando nele)."""
    if data is None:
        return ""
    if isinstance(data, str):
        data = datetime.fromisoformat(data)
    if data.tzinfo is None:
        data = data.replace(tzinfo=FUSO)
    return data.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def formatar_confianca(confianca: float) -> str:
    return f"{confianca:.0%}"


def como_citacao(texto: str) -> str:
    """Markdown de citação que sobrevive a quebras de linha."""
    return "> " + texto.replace("\n", "\n> ")


# --- projeto (autores e canais) ----------------------------------------------------------


def _ler_projeto(caminho: Path) -> dict:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def autores_do_projeto(caminho: Path) -> list[str]:
    """Nomes de `data/projeto_alfa.json` (equipe e pessoas sintéticas), sem repetir."""
    projeto = _ler_projeto(caminho)
    nomes = [p.get("nome") for p in projeto.get("papeis", {}).values()]
    nomes += [p.get("nome") for p in projeto.get("pessoas_sinteticas", {}).values()]
    unicos = list(dict.fromkeys(n for n in nomes if n))
    return unicos or list(textos_app.AUTORES_PADRAO)


def canais_do_projeto(caminho: Path) -> list[str]:
    canais = list(_ler_projeto(caminho).get("canais", {}))
    return canais or list(textos_app.CANAIS_PADRAO)


# --- registro e decisão ------------------------------------------------------------------


def criar_registro_simulado(
    texto: str, autor: str, canal: str, agora: datetime | None = None
) -> Registro:
    """Registro de origem Slack, igual ao que o bot criaria. O id vem de `gerar_id`."""
    agora = agora or datetime.now(FUSO)
    texto = texto.strip()
    return Registro(
        id=gerar_id(Origem.slack.value, texto, agora),
        origem=Origem.slack,
        data=agora,
        autor=autor,
        texto=texto,
        metadados={"canal": canal, "simulado": True},
    )


def nova_decisao(
    registro_id: str, acao: str, quem: str, quando: datetime | None = None
) -> Decisao:
    return Decisao(alerta_id=registro_id, acao=acao, quem=quem, quando=quando or datetime.now(FUSO))


def rotulo_do_botao(acao: str) -> str:
    return dict(BOTOES_DECISAO).get(acao, acao)


# --- resultado do grafo ------------------------------------------------------------------


def classificar_resultado(resultado: dict | None) -> str:
    """'alerta' (postou, aguarda decisão), 'resumo' (confiança média) ou 'sem_desvio'."""
    if not resultado:
        return "sem_desvio"
    alerta = resultado.get("alerta")
    if alerta is None or _valor(alerta.tipo) == "nenhum":
        return "sem_desvio"
    acao = resultado.get("acao")
    if acao == "postar":
        return "alerta"
    if acao == "resumo":
        return "resumo"
    return "sem_desvio"


def mensagem_de_erro(exc: BaseException) -> str:
    """Mensagem em português para erros do modelo; nunca expõe o traceback na tela."""
    texto = f"{type(exc).__name__} {exc}".lower()
    if "api_key" in texto or "authentication" in texto or "x-api-key" in texto:
        return textos_app.ERRO_SEM_CHAVE
    return textos_app.ERRO_GENERICO.format(tipo=type(exc).__name__, detalhe=str(exc)[:300])


def pode_decidir(status: str, registro_id: str, locais: Any) -> bool:
    """Só dá para retomar o grafo no processo que o criou (checkpointer em memória)."""
    return status == "pendente" and registro_id in locais


# --- histórico ---------------------------------------------------------------------------


@dataclass
class ResumoHistorico:
    registros: int = 0
    alertas: int = 0
    resumos: int = 0
    ignorados: int = 0
    erros: list[str] = field(default_factory=list)
    interrompido: bool = False
    _seguidos: int = 0

    def contar(self, resultado: dict) -> None:
        self._seguidos = 0
        tipo = classificar_resultado(resultado)
        if tipo == "alerta":
            self.alertas += 1
        elif tipo == "resumo":
            self.resumos += 1

    def contar_erro(self, registro_id: str, exc: BaseException) -> bool:
        """Anota o erro. Devolve True se é hora de parar (erros demais seguidos)."""
        self._seguidos += 1
        self.erros.append(f"{registro_id}: {mensagem_de_erro(exc)}")
        if self._seguidos >= MAX_ERROS_SEGUIDOS:
            self.interrompido = True
        return self.interrompido

    def texto(self) -> str:
        return textos_app.HISTORICO_RESUMO.format(
            registros=self.registros,
            alertas=self.alertas,
            resumos=self.resumos,
            ignorados=self.ignorados,
            erros=len(self.erros),
        )
