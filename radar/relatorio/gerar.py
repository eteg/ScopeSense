"""Gera o relatório do Radar: coleta o período, monta o prompt e chama o modelo.

O system prompt é o de `prompt_sistema.md` (Radar de Desvios), com as variáveis
`{{...}}` preenchidas. Ele foi escrito para um agente com ferramentas; aqui a
aplicação coleta tudo antes e entrega no texto do usuário, então o modelo não
precisa (nem pode) buscar nada.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from radar import config
from radar.core.errors import FalhaNaFonte, FonteNaoConfigurada, RadarError
from radar.core.models import Consulta, Origem, Papel, Registro
from radar.llm import _get_client

FUSO = ZoneInfo("America/Sao_Paulo")
PROMPT = Path(__file__).with_name("prompt_sistema.md")
SEPARADOR = "<<<RESPOSTA>>>"
MAX_TEXTO_REGISTRO = 2000
MAX_TEXTO_CONTRATO = 120_000
MAX_TOKENS = 16000  # o modelo pensa antes de escrever: precisa de folga
ESFORCO = "medium"  # resumo de relatório, não problema difícil; pensa menos e responde mais rápido

ROTULO_PAPEL = {
    Papel.gestor: "Gestor do projeto",
    Papel.comercial: "Comercial",
    Papel.administrativo_contratos: "Administrativo de contratos",
}


@dataclass
class Pessoa:
    nome: str
    papel: Papel
    slack_id: str | None


@dataclass
class Coleta:
    slack: list[Registro] = field(default_factory=list)
    emails: list[Registro] = field(default_factory=list)
    arquivos: list[tuple[str, str, str]] = field(default_factory=list)  # nome, tipo, texto
    anexos_gmail: int = 0
    avisos: list[str] = field(default_factory=list)

    def contagem(self) -> dict[str, int]:
        threads = {r.metadados.get("thread_ts") for r in self.slack if r.metadados.get("thread_ts")}
        return {
            "mensagens_slack": len(self.slack),
            "threads_slack": len(threads),
            "emails": len(self.emails),
            "arquivos": len(self.arquivos) - self.anexos_gmail,
            "anexos_gmail": self.anexos_gmail,
        }


# --- coleta ------------------------------------------------------------------------------


def coletar(registry, desde: datetime, ate: datetime, arquivos) -> Coleta:
    """Lê Slack (canais do projeto, com threads) e Gmail (só e-mails do projeto)."""
    coleta = Coleta(arquivos=arquivos)
    consulta = Consulta(desde=desde, ate=ate, limite=1000)
    for origem, destino, nome in (
        (Origem.slack, coleta.slack, "Slack"),
        (Origem.email, coleta.emails, "Gmail"),
    ):
        try:
            destino.extend(registry.get(origem).fetch(consulta))
        except RadarError as exc:  # uma fonte fora do ar não impede o relatório
            coleta.avisos.append(f"{nome} não foi lido: {exc}")
    return coleta


def anexos_do_gmail(registry) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Contrato e documentos em PDF anexados aos e-mails do projeto (Gmail API, leitura).

    O servidor MCP do Gmail não entrega conteúdo de anexo; por isso é a API REST.
    """
    from radar.projeto.store import texto_do_pdf, tipo_pelo_nome

    try:
        anexos = registry.get(Origem.email).anexos_pdf()
    except RadarError as exc:
        return [], [f"Anexos do Gmail não foram lidos: {exc}"]
    saida, avisos = [], []
    for a in anexos:
        try:
            texto = texto_do_pdf(dados=a["bytes"])
        except Exception as exc:  # noqa: BLE001 - um PDF ruim não derruba o relatório
            avisos.append(f"Não consegui ler {a['nome']}: {exc}")
            continue
        origem = f'anexo do e-mail "{a["assunto"]}", de {a["de"]}, {_quando(a["data"])}, {a["link"]}'
        saida.append((f"{a['nome']} ({origem})", tipo_pelo_nome(a["nome"]), texto))
    return saida, avisos


# --- prompt ------------------------------------------------------------------------------


def _quando(data: datetime) -> str:
    return data.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def _registro(r: Registro) -> str:
    meta = [r.origem.value, _quando(r.data), r.autor]
    if r.metadados.get("thread_ts") and r.metadados.get("thread_ts") != r.metadados.get("ts"):
        meta.append(f"resposta na thread {r.metadados['thread_ts']}")
    elif r.metadados.get("respostas"):
        meta.append(f"abre thread {r.metadados.get('ts')} com {r.metadados['respostas']} respostas")
    if r.link:
        meta.append(r.link)
    texto = r.texto.strip()
    if len(texto) > MAX_TEXTO_REGISTRO:
        texto = texto[:MAX_TEXTO_REGISTRO] + " […]"
    return f"- [{' · '.join(meta)}]\n  {texto.replace(chr(10), chr(10) + '  ')}"


def _pessoas_do_papel(pessoas: list[Pessoa], papel: Papel) -> str:
    do_papel = [p for p in pessoas if p.papel == papel]
    if not do_papel:
        return "(ninguém cadastrado neste papel)"
    return "; ".join(
        f"{p.nome} (<@{p.slack_id}>)" if p.slack_id else f"{p.nome} (não encontrei no Slack)"
        for p in do_papel
    )


def montar_prompt(
    *,
    projeto: str,
    cliente: str | None,
    canal_nome: str,
    canal_id: str,
    dominios_email: str,
    pessoas: list[Pessoa],
    desde: datetime,
    ate: datetime,
    coleta: Coleta,
) -> tuple[str, str]:
    """Devolve (system, user)."""
    valores = {
        "NOME_EMPRESA": "ETEG",
        "NOME_PROJETO": projeto,
        "NOME_CLIENTE": cliente or "(não informado)",
        "CANAL_SLACK": f"#{canal_nome}",
        "CANAL_SLACK_ID": canal_id,
        "PASTA_DRIVE_NOME": "Arquivos do projeto (Configurações + anexos dos e-mails do projeto)",
        "PASTA_DRIVE_ID": "arquivos-do-projeto",
        "DOMINIOS_EMAIL": dominios_email or "(não informado)",
        "DATA_INICIO": desde.astimezone(FUSO).strftime("%d/%m/%Y"),
        "DATA_FIM": ate.astimezone(FUSO).strftime("%d/%m/%Y"),
        "DATA_HOJE": datetime.now(FUSO).strftime("%d/%m/%Y"),
        "GESTOR_PROJETO": _pessoas_do_papel(pessoas, Papel.gestor),
        "ADM_CONTRATOS": _pessoas_do_papel(pessoas, Papel.administrativo_contratos),
        "COMERCIAL": _pessoas_do_papel(pessoas, Papel.comercial),
    }
    system = PROMPT.read_text(encoding="utf-8")
    for chave, valor in valores.items():
        system = system.replace(f"{{{{{chave}}}}}", valor)
    # O prompt cita o papel como <@ADM_CONTRATOS>: troca pelo ID real, se houver.
    adm = next(
        (p for p in pessoas if p.papel == Papel.administrativo_contratos and p.slack_id), None
    )
    system = system.replace(
        "<@ADM_CONTRATOS>", f"<@{adm.slack_id}>" if adm else "*Administrativo de contratos*"
    )

    contratos, total = [], 0
    for nome, tipo, texto in coleta.arquivos:
        trecho = texto[: max(0, MAX_TEXTO_CONTRATO - total)]
        total += len(trecho)
        contratos.append(f"### {nome} (tipo: {tipo})\n{trecho or '(sem texto extraível)'}")

    ids = "\n".join(
        f"- {ROTULO_PAPEL[p.papel]}: {p.nome} → "
        + (f"<@{p.slack_id}>" if p.slack_id else "não encontrei no Slack")
        for p in pessoas
    )
    user = f"""IMPORTANTE: neste ambiente você NÃO tem ferramentas. A aplicação já coletou tudo do período e entrega abaixo. "Drive" (a pasta do projeto) aqui são os arquivos enviados na tela de Configurações e os PDFs anexados aos e-mails do projeto (o contrato pode estar entre eles; cite o link do e-mail de origem). Use só estes dados; não invente links (use os que vierem nos registros).

Responda SOMENTE com o texto da mensagem do Slack (mrkdwn), sem comentários antes ou depois. Se o relatório passar de 3.500 caracteres, separe cada mensagem (a principal e cada resposta da thread) com uma linha contendo apenas {SEPARADOR}.

Pessoas cadastradas no setup e o ID do Slack para marcar (use EXATAMENTE estes IDs; não marque mais ninguém):
{ids or "(ninguém cadastrado)"}

{chr(10).join(f"Aviso da coleta: {a}" for a in coleta.avisos)}

## Combinado: arquivos do projeto ({len(coleta.arquivos)})
{chr(10).join(contratos) if contratos else "NENHUM ARQUIVO ENVIADO: não há contrato na pasta do projeto."}

## Execução: Slack #{canal_nome} ({len(coleta.slack)} mensagens, com threads)
{chr(10).join(_registro(r) for r in coleta.slack) or "(nenhuma mensagem no período)"}

## Execução: e-mails do projeto ({len(coleta.emails)})
{chr(10).join(_registro(r) for r in coleta.emails) or "(nenhum e-mail no período)"}
"""
    return system, user


# --- modelo e saída ----------------------------------------------------------------------


def chamar_modelo(system: str, user: str) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise FonteNaoConfigurada(
            "Falta ANTHROPIC_API_KEY no .env: o relatório é escrito pelo modelo. "
            "Coloque a chave e reinicie a API."
        )
    import anthropic

    try:
        resposta = _get_client().messages.create(
            model=config.MODELO_PRINCIPAL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": ESFORCO},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIStatusError as exc:
        detalhe = (exc.body or {}).get("error", {}).get("message") if isinstance(exc.body, dict) else None
        if "workspace" in str(detalhe or exc).lower():
            raise FalhaNaFonte(
                "A chave da Anthropic não está ligada a um workspace: coloque "
                "ANTHROPIC_WORKSPACE_ID no .env (ou use uma chave de workspace) e reinicie a API."
            ) from exc
        raise FalhaNaFonte(f"O modelo recusou o pedido ({exc.status_code}): {detalhe or exc}") from exc
    except anthropic.APIError as exc:
        raise FalhaNaFonte(f"Falha ao falar com o modelo: {exc}") from exc
    if resposta.stop_reason == "refusal":
        raise FalhaNaFonte("O modelo recusou escrever o relatório. Tente outro período.")
    texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text").strip()
    if not texto:
        raise FalhaNaFonte(
            f"O modelo não devolveu texto (parou por {resposta.stop_reason}). Tente de novo."
        )
    return texto


_MENCAO = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")
_AVISO_GERAL = re.compile(r"<!(channel|here|everyone)>")


def limpar_saida(texto: str, pessoas: list[Pessoa]) -> str:
    """Só marca quem está no setup. Tira @channel/@here (o relatório não deve avisar todos)."""
    permitidos = {p.slack_id for p in pessoas if p.slack_id}
    texto = _MENCAO.sub(lambda m: m.group(0) if m.group(1) in permitidos else "@pessoa", texto)
    return _AVISO_GERAL.sub(lambda m: f"@{m.group(1)}", texto).strip()


def separar(texto: str) -> list[str]:
    return [parte.strip() for parte in texto.split(SEPARADOR) if parte.strip()]
