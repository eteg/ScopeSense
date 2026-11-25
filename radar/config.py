"""Modelos e limiares. Os nomes dos modelos ficam SÓ aqui."""

import os

MODELO_TRIAGEM = "claude-haiku-5-5"  # triagem, juiz do eval, leitura de PDF
MODELO_PRINCIPAL = "claude-sonnet-5-5"  # classificação e extração

LIMIAR_POSTAR = 0.8  # >= 0.8 posta o alerta no grupo do projeto
LIMIAR_RESUMO = 0.5  # 0.5 a 0.8 fica em resumo; < 0.5 descarta e fica no traço

TENTATIVAS_SCHEMA = 2  # novas tentativas quando o modelo devolve saída inválida
K_CLAUSULAS = 3  # cláusulas devolvidas pelo RAG

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/radar.db")
# Projeto monitorado (nome, cliente, canais e pessoas por papel) e PDFs enviados pela tela.
PROJETO_PATH = os.environ.get("PROJETO_PATH", "data/projeto_alfa.json")
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "data/uploads")

# Com MODO_DEMO ligado, as respostas do modelo saem do cache (demo estável e barata).
MODO_DEMO = os.environ.get("MODO_DEMO", "").strip().lower() in {"1", "true", "sim", "yes", "on"}
