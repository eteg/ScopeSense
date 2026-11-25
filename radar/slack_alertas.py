"""Alerta no Slack (G-07): Block Kit com contrato e evidência lado a lado, e os botões (G-08).

É o ÚNICO módulo que escreve no Slack (token de bot `xoxb-`). O alerta é POSTADO NO GRUPO
(canal) do projeto, marcando o responsável com `<@ID>`; não há DM. Funções finas e sem regra de
negócio: todo texto, emoji e rótulo vem de `radar.ui` (o design da Lara entra lá).
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from radar import config, db
from radar.core.models import Alerta, Decisao, Papel, Registro
from radar.fontes.slack_export import FUSO
from radar.ui import tema, textos

LIMITE_TRECHO = 300  # limite de caracteres de cada citação (o Block Kit tem tetos próprios)
CAMINHO_PROJETO = Path(__file__).resolve().parents[1] / "data" / "projeto_alfa.json"
PREFIXO_PENDENTE = "U_PENDENTE"


def _cortar(texto: str, limite: int = LIMITE_TRECHO) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _escapar(texto: str) -> str:
    """Escapa os três caracteres especiais do mrkdwn do Slack."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _contexto(*textos_mrkdwn: str) -> dict:
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": t} for t in textos_mrkdwn],
    }


def _chave_tipo(alerta: Alerta) -> str | None:
    return tema.CHAVE_POR_TIPO.get(str(getattr(alerta.tipo, "value", alerta.tipo)))


def titulo_do_alerta(alerta: Alerta) -> str:
    """Título neutro do tipo do desvio (nunca cita quem escreveu)."""
    chave = _chave_tipo(alerta)
    return textos.TITULO_DESVIO.get(chave, textos.TITULO_DESVIO_GENERICO)


def _blocos_conteudo(alerta: Alerta, registro: Registro | None) -> list[dict]:
    """Header + citações + linha de contexto. `registro` pode faltar (reconstrução parcial)."""
    emoji = tema.EMOJI_DESVIO.get(_chave_tipo(alerta) or "", "")
    titulo = f"{emoji} {titulo_do_alerta(alerta)}".strip()
    esquerda = (
        f"*{textos.ROTULO_CLAUSULA.format(numero=_escapar(alerta.clausula))}*\n"
        f"{_escapar(_cortar(alerta.trecho_contrato))}"
    )
    if registro is not None:
        quando = registro.data.astimezone(FUSO).strftime(textos.FORMATO_DATA_ALERTA)
        rotulo = textos.ROTULO_EVIDENCIA_AUTOR.format(autor=_escapar(registro.autor), data=quando)
    else:
        rotulo = textos.ROTULO_EVIDENCIA
    direita = f"*{rotulo}*\n{_escapar(_cortar(alerta.trecho_evidencia))}"

    itens = [f"{textos.ROTULO_CONFIANCA}: {alerta.confianca:.0%}"]
    if registro is not None:
        origem = str(getattr(registro.origem, "value", registro.origem))
        itens.append(f"{textos.ROTULO_ORIGEM}: {textos.NOME_ORIGEM.get(origem, origem)}")
        if registro.link and registro.link.startswith("http"):
            itens.append(f"<{registro.link}|{textos.ROTULO_LINK_ORIGINAL}>")

    return [
        {"type": "header", "text": {"type": "plain_text", "text": titulo, "emoji": True}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": esquerda},
                {"type": "mrkdwn", "text": direita},
            ],
        },
        _contexto(*itens),
    ]


def _botao(texto: str, action_id: str, valor: str, estilo: str | None = None) -> dict:
    botao = {
        "type": "button",
        "text": {"type": "plain_text", "text": texto, "emoji": True},
        "action_id": action_id,
        "value": valor,
    }
    if estilo:
        botao["style"] = estilo
    return botao


def montar_blocos(alerta: Alerta, registro: Registro) -> list[dict]:
    """Block Kit do alerta: header neutro, contrato e evidência lado a lado, contexto, botões."""
    blocos = _blocos_conteudo(alerta, registro)
    blocos.append(
        {
            "type": "actions",
            "elements": [
                _botao(_rotulo_botao("aprovar"), "aprovar", alerta.registro_id, "primary"),
                _botao(_rotulo_botao("descartar"), "descartar", alerta.registro_id),
                _botao(_rotulo_botao("nao_e_desvio"), "nao_e_desvio", alerta.registro_id),
            ],
        }
    )
    return blocos


def _rotulo_botao(acao: str) -> str:
    return {
        "aprovar": tema.ROTULO_APROVAR,
        "descartar": tema.ROTULO_DESCARTAR,
        "nao_e_desvio": tema.ROTULO_NAO_E_DESVIO,
    }[acao]


def texto_fallback(alerta: Alerta, usuario_id: str | None = None) -> str:
    """Texto da notificação (celular, preview), com a menção quando houver."""
    texto = textos.TEXTO_FALLBACK_ALERTA.format(
        titulo=titulo_do_alerta(alerta), clausula=alerta.clausula
    )
    return f"<@{usuario_id}> · {texto}" if usuario_id else texto


def enviar_alerta(
    client: Any,
    alerta: Alerta,
    registro: Registro,
    canal: str,
    usuario_id: str | None = None,
) -> dict:
    """Posta o alerta no grupo do projeto e guarda canal/ts no banco (para o `chat_update`)."""
    blocos = montar_blocos(alerta, registro)
    if usuario_id:
        blocos.insert(
            0,
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{textos.ROTULO_PARA} <@{usuario_id}>"},
            },
        )
    resposta = client.chat_postMessage(
        channel=canal, blocks=blocos, text=texto_fallback(alerta, usuario_id)
    )
    ts = resposta["ts"]
    canal_postado = resposta.get("channel") or canal
    caminho = config.DATABASE_PATH  # lido na hora da chamada (os testes trocam o banco)
    db.init_db(caminho)
    db.atualizar_slack_msg(alerta.registro_id, canal_postado, ts, caminho=caminho)
    return {"canal": canal_postado, "ts": ts}


def usuario_do_papel(
    papel: Papel | str | None, caminho_projeto: str | Path | None = None
) -> str | None:
    """`slack_id` do papel em `data/projeto_alfa.json`; ID pendente ou vazio devolve None."""
    if papel is None:
        return None
    chave = str(getattr(papel, "value", papel))
    try:
        dados = json.loads(Path(caminho_projeto or CAMINHO_PROJETO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    slack_id = ((dados.get("papeis") or {}).get(chave) or {}).get("slack_id") or ""
    slack_id = str(slack_id).strip()
    if not slack_id or slack_id.startswith(PREFIXO_PENDENTE):
        return None
    return slack_id


def linha_decisao(decisao: Decisao) -> str:
    hora = decisao.quando.astimezone(FUSO).strftime(textos.FORMATO_HORA_DECISAO)
    return textos.LINHA_DECISAO[decisao.acao].format(quem=decisao.quem, hora=hora)


def atualizar_apos_decisao(
    client: Any,
    canal: str,
    ts: str,
    alerta: Alerta | None,
    decisao: Decisao,
    blocos_originais: Sequence[dict] | None = None,
) -> None:
    """Troca os botões por "Aprovado por X às HH:MM" (ou descartado / não é desvio).

    Mantém o resto da mensagem: usa `blocos_originais` (os da mensagem clicada) quando vierem;
    senão reconstrói o conteúdo a partir do alerta.
    """
    if blocos_originais:
        base = list(blocos_originais)
    elif alerta is not None:
        base = _blocos_conteudo(alerta, None)
    else:
        base = []
    blocos = [b for b in base if b.get("type") != "actions"]
    linha = linha_decisao(decisao)
    emoji = tema.EMOJI_DECISAO.get(decisao.acao, "")
    blocos.append(_contexto(f"{emoji} {_escapar(linha)}".strip()))
    texto = f"{titulo_do_alerta(alerta)} · {linha}" if alerta is not None else linha
    client.chat_update(channel=canal, ts=ts, blocks=blocos, text=texto)
