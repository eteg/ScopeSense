"""Achados SINTÉTICOS para a demo e para desenvolver o frontend.

O conteúdo segue o design do MVP (canvas "Radar de Desvios · Interfaces",
tela "Fila de alertas"): o Projeto Alfa com 5 alertas, mais um problema de
projeto (bloqueio). Empresa, cliente, pessoas e links são fictícios.

Uso:
    python -m radar.achados.demo            # acrescenta os achados de exemplo
    python -m radar.achados.demo --limpar   # apaga o banco antes
"""

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from radar.achados.config import AchadosSettings
from radar.achados.models import AchadoNovo, Analise, Categoria, Citacao, Gravidade, Papel
from radar.achados.store import AchadoStore
from radar.core.models import Origem
from radar.projeto.models import CanalSlack, Pessoa, ProjetoConfig
from radar.projeto.store import ProjetoStore

TZ = ZoneInfo("America/Sao_Paulo")
CONTRATO = "Contrato do Projeto Alfa"
CANAL = "#alfa-projeto"


def _hoje(hora: int, minuto: int = 0, dias_atras: int = 0) -> datetime:
    base = datetime.now(TZ).replace(hour=hora, minute=minuto, second=0, microsecond=0)
    return base - timedelta(days=dias_atras)


def _contrato(clausula: str, trecho: str) -> Citacao:
    return Citacao(
        origem=Origem.documento,
        trecho=trecho,
        referencia=clausula,
        link="https://example.com/drive/contrato-alfa",
    )


def _slack(autor: str, quando: datetime, trecho: str) -> Citacao:
    return Citacao(
        origem=Origem.slack,
        trecho=trecho,
        referencia=f"Slack {CANAL}",
        autor=autor,
        data=quando,
        link=f"https://example.com/slack/alfa-projeto/p{int(quando.timestamp())}",
    )


ACHADOS: list[AchadoNovo] = [
    AchadoNovo(
        categoria=Categoria.desvio,
        tipo="Escopo",
        gravidade=Gravidade.critico,
        titulo="Módulo de relatórios financeiros aceito sem aditivo",
        combinado=_contrato(
            "Cl. 3.1",
            "O escopo compreende exclusivamente os módulos Cadastro, Agenda e Portal.",
        ),
        execucao=[
            _slack(
                "Marina", _hoje(14, 31), "Consegue incluir um módulo de relatórios financeiros?"
            ),
            _slack("Paulo", _hoje(14, 32), "Claro, a gente faz."),
        ],
        por_que_importa=(
            "Trabalho fora do escopo sem aditivo vira horas não pagas e cria expectativa "
            "de que o módulo está incluído."
        ),
        o_que_fazer="Abrir change request com estimativa antes de começar o módulo.",
        papeis=[Papel.gestor, Papel.comercial],
        horas_estimadas=96,
    ),
    AchadoNovo(
        categoria=Categoria.desvio,
        tipo="Documentação de terceiros",
        gravidade=Gravidade.critico,
        titulo="João começa amanhã com ASO vencido",
        combinado=_contrato("Cl. 8.2", "O terceiro só poderá iniciar atividades com ASO válido."),
        execucao=[
            _slack("Fornecedor", _hoje(9, 10), "O João começa amanhã no cliente."),
            Citacao(
                origem=Origem.documento,
                trecho="Validade: 10/11/2026",
                referencia="ASO_Joao.pdf",
                link="https://example.com/drive/aso-joao",
            ),
        ],
        por_que_importa=(
            "Pela Súmula 331 do TST, a contratante responde pelo terceiro que não fiscalizou."
        ),
        o_que_fazer="Suspender o início do João até o fornecedor enviar o ASO renovado.",
        papeis=[Papel.adm_contratos],
    ),
    AchadoNovo(
        categoria=Categoria.desvio,
        tipo="Prazo",
        gravidade=Gravidade.atencao,
        titulo="Entrega do Portal remarcada para 19/12",
        combinado=_contrato("Cl. 5.1", "O módulo Portal será entregue até 05/12/2026."),
        execucao=[
            Citacao(
                origem=Origem.email,
                trecho="Vamos precisar mover a entrega do Portal para 19/12.",
                referencia="E-mail",
                autor="Rafael",
                data=_hoje(11, 5),
                link="https://example.com/mail/portal",
            )
        ],
        por_que_importa="O atraso passa do prazo da cláusula 5.1 e pode gerar multa por SLA.",
        o_que_fazer="Negociar a nova data por escrito com o cliente e registrar em aditivo.",
        papeis=[Papel.comercial],
    ),
    AchadoNovo(
        categoria=Categoria.desvio,
        tipo="Promessa não contratada",
        gravidade=Gravidade.atencao,
        titulo="Treinamento prometido sem custo",
        combinado=_contrato("Nenhuma cláusula", "O contrato não prevê treinamento."),
        execucao=[
            Citacao(
                origem=Origem.reuniao,
                trecho="Pode deixar, a gente inclui o treinamento da equipe sem custo.",
                referencia="Reunião 23/11, 32:10",
                data=_hoje(15, 0, dias_atras=2),
                link="https://example.com/drive/reuniao-2311",
            )
        ],
        por_que_importa="A promessa vira obrigação informal sem receita.",
        o_que_fazer="Formalizar o treinamento como item pago ou alinhar que não está incluído.",
        papeis=[Papel.adm_contratos],
    ),
    AchadoNovo(
        categoria=Categoria.desvio,
        tipo="Escopo",
        gravidade=Gravidade.observacao,
        titulo="Troca do texto da tela de login",
        combinado=_contrato(
            "Cl. 3.1", "Ajustes de texto e layout estão incluídos no módulo Portal."
        ),
        execucao=[_slack("Marina", _hoje(16, 2), "Dá para trocar “Entrar” por “Acessar portal”?")],
        por_que_importa="Ajuste pequeno, já coberto pelo contrato.",
        o_que_fazer="Nada além de acompanhar.",
        papeis=[Papel.gestor],
    ),
    AchadoNovo(
        categoria=Categoria.problema,
        tipo="Bloqueio",
        gravidade=Gravidade.atencao,
        titulo="Acesso à homologação pendente há 6 dias úteis",
        execucao=[
            _slack(
                "Rafael", _hoje(10, 0, dias_atras=8), "alguém conseguiu o acesso à VPN do cliente?"
            ),
            _slack("Bia", _hoje(9, 40), "testes da fase 2 parados esperando acesso"),
        ],
        por_que_importa="3 cobranças sem resposta. Os testes da fase 2 estão parados.",
        o_que_fazer="Escalar o pedido de acesso ao ponto focal do cliente ainda hoje.",
        papeis=[Papel.gestor],
    ),
]

# IDs fictícios: na demo os canais não existem no Slack. Ao salvar a tela de
# Configurações sem mexer neles, o Radar não consulta o Slack.
CONFIG = ProjetoConfig(
    canais_slack=[
        CanalSlack(id="C0DEMO00001", nome="alfa-projeto"),
        CanalSlack(id="C0DEMO00002", nome="alfa-contratos"),
    ],
    pessoas=[
        Pessoa(nome="Paulo Lima", papel=Papel.gestor),
        Pessoa(nome="Carla Melo", papel=Papel.comercial),
        Pessoa(nome="Ana Souza", papel=Papel.adm_contratos),
    ],
)

RESUMO = (
    "A cliente pediu um módulo extra e a equipe aceitou no canal. A entrega do Portal foi "
    "remarcada por e-mail. O fornecedor confirmou o início do João amanhã, com ASO vencido."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limpar", action="store_true", help="apaga o banco antes")
    args = parser.parse_args()

    settings = AchadosSettings()
    if args.limpar:
        Path(settings.db_path).unlink(missing_ok=True)
        shutil.rmtree(settings.arquivos_dir, ignore_errors=True)
    store = AchadoStore(settings.db_path)
    for achado in ACHADOS:
        store.adicionar(settings.projeto, achado)
    store.registrar_analise(
        Analise(
            projeto=settings.projeto,
            executada_em=_hoje(14, 33),
            duracao_s=38,
            resumo=RESUMO,
            registros_lidos={"mensagens": 23, "e-mails": 4, "PDF": 1},
        )
    )
    ProjetoStore(settings.db_path, settings.arquivos_dir).salvar_config(settings.projeto, CONFIG)
    print(
        f"{len(ACHADOS)} achados sintéticos, 1 análise e a configuração do projeto "
        f"gravados em {settings.db_path}."
    )


if __name__ == "__main__":
    main()
