"""Radar de Desvios: tela Streamlit (fila de alertas, simular mensagem e histórico).

É o plano B da demo: roda o MESMO `grafo.processar` e `grafo.retomar` do fluxo real, com o
Slack desligado. Só desenha; as regras ficam em `radar/ui/app_logica.py`, os textos em
`radar/ui/textos_app.py` e a estética em `radar/ui/tema.py` e `radar/ui/estilo.css`.

`processar` e `retomar` usam o checkpointer em memória: só dá para decidir, aqui, os alertas
criados NESTE processo. Os que vieram de outro processo (o bot do Slack) ficam só para leitura.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # antes de importar `radar.config`: ele lê DATABASE_PATH e MODO_DEMO do ambiente

import streamlit as st  # noqa: E402

from radar import cache_llm, config, db, grafo, observabilidade  # noqa: E402
from radar.core.models import Acao, Consulta, Registro  # noqa: E402
from radar.fontes.arquivos import FileSource, contexto_de  # noqa: E402
from radar.ui import app_logica as logica  # noqa: E402
from radar.ui import textos, textos_app  # noqa: E402

RAIZ = Path(__file__).parent
PASTA_DADOS = RAIZ / "data"
ARQUIVO_PROJETO = PASTA_DADOS / "projeto_alfa.json"

SS_AVISO = "aviso"
SS_SIMULACAO = "simulacao"
SS_HISTORICO = "resumo_historico"

st.set_page_config(page_title=textos.TITULO_APP)

_css = RAIZ / "radar" / "ui" / "estilo.css"
if _css.exists():
    st.markdown(f"<style>{_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_resource
def iniciar(caminho_banco: str) -> dict[str, Registro]:
    """Uma vez por processo: cria o banco e liga o notificador do grafo.

    Devolve os alertas postados por este processo (registro_id -> registro). Só estes têm
    pausa de aprovação viva no grafo em memória, então só estes podem receber decisão aqui.
    """
    db.init_db(caminho_banco)
    observabilidade.ativar_langfuse()  # no-op (desligado) sem as chaves do Langfuse no .env
    cache_llm.ativar_cache_sqlite(caminho_banco)  # grava sempre; só lê com MODO_DEMO=1
    locais: dict[str, Registro] = {}

    def notificador(alerta, registro: Registro) -> None:
        locais[alerta.registro_id] = registro

    grafo.configurar(notificador)
    return locais


CAMINHO = str(config.DATABASE_PATH)
LOCAIS = iniciar(CAMINHO)


# --- decisão (callback dos botões: roda antes do script, o aviso aparece no topo) --------


def _decidir(registro_id: str, acao: str) -> None:
    try:
        decisao = logica.nova_decisao(registro_id, acao, textos_app.QUEM_DECIDE)
        resultado = grafo.retomar(registro_id, decisao)
    except Exception as exc:  # noqa: BLE001 - a tela nunca cai por causa do grafo
        detalhe = logica.mensagem_de_erro(exc)
        aviso = ("erro", textos_app.DECISAO_ERRO.format(detalhe=detalhe))
    else:
        if resultado is None:
            aviso = ("info", textos_app.DECISAO_JA_REGISTRADA)
        else:
            rotulo = logica.rotulo_do_botao(acao)
            aviso = ("sucesso", textos_app.DECISAO_REGISTRADA.format(rotulo=rotulo))
    st.session_state[SS_AVISO] = aviso


# --- apresentação ------------------------------------------------------------------------


def cartao_alerta(alerta, registro: Registro | None, contexto: str) -> None:
    """Um alerta: cláusula à esquerda, evidência à direita, status e (se couber) botões."""
    with st.container(border=True):
        emoji = logica.emoji_do_tipo(alerta.tipo)
        st.markdown(f"**{emoji} {logica.titulo_do_tipo(alerta.tipo)}**")
        st.caption(
            " · ".join(
                [
                    textos_app.ROTULO_CONFIANCA.format(
                        valor=logica.formatar_confianca(alerta.confianca)
                    ),
                    textos_app.ROTULO_RESPONSAVEL.format(
                        papel=logica.rotulo_papel(alerta.responsavel)
                    ),
                    textos_app.ROTULO_STATUS.format(status=logica.rotulo_status(alerta.status)),
                ]
            )
        )
        esquerda, direita = st.columns(2)
        with esquerda:
            clausula = textos_app.ROTULO_CLAUSULA.format(numero=alerta.clausula)
            st.markdown(f"**{textos.ROTULO_CONTRATO}** · {clausula}")
            st.markdown(logica.como_citacao(alerta.trecho_contrato))
        with direita:
            st.markdown(f"**{textos.ROTULO_EVIDENCIA}**")
            if registro is not None:
                st.caption(
                    " · ".join(
                        [
                            textos_app.ROTULO_ORIGEM.format(
                                origem=logica.rotulo_origem(registro.origem)
                            ),
                            textos_app.ROTULO_AUTOR.format(autor=registro.autor),
                            textos_app.ROTULO_DATA.format(data=logica.formatar_data(registro.data)),
                        ]
                    )
                )
            else:
                st.caption(textos_app.REGISTRO_NAO_ENCONTRADO)
            st.markdown(logica.como_citacao(alerta.trecho_evidencia))
        st.caption(alerta.justificativa)
        if alerta.trace_url:
            st.markdown(f"[{textos_app.VER_TRACO}]({alerta.trace_url})")
        _area_de_decisao(alerta, contexto)


def _area_de_decisao(alerta, contexto: str) -> None:
    if logica.pode_decidir(alerta.status, alerta.registro_id, LOCAIS):
        colunas = st.columns(len(logica.BOTOES_DECISAO))
        for coluna, (acao, rotulo) in zip(colunas, logica.BOTOES_DECISAO, strict=True):
            coluna.button(
                rotulo,
                key=f"{contexto}_{acao}_{alerta.registro_id}",
                on_click=_decidir,
                args=(alerta.registro_id, acao),
                use_container_width=True,
            )
    elif alerta.status == "pendente":
        st.caption(textos_app.NOTA_SOMENTE_LEITURA)
    elif getattr(alerta, "decisao", None) is not None:
        d = alerta.decisao
        st.caption(
            textos_app.DECIDIDO_POR.format(quem=d.quem, quando=logica.formatar_data(d.quando))
        )


def _registro_de(registro_id: str) -> Registro | None:
    return LOCAIS.get(registro_id) or db.obter_registro(registro_id, caminho=CAMINHO)


def _salvo_de(resultado: dict, registro_id: str):
    """O alerta como está no banco (status atual); se não estiver, o que o grafo devolveu."""
    for salvo in db.listar_alertas(caminho=CAMINHO):
        if salvo.registro_id == registro_id:
            return salvo
    alerta = resultado["alerta"]
    status = "pendente" if resultado.get("acao") == "postar" else "em_resumo"
    return db.AlertaSalvo(
        **alerta.model_dump(), acao=Acao(resultado.get("acao", "descartar")), status=status
    )


# --- aba: fila ---------------------------------------------------------------------------


def aba_fila() -> None:
    col_papel, col_status, col_atualizar = st.columns([2, 2, 1], vertical_alignment="bottom")
    papel = col_papel.selectbox(
        textos_app.FILTRO_PAPEL,
        [None, *logica.PAPEL_FILTRO],
        format_func=lambda v: textos_app.FILTRO_TODOS if v is None else logica.rotulo_papel(v),
        key="filtro_papel",
    )
    status = col_status.selectbox(
        textos_app.FILTRO_STATUS,
        [None, *logica.STATUS_FILTRO],
        format_func=lambda v: textos_app.FILTRO_TODOS if v is None else logica.rotulo_status(v),
        key="filtro_status",
    )
    col_atualizar.button(textos_app.ATUALIZAR, key="atualizar", use_container_width=True)

    alertas = list(reversed(db.listar_alertas(papel=papel, status=status, caminho=CAMINHO)))
    if not alertas:
        st.info(
            textos.TEXTO_SEM_ALERTAS
            if papel is None and status is None
            else textos_app.FILA_VAZIA_FILTRADA
        )
        return
    st.caption(textos_app.CONTAGEM_ALERTAS.format(n=len(alertas)))
    for alerta in alertas:
        cartao_alerta(alerta, _registro_de(alerta.registro_id), "fila")


# --- aba: simular mensagem (plano B) -----------------------------------------------------


def aba_simular() -> None:
    st.caption(textos_app.SIMULAR_INTRO)
    texto = st.text_area(textos_app.CAMPO_MENSAGEM, key="sim_texto")
    col_autor, col_canal = st.columns(2)
    autor = col_autor.selectbox(
        textos_app.CAMPO_AUTOR, logica.autores_do_projeto(ARQUIVO_PROJETO), key="sim_autor"
    )
    canal = col_canal.selectbox(
        textos_app.CAMPO_CANAL, logica.canais_do_projeto(ARQUIVO_PROJETO), key="sim_canal"
    )

    if st.button(textos_app.ENVIAR, key="sim_enviar", type="primary"):
        if not texto.strip():
            st.warning(textos_app.MENSAGEM_VAZIA)
        else:
            _enviar_simulacao(texto, autor, canal)

    simulacao = st.session_state.get(SS_SIMULACAO)
    if simulacao:
        _mostrar_simulacao(simulacao)


def _enviar_simulacao(texto: str, autor: str, canal: str) -> None:
    registro = logica.criar_registro_simulado(texto, autor, canal)
    try:
        with st.spinner(textos_app.ANALISANDO):
            db.salvar_registro(registro, caminho=CAMINHO)
            resultado = grafo.processar(registro)  # o MESMO processar do fluxo real
    except Exception as exc:  # noqa: BLE001 - erro do modelo não derruba o app
        st.session_state[SS_SIMULACAO] = {"erro": logica.mensagem_de_erro(exc)}
    else:
        st.session_state[SS_SIMULACAO] = {
            "registro": registro,
            "resultado": resultado,
            "tipo": logica.classificar_resultado(resultado),
        }


def _mostrar_simulacao(simulacao: dict) -> None:
    if "erro" in simulacao:
        st.error(simulacao["erro"])
        return
    tipo = simulacao["tipo"]
    if tipo == "sem_desvio":
        st.info(textos_app.RESULTADO_SEM_DESVIO)
        return
    registro = simulacao["registro"]
    if tipo == "alerta":
        st.success(textos_app.RESULTADO_ALERTA)
    else:
        st.info(textos_app.RESULTADO_RESUMO)
    alerta = _salvo_de(simulacao["resultado"], registro.id)
    cartao_alerta(alerta, registro, "sim")


# --- aba: histórico ----------------------------------------------------------------------


def aba_historico() -> None:
    st.caption(textos_app.HISTORICO_INTRO)
    if st.button(textos_app.PROCESSAR_HISTORICO, key="historico_processar"):
        _processar_historico()
    resumo = st.session_state.get(SS_HISTORICO)
    if resumo is not None:
        st.success(resumo.texto())
        if resumo.interrompido:
            st.warning(textos_app.HISTORICO_INTERROMPIDO.format(n=logica.MAX_ERROS_SEGUIDOS))
        if resumo.erros:
            with st.expander(textos_app.HISTORICO_ERROS.format(n=len(resumo.erros))):
                for erro in resumo.erros:
                    st.text(erro)


def _processar_historico() -> None:
    try:
        registros = FileSource(PASTA_DADOS).fetch(Consulta(limite=1000))
    except Exception as exc:  # noqa: BLE001
        st.error(textos_app.HISTORICO_FALHA_FONTE.format(detalhe=logica.mensagem_de_erro(exc)))
        return
    if not registros:
        st.warning(textos_app.HISTORICO_SEM_REGISTROS)
        return

    # Reprocessar um alerta que já está no banco sobrescreveria o status dele: pula.
    na_fila = {a.registro_id for a in db.listar_alertas(caminho=CAMINHO)}
    resumo = logica.ResumoHistorico(registros=len(registros))
    total = len(registros)
    barra = st.progress(0.0, text=textos_app.HISTORICO_PROGRESSO.format(atual=0, total=total))
    for i, registro in enumerate(registros, start=1):
        barra.progress(
            (i - 1) / total, text=textos_app.HISTORICO_PROGRESSO.format(atual=i, total=total)
        )
        if registro.id in na_fila or registro.id in LOCAIS:
            resumo.ignorados += 1
            continue
        try:
            db.salvar_registro(registro, caminho=CAMINHO)
            resultado = grafo.processar(registro, contexto_de(registros, registro))
        except Exception as exc:  # noqa: BLE001 - um registro ruim não derruba os outros
            if resumo.contar_erro(registro.id, exc):
                break
        else:
            resumo.contar(resultado)
    barra.empty()
    st.session_state[SS_HISTORICO] = resumo


# --- página ------------------------------------------------------------------------------

st.title(textos.TITULO_APP)

_aviso = st.session_state.pop(SS_AVISO, None)
if _aviso:
    {"sucesso": st.success, "info": st.info, "erro": st.error}[_aviso[0]](_aviso[1])

tab_fila, tab_simular, tab_historico = st.tabs(
    [textos_app.ABA_FILA, textos_app.ABA_SIMULAR, textos_app.ABA_HISTORICO]
)
# Processar primeiro (histórico e simulação) e desenhar a fila por último: assim ela já
# mostra, na mesma execução, o que acabou de ser gerado.
with tab_historico:
    aba_historico()
with tab_simular:
    aba_simular()
with tab_fila:
    aba_fila()
