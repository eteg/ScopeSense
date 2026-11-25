"""Schema do alerta: um exemplo válido de cada modelo e as regras de quem preenche o quê."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from radar.core.models import (
    Acao,
    Alerta,
    Decisao,
    DocumentoExtraido,
    ListaObrigacoes,
    Obrigacao,
    Origem,
    Papel,
    Registro,
    SaidaClassificacao,
    TipoDesvio,
)

SAIDA = {
    "tipo": "escopo_extra",
    "confianca": 0.9,
    "clausula": "2.2",
    "trecho_contrato": "Treinamento fora do escopo",
    "trecho_evidencia": "a gente faz o treinamento",
    "justificativa": "A conversa promete o que a cláusula exclui.",
}


def test_saida_classificacao_valida_e_sem_responsavel():
    saida = SaidaClassificacao.model_validate(SAIDA)
    assert saida.tipo is TipoDesvio.escopo_extra
    assert "responsavel" not in SaidaClassificacao.model_fields
    assert not hasattr(saida, "responsavel")


def test_confianca_e_justificativa_tem_limites():
    with pytest.raises(ValidationError):
        SaidaClassificacao.model_validate({**SAIDA, "confianca": 1.5})
    with pytest.raises(ValidationError):
        SaidaClassificacao.model_validate({**SAIDA, "justificativa": "x" * 301})


def test_alerta_aceita_responsavel_so_do_codigo():
    alerta = Alerta(**SAIDA, registro_id="slack:1")
    assert alerta.responsavel is None
    alerta = Alerta(**SAIDA, registro_id="slack:1", responsavel=Papel.gestor)
    assert alerta.responsavel == "gestor"


def test_enums_do_plano():
    assert {t.value for t in TipoDesvio} == {
        "escopo_extra", "prazo_sla", "terceiro_sem_documento",
        "promessa_fora_do_contrato", "nenhum",
    }  # fmt: skip
    assert {p.value for p in Papel} == {"gestor", "comercial", "administrativo_contratos"}
    assert {a.value for a in Acao} == {"postar", "resumo", "descartar"}


def test_obrigacao_e_lista():
    lista = ListaObrigacoes.model_validate(
        {
            "obrigacoes": [
                {"clausula": "4.1", "texto": "Entrega em 30 dias", "tipo": "prazo",
                 "prazo": "2026-12-31"},
                {"clausula": "6.2", "texto": "ASO do terceiro", "tipo": "terceiro",
                 "documento_exigido": "aso"},
            ]
        }
    )  # fmt: skip
    assert isinstance(lista.obrigacoes[0], Obrigacao)
    assert lista.obrigacoes[0].prazo == date(2026, 12, 31)
    assert lista.obrigacoes[1].documento_exigido == "aso"


def test_decisao():
    decisao = Decisao(
        alerta_id="slack:1", acao="aprovar", quem="ana", quando=datetime(2026, 11, 25, tzinfo=UTC)
    )
    assert decisao.acao == "aprovar"
    with pytest.raises(ValidationError):
        Decisao(alerta_id="x", acao="dm", quem="ana", quando=datetime(2026, 11, 25, tzinfo=UTC))


def test_documento_extraido_validade_iso():
    doc = DocumentoExtraido.model_validate(
        {"tipo": "aso", "pessoa": "Fulano", "validade": "2026-03-01", "arquivo": "aso.pdf"}
    )
    assert doc.validade == date(2026, 3, 1)
    assert doc.empresa is None


def test_registro_canal_e_thread_id_vem_dos_metadados():
    base = {
        "id": "slack:1",
        "origem": Origem.slack,
        "data": datetime(2026, 11, 25, tzinfo=UTC),
        "autor": "ana",
        "texto": "oi",
    }
    sem = Registro(**base)
    assert sem.canal is None and sem.thread_id is None

    com = Registro(**base, metadados={"canal": "projeto-x", "thread_id": "1700000000.000100"})
    assert com.canal == "projeto-x"
    assert com.thread_id == "1700000000.000100"
    assert "canal" not in Registro.model_fields  # propriedade, não campo
    with pytest.raises(AttributeError):
        com.canal = "outro"  # type: ignore[misc]