"""Custo de uma chamada ao modelo, em dólar e em reais.

Preços da Anthropic por milhão de tokens (tabela de 2026-11). O raciocínio
(thinking) é cobrado como saída. Cotação do dólar: AwesomeAPI (valor de venda),
guardada por 1 hora; sem internet, usa USD_BRL do .env (marcada como estimada).
Não inclui IOF nem impostos do cartão.
"""

import os
import time
from typing import Any

import httpx

# US$ por milhão de tokens: entrada, saída, leitura de cache e escrita de cache (5 min).
PRECOS_USD_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-5-5": {"entrada": 2.00, "saida": 10.00, "cache_leitura": 0.10, "cache_escrita": 2.50},
    "claude-haiku-5-5": {"entrada": 0.10, "saida": 0.50, "cache_leitura": 0.01, "cache_escrita": 0.125},
    "claude-opus-5-5": {"entrada": 4.00, "saida": 20.00, "cache_leitura": 0.20, "cache_escrita": 5.00},
}
COTACAO_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
COTACAO_PADRAO = 5.80
_cotacao: tuple[float, float, str] | None = None  # (quando, valor, origem)


def cotacao_usd_brl() -> tuple[float, str]:
    """(R$ por US$, origem). Origem: "AwesomeAPI dd/mm hh:mm" ou "estimada"."""
    global _cotacao
    agora = time.monotonic()
    if _cotacao and agora - _cotacao[0] < 3600:
        return _cotacao[1], _cotacao[2]
    try:
        dados = httpx.get(COTACAO_URL, timeout=5).json()["USDBRL"]
        valor = float(dados["ask"])
        data = dados.get("create_date", "")
        origem = f"AwesomeAPI {data[8:10]}/{data[5:7]} {data[11:16]}" if data else "AwesomeAPI"
        _cotacao = (agora, valor, origem)
        return valor, origem
    except Exception:  # noqa: BLE001 - sem cotação, o relatório sai mesmo assim
        return float(os.environ.get("USD_BRL") or COTACAO_PADRAO), "estimada"


def calcular(modelo: str, usage: Any) -> dict:
    """Tokens e custo de uma resposta (`resposta.usage` do SDK da Anthropic)."""
    precos = PRECOS_USD_MTOK.get(modelo)
    detalhes = getattr(usage, "output_tokens_details", None)
    tokens = {
        "entrada": getattr(usage, "input_tokens", 0) or 0,
        "saida": getattr(usage, "output_tokens", 0) or 0,  # já inclui o raciocínio
        "raciocinio": getattr(detalhes, "thinking_tokens", 0) or 0,
        "cache_leitura": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_escrita": getattr(usage, "cache_creation_input_tokens", 0) or 0,
    }
    cotacao, origem = cotacao_usd_brl()
    usd = None
    if precos:
        usd = sum(tokens[k] * precos[k] for k in precos) / 1_000_000
    return {
        "modelo": modelo,
        "tokens": tokens,
        "usd": round(usd, 6) if usd is not None else None,
        "brl": round(usd * cotacao, 4) if usd is not None else None,
        "cotacao_usd_brl": cotacao,
        "cotacao_origem": origem,
        "precos_usd_mtok": precos,
    }
