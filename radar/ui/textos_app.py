"""Textos e rótulos da tela do Streamlit (`app.py`). Sem regra de negócio.

Os rótulos dos botões de decisão e os títulos por tipo de desvio já existem em `tema.py` e
`textos.py`; aqui ficam só os textos novos da fila, da simulação e do histórico.
Tom neutro: "possível desvio", nunca acusação.
"""

# --- abas --------------------------------------------------------------------------------
ABA_FILA = "Fila de alertas"
ABA_SIMULAR = "Simular mensagem"
ABA_HISTORICO = "Histórico"

# --- fila --------------------------------------------------------------------------------
FILTRO_PAPEL = "Responsável"
FILTRO_STATUS = "Status"
FILTRO_TODOS = "Todos"
ATUALIZAR = "Atualizar"
CONTAGEM_ALERTAS = "{n} alerta(s) na fila"
FILA_VAZIA_FILTRADA = "Nenhum alerta com esses filtros."
ROTULO_CLAUSULA = "Cláusula {numero}"
ROTULO_ORIGEM = "Origem: {origem}"
ROTULO_AUTOR = "Autor: {autor}"
ROTULO_DATA = "Data: {data}"
ROTULO_CONFIANCA = "Confiança: {valor}"
ROTULO_RESPONSAVEL = "Responsável: {papel}"
ROTULO_STATUS = "Status: {status}"
SEM_RESPONSAVEL = "sem responsável definido"
REGISTRO_NAO_ENCONTRADO = "Registro de origem não encontrado no banco."
VER_TRACO = "Ver traço no Langfuse"
DECIDIDO_POR = "Decidido por {quem} em {quando}."
NOTA_SOMENTE_LEITURA = (
    "Somente leitura: este alerta foi criado em outro processo (por exemplo, o bot do Slack), "
    "e a aprovação só funciona no processo que o gerou. Decida pelos botões do Slack."
)

ROTULO_STATUS_POR_VALOR = {
    "pendente": "Pendente",
    "aprovado": "Aprovado",
    "descartado": "Descartado",
    "nao_e_desvio": "Não é desvio",
    "em_resumo": "Em resumo",
}
ROTULO_PAPEL_POR_VALOR = {
    "gestor": "Gestor",
    "comercial": "Comercial",
    "administrativo_contratos": "Administrativo de contratos",
}
ROTULO_ORIGEM_POR_VALOR = {
    "slack": "Slack",
    "email": "E-mail",
    "agenda": "Agenda",
    "reuniao": "Reunião",
    "documento": "Documento",
}

# --- decisão -----------------------------------------------------------------------------
QUEM_DECIDE = "Plano B (Streamlit)"
DECISAO_REGISTRADA = "Decisão registrada: {rotulo}."
DECISAO_JA_REGISTRADA = "Este alerta já tinha uma decisão. Nada foi gravado de novo."
DECISAO_ERRO = "Não foi possível registrar a decisão. {detalhe}"

# --- simular mensagem --------------------------------------------------------------------
SIMULAR_INTRO = (
    "Plano B sem Slack: a mensagem digitada aqui segue o mesmo caminho de uma mensagem real "
    "do canal (o mesmo fluxo de análise e de aprovação)."
)
CAMPO_MENSAGEM = "Mensagem"
CAMPO_AUTOR = "Autor"
CAMPO_CANAL = "Canal"
ENVIAR = "Enviar"
ANALISANDO = "Analisando a mensagem..."
MENSAGEM_VAZIA = "Escreva uma mensagem antes de enviar."
RESULTADO_ALERTA = "Possível desvio encontrado. Decida abaixo."
RESULTADO_RESUMO = (
    "Possível desvio com confiança média: ficou no resumo e não gerou alerta para decisão."
)
RESULTADO_SEM_DESVIO = "Sem desvio: nenhum alerta foi gerado para esta mensagem."
AUTORES_PADRAO = ("Autor de teste",)
CANAIS_PADRAO = ("projeto-alfa", "projeto-alfa-cliente")

# --- histórico ---------------------------------------------------------------------------
HISTORICO_INTRO = (
    "Lê os arquivos da pasta data (Slack, reunião, documentos) e passa cada registro pelo "
    "mesmo fluxo de análise. Pode demorar e chama o modelo: só rode quando precisar."
)
PROCESSAR_HISTORICO = "Processar histórico"
HISTORICO_PROGRESSO = "Processando {atual} de {total}..."
HISTORICO_SEM_REGISTROS = "Nenhum registro encontrado na pasta de dados."
HISTORICO_RESUMO = (
    "{registros} registro(s) lido(s): {alertas} alerta(s), {resumos} em resumo, "
    "{ignorados} já na fila (ignorados), {erros} erro(s)."
)
HISTORICO_INTERROMPIDO = "Processamento interrompido após {n} erros seguidos."
HISTORICO_ERROS = "Ver erros ({n})"
HISTORICO_FALHA_FONTE = "Não foi possível ler a pasta de dados. {detalhe}"

# --- erros -------------------------------------------------------------------------------
ERRO_SEM_CHAVE = (
    "O modelo não pôde ser chamado: falta a chave ANTHROPIC_API_KEY (ou ela é inválida). "
    "Preencha no arquivo .env e reinicie o app."
)
ERRO_GENERICO = "Não foi possível processar: {tipo}: {detalhe}"
