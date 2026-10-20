from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session, selectinload

from backend.core.database import obtener_sesion
from backend.core.exceptions import RecursoNoEncontrado
from backend.models import (
    Analisis,
    AplicacionVacuna,
    AtencionVeterinaria,
    Cliente,
    ClinicaVeterinaria,
    Contenedor,
    Envio,
    EventoCustodia,
    Factura,
    HistoriaClinica,
    LaboratorioCentral,
    Mascota,
    MuestraBiologica,
    OrdenAnalisis,
    OrdenDerivacion,
    ProfesionalVeterinario,
    RemitoBiologico,
    ResultadoAnalisis,
    Turno,
    Vacuna,
)
from backend.models.enums import EstadoMuestra
from backend.schemas import (
    AnalisisCrear,
    AplicacionVacunaCrear,
    AtencionCrear,
    ClienteActualizar,
    ClienteCrear,
    ClinicaCrear,
    ContenedorCrear,
    DespachoCrear,
    EmpaquetadoCrear,
    EventoCustodiaCrear,
    FacturaCrear,
    HistoriaClinicaActualizar,
    LaboratorioCrear,
    MascotaActualizar,
    MascotaCrear,
    MuestraExtraer,
    OrdenDerivacionCrear,
    ProfesionalCrear,
    RecepcionLaboratorioCrear,
    ResultadoCrear,
    TurnoCrear,
    VacunaCrear,
)
from backend.services import ServicioPatitas
from backend.services.reportes import (
    atenciones_y_derivaciones,
    facturacion_por_clinica_y_componente,
    muestras_rechazadas,
    tiempos_logisticos,
    tratamientos_y_vacunas_pendientes,
)

router = APIRouter(prefix="/api")


def _valor_json(valor: Any) -> Any:
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (UUID, date, datetime, Decimal)):
        return str(valor)
    return valor


def serializar(entidad: Any) -> dict[str, Any]:
    """Serializa solo columnas; evita cargar grafos completos accidentalmente."""

    mapper = inspect(type(entidad))
    return {
        atributo.key: _valor_json(getattr(entidad, atributo.key))
        for atributo in mapper.column_attrs
    }


def serializar_lista(entidades: list[Any]) -> list[dict[str, Any]]:
    return [serializar(entidad) for entidad in entidades]


def serializar_orden(orden: OrdenDerivacion) -> dict[str, Any]:
    solicitudes = []
    for solicitud in orden.solicitudes_analisis:
        detalle = serializar(solicitud)
        detalle["analisis"] = serializar(solicitud.analisis)
        detalle["resultado"] = (
            serializar(solicitud.resultado) if solicitud.resultado is not None else None
        )
        solicitudes.append(detalle)
    return {"orden": serializar(orden), "analisis_solicitados": solicitudes}


def serializar_factura(factura: Factura) -> dict[str, Any]:
    return {
        "factura": serializar(factura),
        "componentes": serializar_lista(factura.componentes),
    }


def _crear(sesion: Session, operacion):
    with sesion.begin():
        entidad = operacion(ServicioPatitas(sesion))
        resultado = serializar(entidad)
    return resultado


@router.get("/salud", tags=["Sistema"])
def salud() -> dict[str, str]:
    return {"estado": "ok", "servicio": "Patitas"}


# Clientes y mascotas ---------------------------------------------------------
@router.post("/clientes", status_code=status.HTTP_201_CREATED, tags=["Clientes"])
def crear_cliente(datos: ClienteCrear, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.crear_cliente(datos))


@router.get("/clientes", tags=["Clientes"])
def listar_clientes(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(sesion.scalars(select(Cliente).order_by(Cliente.apellido)).all())


@router.get("/clientes/{cliente_id}", tags=["Clientes"])
def obtener_cliente(cliente_id: UUID, sesion: Session = Depends(obtener_sesion)):
    cliente = sesion.get(Cliente, cliente_id)
    if cliente is None:
        raise RecursoNoEncontrado("cliente", cliente_id)
    return serializar(cliente)


@router.patch("/clientes/{cliente_id}", tags=["Clientes"])
def actualizar_cliente(
    cliente_id: UUID,
    datos: ClienteActualizar,
    sesion: Session = Depends(obtener_sesion),
):
    return _crear(
        sesion, lambda servicio: servicio.actualizar_cliente(cliente_id, datos)
    )


@router.delete("/clientes/{cliente_id}", tags=["Clientes"])
def desactivar_cliente(cliente_id: UUID, sesion: Session = Depends(obtener_sesion)):
    with sesion.begin():
        cliente = sesion.get(Cliente, cliente_id)
        if cliente is None:
            raise RecursoNoEncontrado("cliente", cliente_id)
        cliente.activo = False
    return {"cliente_id": str(cliente_id), "activo": False}


@router.post("/mascotas", status_code=status.HTTP_201_CREATED, tags=["Mascotas"])
def crear_mascota(datos: MascotaCrear, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.crear_mascota(datos))


@router.patch("/mascotas/{mascota_id}", tags=["Mascotas"])
def actualizar_mascota(
    mascota_id: UUID,
    datos: MascotaActualizar,
    sesion: Session = Depends(obtener_sesion),
):
    return _crear(
        sesion, lambda servicio: servicio.actualizar_mascota(mascota_id, datos)
    )


@router.get("/mascotas", tags=["Mascotas"])
def listar_mascotas(
    cliente_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Mascota).order_by(Mascota.nombre)
    if cliente_id:
        consulta = consulta.where(Mascota.cliente_id == cliente_id)
    return serializar_lista(sesion.scalars(consulta).all())


@router.get("/mascotas/{mascota_id}/historia-clinica", tags=["Mascotas"])
def obtener_historia(mascota_id: UUID, sesion: Session = Depends(obtener_sesion)):
    mascota = sesion.scalar(
        select(Mascota)
        .options(
            selectinload(Mascota.historia_clinica).selectinload(
                HistoriaClinica.atenciones
            )
        )
        .where(Mascota.id == mascota_id)
    )
    if mascota is None:
        raise RecursoNoEncontrado("mascota", mascota_id)
    return {
        "mascota": serializar(mascota),
        "historia": serializar(mascota.historia_clinica),
        "atenciones": serializar_lista(mascota.historia_clinica.atenciones),
    }


@router.patch("/mascotas/{mascota_id}/historia-clinica", tags=["Mascotas"])
def actualizar_historia(
    mascota_id: UUID,
    datos: HistoriaClinicaActualizar,
    sesion: Session = Depends(obtener_sesion),
):
    return _crear(
        sesion,
        lambda servicio: servicio.actualizar_historia_clinica(mascota_id, datos),
    )


# Catálogos ------------------------------------------------------------------
@router.post("/clinicas", status_code=201, tags=["Configuración"])
def crear_clinica(datos: ClinicaCrear, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.crear_clinica(datos))


@router.get("/clinicas", tags=["Configuración"])
def listar_clinicas(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(sesion.scalars(select(ClinicaVeterinaria)).all())


@router.post("/laboratorio", status_code=201, tags=["Configuración"])
def crear_laboratorio(
    datos: LaboratorioCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.crear_laboratorio(datos))


@router.get("/laboratorio", tags=["Configuración"])
def obtener_laboratorio(sesion: Session = Depends(obtener_sesion)):
    laboratorio = sesion.scalar(select(LaboratorioCentral).limit(1))
    if laboratorio is None:
        raise RecursoNoEncontrado("laboratorio central", "configuración")
    return serializar(laboratorio)


@router.post("/profesionales", status_code=201, tags=["Configuración"])
def crear_profesional(
    datos: ProfesionalCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.crear_profesional(datos))


@router.get("/profesionales", tags=["Configuración"])
def listar_profesionales(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(sesion.scalars(select(ProfesionalVeterinario)).all())


@router.post("/analisis", status_code=201, tags=["Configuración"])
def crear_analisis(datos: AnalisisCrear, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.crear_analisis(datos))


@router.get("/analisis", tags=["Configuración"])
def listar_analisis(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(sesion.scalars(select(Analisis)).all())


@router.post("/vacunas", status_code=201, tags=["Vacunación"])
def crear_vacuna(datos: VacunaCrear, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.crear_vacuna(datos))


@router.get("/vacunas", tags=["Vacunación"])
def listar_vacunas(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(sesion.scalars(select(Vacuna)).all())


@router.post("/contenedores", status_code=201, tags=["Custodia"])
def crear_contenedor(
    datos: ContenedorCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.crear_contenedor(datos))


@router.get("/contenedores", tags=["Custodia"])
def listar_contenedores(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(sesion.scalars(select(Contenedor)).all())


# Atención -------------------------------------------------------------------
@router.post("/turnos", status_code=201, tags=["Atención clínica"])
def programar_turno(datos: TurnoCrear, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.programar_turno(datos))


@router.get("/turnos", tags=["Atención clínica"])
def listar_turnos(
    profesional_id: UUID | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Turno).order_by(Turno.inicio)
    if profesional_id:
        consulta = consulta.where(Turno.profesional_id == profesional_id)
    if desde:
        consulta = consulta.where(Turno.inicio >= desde)
    if hasta:
        consulta = consulta.where(Turno.inicio < hasta)
    return serializar_lista(sesion.scalars(consulta).all())


@router.post("/atenciones", status_code=201, tags=["Atención clínica"])
def registrar_atencion(
    datos: AtencionCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.registrar_atencion(datos))


@router.get("/atenciones", tags=["Atención clínica"])
def listar_atenciones(
    clinica_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(AtencionVeterinaria).order_by(AtencionVeterinaria.fecha.desc())
    if clinica_id:
        consulta = consulta.where(AtencionVeterinaria.clinica_id == clinica_id)
    return serializar_lista(sesion.scalars(consulta).all())


@router.post("/vacunas/aplicaciones", status_code=201, tags=["Vacunación"])
def aplicar_vacuna(
    datos: AplicacionVacunaCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.aplicar_vacuna(datos))


@router.get("/vacunas/aplicaciones", tags=["Vacunación"])
def listar_aplicaciones_vacunas(
    mascota_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(AplicacionVacuna).order_by(
        AplicacionVacuna.fecha_aplicacion.desc()
    )
    if mascota_id is not None:
        consulta = consulta.where(AplicacionVacuna.mascota_id == mascota_id)
    return serializar_lista(sesion.scalars(consulta).all())


# Laboratorio y transporte ----------------------------------------------------
@router.post("/ordenes-derivacion", status_code=201, tags=["Laboratorio"])
def crear_orden(
    datos: OrdenDerivacionCrear, sesion: Session = Depends(obtener_sesion)
):
    with sesion.begin():
        orden = ServicioPatitas(sesion).crear_orden_derivacion(datos)
        resultado = serializar_orden(orden)
    return resultado


@router.get("/ordenes-derivacion", tags=["Laboratorio"])
def listar_ordenes(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(
        sesion.scalars(select(OrdenDerivacion).order_by(OrdenDerivacion.fecha_emision.desc())).all()
    )


@router.get("/ordenes-derivacion/{orden_id}", tags=["Laboratorio"])
def obtener_orden(orden_id: UUID, sesion: Session = Depends(obtener_sesion)):
    orden = sesion.scalar(
        select(OrdenDerivacion)
        .options(
            selectinload(OrdenDerivacion.solicitudes_analisis).selectinload(
                OrdenAnalisis.analisis
            ),
            selectinload(OrdenDerivacion.solicitudes_analisis).selectinload(
                OrdenAnalisis.resultado
            ),
        )
        .where(OrdenDerivacion.id == orden_id)
    )
    if orden is None:
        raise RecursoNoEncontrado("orden de derivación", orden_id)
    return serializar_orden(orden)


@router.post("/muestras", status_code=201, tags=["Laboratorio"])
def extraer_muestra(datos: MuestraExtraer, sesion: Session = Depends(obtener_sesion)):
    return _crear(sesion, lambda servicio: servicio.extraer_muestra(datos))


@router.get("/muestras", tags=["Laboratorio"])
def listar_muestras(
    orden_id: UUID | None = None,
    remito_id: UUID | None = None,
    estado: EstadoMuestra | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(MuestraBiologica).order_by(
        MuestraBiologica.fecha_extraccion.desc()
    )
    if orden_id is not None:
        consulta = consulta.where(MuestraBiologica.orden_id == orden_id)
    if remito_id is not None:
        consulta = consulta.where(MuestraBiologica.remito_id == remito_id)
    if estado is not None:
        consulta = consulta.where(MuestraBiologica.estado_actual == estado)
    return serializar_lista(sesion.scalars(consulta).all())


@router.post("/muestras/empaquetar", status_code=201, tags=["Custodia"])
def empaquetar_muestras(
    datos: EmpaquetadoCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.empaquetar_muestras(datos))


@router.post("/remitos/{remito_id}/despachar", status_code=201, tags=["Custodia"])
def despachar_remito(
    remito_id: UUID,
    datos: DespachoCrear,
    sesion: Session = Depends(obtener_sesion),
):
    return _crear(sesion, lambda servicio: servicio.despachar_remito(remito_id, datos))


@router.post("/envios/{envio_id}/eventos-custodia", status_code=201, tags=["Custodia"])
def registrar_transferencia(
    envio_id: UUID,
    datos: EventoCustodiaCrear,
    sesion: Session = Depends(obtener_sesion),
):
    with sesion.begin():
        eventos = ServicioPatitas(sesion).registrar_transferencia_custodia(
            envio_id, datos
        )
        resultado = serializar_lista(eventos)
    return resultado


@router.post("/remitos/{remito_id}/recibir", status_code=201, tags=["Custodia"])
def recibir_remito(
    remito_id: UUID,
    datos: RecepcionLaboratorioCrear,
    sesion: Session = Depends(obtener_sesion),
):
    return _crear(sesion, lambda servicio: servicio.recibir_remito(remito_id, datos))


@router.get("/remitos", tags=["Custodia"])
def listar_remitos(sesion: Session = Depends(obtener_sesion)):
    return serializar_lista(
        sesion.scalars(select(RemitoBiologico).order_by(RemitoBiologico.fecha_emision.desc())).all()
    )


@router.get("/envios", tags=["Custodia"])
def listar_envios(
    remito_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Envio).order_by(Envio.fecha_salida.desc())
    if remito_id is not None:
        consulta = consulta.where(Envio.remito_id == remito_id)
    return serializar_lista(sesion.scalars(consulta).all())


@router.get("/muestras/{muestra_id}/trazabilidad", tags=["Custodia"])
def trazabilidad_muestra(
    muestra_id: UUID, sesion: Session = Depends(obtener_sesion)
):
    muestra = sesion.get(MuestraBiologica, muestra_id)
    if muestra is None:
        raise RecursoNoEncontrado("muestra", muestra_id)
    eventos = sesion.scalars(
        select(EventoCustodia)
        .where(EventoCustodia.muestra_id == muestra_id)
        .order_by(EventoCustodia.secuencia)
    ).all()
    return {"muestra": serializar(muestra), "eventos": serializar_lista(eventos)}


@router.post("/resultados", status_code=201, tags=["Laboratorio"])
def registrar_resultado(
    datos: ResultadoCrear, sesion: Session = Depends(obtener_sesion)
):
    return _crear(sesion, lambda servicio: servicio.registrar_resultado(datos))


@router.get("/resultados", tags=["Laboratorio"])
def listar_resultados(
    orden_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = (
        select(ResultadoAnalisis)
        .join(OrdenAnalisis)
        .order_by(ResultadoAnalisis.fecha_resultado.desc())
    )
    if orden_id is not None:
        consulta = consulta.where(OrdenAnalisis.orden_id == orden_id)
    return serializar_lista(sesion.scalars(consulta).all())


@router.post("/facturas", status_code=201, tags=["Facturación"])
def emitir_factura(datos: FacturaCrear, sesion: Session = Depends(obtener_sesion)):
    with sesion.begin():
        factura = ServicioPatitas(sesion).emitir_factura(datos)
        resultado = serializar_factura(factura)
    return resultado


@router.get("/facturas", tags=["Facturación"])
def listar_facturas(
    clinica_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Factura).order_by(Factura.fecha_emision.desc())
    if clinica_id:
        consulta = consulta.where(Factura.clinica_id == clinica_id)
    return serializar_lista(sesion.scalars(consulta).all())


@router.get("/facturas/{factura_id}", tags=["Facturación"])
def obtener_factura(factura_id: UUID, sesion: Session = Depends(obtener_sesion)):
    factura = sesion.scalar(
        select(Factura)
        .options(selectinload(Factura.componentes))
        .where(Factura.id == factura_id)
    )
    if factura is None:
        raise RecursoNoEncontrado("factura", factura_id)
    return serializar_factura(factura)


# Reportes --------------------------------------------------------------------
@router.get("/reportes/atenciones-derivaciones", tags=["Reportes"])
def reporte_atenciones_derivaciones(
    desde: date | None = None,
    hasta: date | None = None,
    clinica_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    return atenciones_y_derivaciones(
        sesion, desde=desde, hasta=hasta, clinica_id=clinica_id
    )


@router.get("/reportes/muestras-rechazadas", tags=["Reportes"])
def reporte_rechazos(
    desde: date | None = None,
    hasta: date | None = None,
    clinica_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    return muestras_rechazadas(
        sesion, desde=desde, hasta=hasta, clinica_id=clinica_id
    )


@router.get("/reportes/tratamientos-vacunas", tags=["Reportes"])
def reporte_tratamientos_vacunas(
    desde: date | None = None,
    hasta: date | None = None,
    clinica_id: UUID | None = None,
    fecha_referencia: date | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    return tratamientos_y_vacunas_pendientes(
        sesion,
        desde=desde,
        hasta=hasta,
        clinica_id=clinica_id,
        fecha_referencia=fecha_referencia,
    )


@router.get("/reportes/facturacion", tags=["Reportes"])
def reporte_facturacion(
    desde: date | None = None,
    hasta: date | None = None,
    clinica_id: UUID | None = None,
    sesion: Session = Depends(obtener_sesion),
):
    return facturacion_por_clinica_y_componente(
        sesion, desde=desde, hasta=hasta, clinica_id=clinica_id
    )


@router.get("/reportes/tiempos-muestras", tags=["Reportes"])
def reporte_tiempos(
    desde: date | None = None,
    hasta: date | None = None,
    clinica_id: UUID | None = None,
    umbral_transito_horas: float = Query(default=24.0, gt=0),
    sesion: Session = Depends(obtener_sesion),
):
    return tiempos_logisticos(
        sesion,
        desde=desde,
        hasta=hasta,
        clinica_id=clinica_id,
        umbral_transito_horas=umbral_transito_horas,
    )
