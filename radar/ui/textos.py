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
