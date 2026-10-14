from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import router
from app.core.config import obtener_configuracion
from app.core.exceptions import ErrorDominio
from app.domain import ErrorDeDominio

configuracion = obtener_configuracion()
app = FastAPI(
    title=configuracion.nombre_aplicacion,
    version="0.1.0",
    description=(
        "Atención veterinaria, derivación de laboratorio y cadena de custodia "
        "inmutable para muestras biológicas."
    ),
)
app.include_router(router)


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

