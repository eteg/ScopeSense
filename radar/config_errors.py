"""Mensagens de erro de configuração que NUNCA exibem valores do .env (podem ser tokens)."""

from pydantic import ValidationError


def describe_validation_error(exc: ValidationError, prefix: str) -> str:
    """Ex.: 'GMAIL_PARTICIPANTS: campo obrigatório'. Usa só o nome do campo e o motivo."""
    problems = []
    for error in exc.errors(include_input=False, include_url=False):
        field = f"{prefix}{str(error['loc'][0]).upper()}" if error["loc"] else prefix.rstrip("_")
        reason = "campo obrigatório" if error["type"] == "missing" else error["msg"]
        problems.append(f"{field}: {reason}")
    return "; ".join(problems)
