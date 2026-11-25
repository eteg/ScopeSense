"""Textos exibidos pelo Radar (títulos, mensagens, rótulos).

Tom neutro: "possível desvio", nunca acusação. O alerta é sobre o contrato, não sobre a pessoa.
Sem regra de negócio neste arquivo.
"""

TITULO_APP = "Radar de Desvios"
STATUS_APP = "Estrutura pronta. As telas entram nas próximas issues."

# Chaves: escopo, prazo, documento, promessa.
TITULO_DESVIO = {
    "escopo": "Possível desvio de escopo",
    "prazo": "Possível desvio de prazo",
    "documento": "Possível pendência de documento do terceiro",
    "promessa": "Possível promessa fora do contrato",
}

ROTULO_CONTRATO = "Contrato"
ROTULO_EVIDENCIA = "Evidência"
TEXTO_SEM_ALERTAS = "Nenhum alerta por enquanto."

# --- Alerta no Slack (G-07/G-08) ---------------------------------------------------------
TITULO_DESVIO_GENERICO = "Possível desvio"
ROTULO_PARA = "Para"
ROTULO_CONFIANCA = "Confiança"
ROTULO_ORIGEM = "Origem"
ROTULO_CLAUSULA = "Cláusula {numero}"
ROTULO_EVIDENCIA_AUTOR = "Evidência ({autor}, {data})"
ROTULO_LINK_ORIGINAL = "Mensagem original"
FORMATO_DATA_ALERTA = "%d/%m %H:%M"
FORMATO_HORA_DECISAO = "%H:%M"

NOME_ORIGEM = {
    "slack": "Slack",
    "email": "E-mail",
    "agenda": "Agenda",
    "reuniao": "Reunião",
    "documento": "Documento",
}

# Linha que troca os botões depois do clique.
LINHA_DECISAO = {
    "aprovar": "Aprovado por {quem} às {hora}",
    "descartar": "Descartado por {quem} às {hora}",
    "nao_e_desvio": "Marcado como não é desvio por {quem} às {hora}",
}

TEXTO_FALLBACK_ALERTA = "{titulo} · cláusula {clausula}"
TEXTO_JA_DECIDIDO = "Este alerta já tem uma decisão registrada."
TEXTO_DECISAO_FALHOU = "Não foi possível registrar a decisão agora. Tente de novo em instantes."
