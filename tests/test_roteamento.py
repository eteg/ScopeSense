"""Roteamento em código (R-05): tipo define o papel, confiança define a ação. Sem modelo."""

import pytest

from radar.core.models import Acao, Alerta, Papel, SaidaClassificacao, TipoDesvio
from radar.roteamento import PAPEL_POR_TIPO, decidir_acao, rotear_alerta


def _alerta(tipo: TipoDesvio, confianca: float = 0.9) -> Alerta:
    return Alerta(
        tipo=tipo,
        confianca=confianca,
        clausula="2.2",
        trecho_contrato="Treinamento fora do escopo",
        trecho_evidencia="a gente faz o treinamento",
        justificativa="A conversa contraria a cláusula.",
        registro_id="reg-1",
    )


@pytest.mark.parametrize(
    ("tipo", "papel"),
    [
        (TipoDesvio.escopo_extra, Papel.gestor),
        (TipoDesvio.prazo_sla, Papel.comercial),
        (TipoDesvio.terceiro_sem_documento, Papel.administrativo_contratos),
        (TipoDesvio.promessa_fora_do_contrato, Papel.administrativo_contratos),
    ],
)
def test_tipo_cai_no_papel_certo(tipo, papel):
    roteado, acao = rotear_alerta(_alerta(tipo))
    assert roteado.responsavel is papel
    assert acao is Acao.postar


def test_nenhum_descarta_e_nao_ganha_papel():
    assert TipoDesvio.nenhum not in PAPEL_POR_TIPO
    roteado, acao = rotear_alerta(_alerta(TipoDesvio.nenhum, 0.99))
    assert acao is Acao.descartar
    assert roteado.responsavel is None


@pytest.mark.parametrize(
    ("confianca", "esperado"),
    [
        (1.0, Acao.postar),
        (0.8, Acao.postar),
        (0.79, Acao.resumo),
        (0.6, Acao.resumo),
        (0.5, Acao.resumo),
        (0.49, Acao.descartar),
        (0.3, Acao.descartar),
        (0.0, Acao.descartar),
    ],
)
def test_bordas_de_confianca(confianca, esperado):
    alerta = _alerta(TipoDesvio.escopo_extra, confianca)
    assert decidir_acao(alerta) is esperado
    assert rotear_alerta(alerta)[1] is esperado


def test_rotear_nao_altera_o_original():
    original = _alerta(TipoDesvio.prazo_sla)
    roteado, _ = rotear_alerta(original)
    assert original.responsavel is None
    assert roteado is not original
    assert roteado.responsavel is Papel.comercial
    assert roteado.model_dump(exclude={"responsavel"}) == original.model_dump(
        exclude={"responsavel"}
    )


def test_modelo_nunca_preenche_responsavel():
    assert "responsavel" not in SaidaClassificacao.model_fields
    assert "responsavel" in Alerta.model_fields
