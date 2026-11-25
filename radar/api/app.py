"""API local do Radar de Desvios. Rodar com: uvicorn radar.api.app:app --reload"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from radar.api.routes import alertas, fontes, gmail, projeto, relatorios, slack
from radar.core.errors import (
    AcessoNegado,
    Conflito,
    EntradaInvalida,
    FalhaNaFonte,
    FonteNaoConfigurada,
    NaoEncontrado,
    RadarError,
)

app = FastAPI(
    title="Radar de Desvios",
    version="0.1.0",
    description="POC do hackathon ETEG 2026. Somente leitura dos canais do projeto.",
)

# Erros do núcleo -> HTTP. Os adaptadores traduzem os erros dos SDKs para estes.
_STATUS: list[tuple[type[RadarError], int]] = [
    (FonteNaoConfigurada, 503),
    (AcessoNegado, 403),  # inclui EscritaBloqueada e ForaDoEscopo
    (NaoEncontrado, 404),
    (Conflito, 409),
    (EntradaInvalida, 422),
    (FalhaNaFonte, 502),
]


@app.exception_handler(RadarError)
async def radar_error_handler(_: Request, exc: RadarError) -> JSONResponse:
    status = next((code for kind, code in _STATUS if isinstance(exc, kind)), 500)
    return JSONResponse(
        status_code=status, content={"detail": str(exc), "erro": type(exc).__name__}
    )


@app.get("/health", tags=["geral"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(fontes.router)
app.include_router(slack.router)
app.include_router(gmail.router)
app.include_router(alertas.router)
app.include_router(projeto.router)
app.include_router(relatorios.router)
