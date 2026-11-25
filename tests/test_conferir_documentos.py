"""R-07: conferência determinística dos documentos do terceiro (sem rede, sem modelo)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from radar.core.models import Alerta, DocumentoExtraido, Origem, Papel, Registro, TipoDesvio
from radar.documentos import carregar_documentos
from radar.nos.conferir_documentos import TRECHO_CLAUSULA_6_1, conferir, conferir_documentos
from radar.roteamento import rotear_alerta

CONTRATO = Path(__file__).resolve().parents[1] / "data" / "contrato_alfa.md"
ENTREGA = datetime(2027, 1, 26, tzinfo=UTC)


def _registro(texto: str, data: datetime = ENTREGA) -> Registro:
    return Registro(id="t:doc", origem=Origem.slack, data=data, autor="gestor", texto=texto)


def _alerta(tipo: TipoDesvio = TipoDesvio.terceiro_sem_documento) -> Alerta:
    return Alerta(
        tipo=tipo,
        confianca=0.7,
        clausula="6",
        trecho_contrato="cláusula do modelo",
        trecho_evidencia="evidência do modelo",
        justificativa="Justificativa do modelo.",
        registro_id="t:doc",
    )


def _aso(pessoa: str, validade: date | None) -> DocumentoExtraido:
    return DocumentoExtraido(
        tipo="aso", pessoa=pessoa, empresa="Nimbus Serviços", validade=validade, arquivo="x.pdf"
    )


@pytest.fixture(scope="module")
def reais() -> list[DocumentoExtraido]:
    return carregar_documentos()


def test_joao_com_pdfs_reais_gera_alerta_com_o_aso_vencido(reais):
    registro = _registro("o João da Nimbus começa amanhã no cliente")
    resultado = conferir(_alerta(), registro, reais)

    assert resultado is not None
    assert resultado.tipo is TipoDesvio.terceiro_sem_documento
    assert resultado.confianca == 1.0
    assert resultado.clausula == "6.1"
    assert "10/11/2026" in resultado.trecho_evidencia
    assert "João Teixeira" in resultado.trecho_evidencia
    assert "6.4" in resultado.justificativa and "FGTS" in resultado.justificativa
    assert "possível" in resultado.justificativa.lower()
    assert len(resultado.justificativa) <= 300
    assert resultado.responsavel is None
    assert resultado.registro_id == "t:doc"


def test_documentos_padrao_vem_de_carregar_documentos():
    resultado = conferir(_alerta(), _registro("o João da Nimbus começa amanhã"))
    assert resultado is not None
    assert "10/11/2026" in resultado.trecho_evidencia


def test_carla_com_aso_em_dia_nao_gera_alerta_mesmo_sem_fgts(reais):
    assert not any(d.tipo == "fgts" for d in reais)  # FGTS ausente, e mesmo assim sem alerta
    assert conferir(_alerta(), _registro("a Carla da Nimbus começa amanhã"), reais) is None


def test_trecho_contrato_e_literal_do_contrato_na_clausula_6_1(reais):
    resultado = conferir(_alerta(), _registro("o João começa amanhã"), reais)
    assert resultado is not None
    assert resultado.trecho_contrato == TRECHO_CLAUSULA_6_1
    contrato = CONTRATO.read_text(encoding="utf-8")
    assert resultado.trecho_contrato in contrato
    clausula_6_1 = contrato.split("### 6.1")[1].split("### 6.2")[0]
    assert resultado.trecho_contrato in clausula_6_1


def test_aso_ausente_gera_alerta():
    docs = [_aso("Carla Mota", date(2027, 8, 15))]
    resultado = conferir(_alerta(), _registro("o João começa amanhã"), docs)
    assert resultado is not None
    assert resultado.confianca == 1.0
    assert resultado.clausula == "6.1"
    assert "João Teixeira" in resultado.trecho_evidencia
    assert "Sem ASO" in resultado.trecho_evidencia


def test_aso_que_vence_na_data_de_inicio_e_valido():
    # registro de 26/01/2027 + amanhã = 27/01/2027; o ASO vence exatamente nesse dia
    docs = [_aso("João Teixeira", date(2027, 1, 27))]
    assert conferir(_alerta(), _registro("o João começa amanhã"), docs) is None
    # um dia antes já está vencido
    docs = [_aso("João Teixeira", date(2027, 1, 26))]
    assert conferir(_alerta(), _registro("o João começa amanhã"), docs) is not None


def test_sem_amanha_usa_a_data_do_registro():
    docs = [_aso("João Teixeira", date(2027, 1, 26))]
    # sem "amanhã", o início é 26/01/2027: o ASO ainda vale
    assert conferir(_alerta(), _registro("o João começa hoje no cliente"), docs) is None
    # com "amanhã", o início passa a 27/01/2027 e o ASO venceu
    assert conferir(_alerta(), _registro("o João começa amanhã no cliente"), docs) is not None


def test_amanha_sem_acento_e_nome_completo():
    docs = [_aso("João Teixeira", date(2027, 1, 26))]
    resultado = conferir(_alerta(), _registro("Joao Teixeira começa AMANHA, ok?"), docs)
    assert resultado is not None


def test_nome_nao_identificado_devolve_o_alerta_inalterado(reais):
    alerta = _alerta()
    assert conferir(alerta, _registro("alguém da Nimbus começa amanhã"), reais) is alerta


def test_outro_tipo_devolve_o_alerta_inalterado(reais):
    alerta = _alerta(TipoDesvio.escopo_extra)
    assert conferir(alerta, _registro("o João começa amanhã"), reais) is alerta


def test_comparacao_usa_date_e_nao_texto():
    # início 20/12/2026 (registro de 19/12 + amanhã); validade 05/01/2027.
    # Como texto, "05/01/2027" < "20/12/2026" (pareceria vencido); como date, ainda vale.
    assert "05/01/2027" < "20/12/2026"
    registro = _registro("o João começa amanhã", datetime(2026, 12, 19, tzinfo=UTC))
    assert conferir(_alerta(), registro, [_aso("João Teixeira", date(2027, 1, 5))]) is None
    # e o inverso: validade 30/11/2026 contra início 01/12/2026 (texto "30/..." > "01/...")
    registro = _registro("o João começa amanhã", datetime(2026, 11, 30, tzinfo=UTC))
    assert conferir(_alerta(), registro, [_aso("João Teixeira", date(2026, 11, 30))]) is not None


def test_pessoas_injetavel():
    docs = [_aso("Ana Lima", date(2020, 1, 1))]
    resultado = conferir(_alerta(), _registro("a Ana começa amanhã"), docs, pessoas=("Ana Lima",))
    assert resultado is not None
    assert "Ana Lima" in resultado.trecho_evidencia


def test_fgts_entregue_nao_aparece_na_justificativa():
    docs = [
        _aso("João Teixeira", date(2026, 11, 10)),
        DocumentoExtraido(tipo="fgts", empresa="Nimbus Serviços", arquivo="f.pdf"),
    ]
    resultado = conferir(_alerta(), _registro("o João começa amanhã"), docs)
    assert resultado is not None
    assert "FGTS" not in resultado.justificativa


def test_no_do_grafo_carla_vira_nenhum_e_o_roteamento_descarta(reais):
    estado = {"alerta": _alerta(), "registro": _registro("a Carla começa amanhã")}
    saida = conferir_documentos(estado)["alerta"]
    assert saida.tipo is TipoDesvio.nenhum
    _, acao = rotear_alerta(saida)
    assert acao.value == "descartar"


def test_no_do_grafo_joao_segue_para_o_roteamento_com_confianca_total():
    estado = {"alerta": _alerta(), "registro": _registro("o João começa amanhã")}
    saida = conferir_documentos(estado)["alerta"]
    roteado, acao = rotear_alerta(saida)
    assert roteado.responsavel is Papel.administrativo_contratos
    assert acao.value == "postar"
