from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from backend.api.routes import router
from backend.core.config import obtener_configuracion
from backend.core.exceptions import ErrorDominio
from backend.domain import ErrorDeDominio

configuracion = obtener_configuracion()
RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
DIRECTORIO_FRONTEND = RAIZ_PROYECTO / "frontend"
app = FastAPI(
    title=configuracion.nombre_aplicacion,
    version="0.1.0",
    description=(
        "Atención veterinaria, derivación de laboratorio y cadena de custodia "
        "inmutable para muestras biológicas."
    ),
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=DIRECTORIO_FRONTEND), name="static")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    """Entrega la interfaz web de Patitas desde el mismo servidor de la API."""

    return FileResponse(DIRECTORIO_FRONTEND / "index.html")


@app.exception_handler(ErrorDominio)
async def manejar_error_dominio(_request: Request, error: ErrorDominio) -> JSONResponse:
    estado = 404 if error.codigo == "recurso_no_encontrado" else 409
    return JSONResponse(
        status_code=estado,
        content={"error": error.codigo, "detalle": error.mensaje},
    )


@app.exception_handler(ErrorDeDominio)
async def manejar_error_state(_request: Request, error: ErrorDeDominio) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": "transicion_estado_invalida", "detalle": str(error)},
    )


@app.exception_handler(IntegrityError)
async def manejar_integridad(_request: Request, _error: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": "integridad_datos",
            "detalle": "La operación viola una restricción de unicidad o relación.",
        },
    )

