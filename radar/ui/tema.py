"""Tokens visuais do Radar (cores, fontes, emoji por desvio, rótulos dos botões).

Estética isolada aqui para ser trocada de uma vez quando o design da Lara chegar.
Sem regra de negócio neste arquivo.
"""

CORES = {
    "primaria": "#1F3A5F",
    "fundo": "#FFFFFF",
    "texto": "#1A1A1A",
    "texto_suave": "#5F6B7A",
    "borda": "#D9DEE5",
    "alerta": "#B45309",
}

FONTES = {
    "titulo": "sans-serif",
    "corpo": "sans-serif",
}

# Emoji por tipo de desvio (chaves: escopo, prazo, documento, promessa).
EMOJI_DESVIO = {
    "escopo": ":mag:",
    "prazo": ":hourglass_flowing_sand:",
    "documento": ":page_facing_up:",
    "promessa": ":speech_balloon:",
}

# Rótulos dos botões da DM/alerta.
ROTULO_APROVAR = "Aprovar"
ROTULO_DESCARTAR = "Descartar"
ROTULO_NAO_E_DESVIO = "Não é desvio"
