"""Consultas de reporting del negocio veterinario.

Las funciones de este módulo reciben una :class:`~sqlalchemy.orm.Session` y
devuelven solamente listas, diccionarios y tipos escalares serializables.  No
dependen de extensiones externas: las agregaciones sencillas se hacen en SQL y
los cálculos temporales o prorrateos se terminan en Python para conservar un
resultado estable en SQLite.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from backend.models import (
    Analisis,
    AplicacionVacuna,
    AtencionVeterinaria,
    Cliente,
    ClinicaVeterinaria,
    ComponenteAtencion,
    Envio,
    Factura,
    HistoriaClinica,
    Mascota,
    MuestraBiologica,
    OrdenAnalisis,
    OrdenDerivacion,
    RemitoBiologico,
    Vacuna,
)
from backend.models.enums import EstadoFactura, EstadoMuestra

FechaFiltro = date | datetime | None
ClinicaFiltro = UUID | str | None
DOS_DECIMALES = Decimal("0.01")


def _valor_enum(valor: Any) -> Any:
    return valor.value if isinstance(valor, Enum) else valor


def _id_serializable(valor: UUID | str) -> str:
    return str(valor)


def _id_filtro(valor: ClinicaFiltro) -> UUID | None:
    if valor is None or isinstance(valor, UUID):
        return valor
    return UUID(valor)


def _como_fecha(valor: date | datetime) -> date:
    return valor.date() if isinstance(valor, datetime) else valor


def _validar_rango(desde: FechaFiltro, hasta: FechaFiltro) -> None:
    if desde is not None and hasta is not None and _como_fecha(desde) > _como_fecha(hasta):
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta")


def _filtrar_fecha_datetime(
    sentencia: Any,
    columna: Any,
    desde: FechaFiltro,
    hasta: FechaFiltro,
) -> Any:
    """Aplica un rango inclusivo; una fecha ``hasta`` incluye todo ese día."""

    _validar_rango(desde, hasta)
    if desde is not None:
        limite_desde = desde if isinstance(desde, datetime) else datetime.combine(desde, time.min)
        sentencia = sentencia.where(columna >= limite_desde)
    if hasta is not None:
        if isinstance(hasta, datetime):
            sentencia = sentencia.where(columna <= hasta)
        else:
            sentencia = sentencia.where(
                columna < datetime.combine(hasta + timedelta(days=1), time.min)
            )
    return sentencia


def _filtrar_fecha_date(
    sentencia: Any,
    columna: Any,
    desde: FechaFiltro,
    hasta: FechaFiltro,
) -> Any:
    _validar_rango(desde, hasta)
    if desde is not None:
        sentencia = sentencia.where(columna >= _como_fecha(desde))
    if hasta is not None:
        sentencia = sentencia.where(columna <= _como_fecha(hasta))
    return sentencia


def _porcentaje(parte: int, total: int) -> float:
    return round(parte * 100 / total, 2) if total else 0.0


def _dinero(valor: Decimal) -> float:
    return float(valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP))


def reporte_atenciones_y_derivaciones(
    sesion: Session,
    *,
    desde: FechaFiltro = None,
    hasta: FechaFiltro = None,
    clinica_id: ClinicaFiltro = None,
) -> list[dict[str, Any]]:
    """Agrupa atenciones y órdenes derivadas por clínica y tipo de atención."""

    sentencia = (
        select(
            ClinicaVeterinaria.id.label("clinica_id"),
            ClinicaVeterinaria.nombre.label("clinica"),
            AtencionVeterinaria.tipo.label("tipo_atencion"),
            func.count(distinct(AtencionVeterinaria.id)).label("atenciones"),
            func.count(distinct(OrdenDerivacion.id)).label("derivaciones"),
        )
        .join(AtencionVeterinaria, AtencionVeterinaria.clinica_id == ClinicaVeterinaria.id)
        .outerjoin(OrdenDerivacion, OrdenDerivacion.atencion_id == AtencionVeterinaria.id)
        .group_by(
            ClinicaVeterinaria.id,
            ClinicaVeterinaria.nombre,
            AtencionVeterinaria.tipo,
        )
        .order_by(ClinicaVeterinaria.nombre, AtencionVeterinaria.tipo)
    )
    sentencia = _filtrar_fecha_datetime(sentencia, AtencionVeterinaria.fecha, desde, hasta)
    filtro_clinica = _id_filtro(clinica_id)
    if filtro_clinica is not None:
        sentencia = sentencia.where(ClinicaVeterinaria.id == filtro_clinica)

    resultado: list[dict[str, Any]] = []
    for fila in sesion.execute(sentencia):
        atenciones = int(fila.atenciones)
        derivaciones = int(fila.derivaciones)
        resultado.append(
            {
                "clinica_id": _id_serializable(fila.clinica_id),
                "clinica": fila.clinica,
                "tipo_atencion": _valor_enum(fila.tipo_atencion),
                "atenciones": atenciones,
                "derivaciones": derivaciones,
                "tasa_derivacion_pct": _porcentaje(derivaciones, atenciones),
            }
        )
    return resultado


def reporte_muestras_rechazadas(
    sesion: Session,
    *,
    desde: FechaFiltro = None,
    hasta: FechaFiltro = None,
    clinica_id: ClinicaFiltro = None,
) -> list[dict[str, Any]]:
    """Informa rechazos por clínica/motivo y su tasa sobre muestras enviadas.

    Una muestra se considera enviada cuando pertenece a un remito con fecha de
    despacho. Las clínicas sin rechazos también aparecen, con motivo ``None`` y
    tasa cero, para que el denominador no desaparezca del informe.
    """

    sentencia = (
        select(
            ClinicaVeterinaria.id.label("clinica_id"),
            ClinicaVeterinaria.nombre.label("clinica"),
            MuestraBiologica.estado_actual,
            MuestraBiologica.motivo_rechazo,
            func.count(MuestraBiologica.id).label("cantidad"),
        )
        .join(RemitoBiologico, MuestraBiologica.remito_id == RemitoBiologico.id)
        .join(
            ClinicaVeterinaria,
            RemitoBiologico.clinica_origen_id == ClinicaVeterinaria.id,
        )
        .where(RemitoBiologico.fecha_despacho.is_not(None))
        .group_by(
            ClinicaVeterinaria.id,
            ClinicaVeterinaria.nombre,
            MuestraBiologica.estado_actual,
            MuestraBiologica.motivo_rechazo,
        )
    )
    sentencia = _filtrar_fecha_datetime(sentencia, RemitoBiologico.fecha_despacho, desde, hasta)
    filtro_clinica = _id_filtro(clinica_id)
    if filtro_clinica is not None:
        sentencia = sentencia.where(ClinicaVeterinaria.id == filtro_clinica)

    enviados: dict[UUID, int] = defaultdict(int)
    metadatos: dict[UUID, str] = {}
    rechazos: dict[tuple[UUID, str], int] = defaultdict(int)
    for fila in sesion.execute(sentencia):
        cantidad = int(fila.cantidad)
        enviados[fila.clinica_id] += cantidad
        metadatos[fila.clinica_id] = fila.clinica
        if fila.estado_actual == EstadoMuestra.RECHAZADA:
            motivo = fila.motivo_rechazo or "sin motivo informado"
            rechazos[(fila.clinica_id, motivo)] += cantidad

    resultado: list[dict[str, Any]] = []
    for id_clinica in sorted(enviados, key=lambda valor: metadatos[valor].casefold()):
        motivos = sorted(
            (
                (motivo, cantidad)
                for (id_rechazo, motivo), cantidad in rechazos.items()
                if id_rechazo == id_clinica
            ),
            key=lambda item: item[0].casefold(),
        )
        if not motivos:
            motivos = [(None, 0)]
        total_enviadas = enviados[id_clinica]
        for motivo, cantidad in motivos:
            resultado.append(
                {
                    "clinica_id": _id_serializable(id_clinica),
                    "clinica": metadatos[id_clinica],
                    "motivo_rechazo": motivo,
                    "muestras_rechazadas": cantidad,
                    "muestras_enviadas": total_enviadas,
                    "tasa_rechazo_pct": _porcentaje(cantidad, total_enviadas),
                }
            )
    return resultado


def reporte_tratamientos_y_vacunas_pendientes(
    sesion: Session,
    *,
    desde: FechaFiltro = None,
    hasta: FechaFiltro = None,
    clinica_id: ClinicaFiltro = None,
    fecha_referencia: date | None = None,
) -> list[dict[str, Any]]:
    """Lista tratamientos y vacunas obligatorias pendientes por mascota.

    Cuando se filtra por clínica o rango, se incluyen las mascotas atendidas en
    ese universo. La vigencia de la vacuna es global: una dosis aplicada en otra
    clínica igualmente satisface el esquema. Si no se indica fecha de referencia
    se usa ``hasta`` (cuando es una fecha) o la fecha actual.
    """

    _validar_rango(desde, hasta)
    filtro_clinica = _id_filtro(clinica_id)
    limitar_por_atenciones = desde is not None or hasta is not None or filtro_clinica is not None

    mascotas_stmt = select(
        Mascota.id,
        Mascota.nombre,
        Mascota.especie,
        Mascota.fecha_nacimiento,
        Cliente.id.label("cliente_id"),
        Cliente.nombre.label("cliente_nombre"),
        Cliente.apellido.label("cliente_apellido"),
    ).join(Cliente, Mascota.cliente_id == Cliente.id)
    if limitar_por_atenciones:
        mascotas_stmt = (
            mascotas_stmt.join(HistoriaClinica, HistoriaClinica.mascota_id == Mascota.id)
            .join(
                AtencionVeterinaria,
                AtencionVeterinaria.historia_clinica_id == HistoriaClinica.id,
            )
            .distinct()
        )
        mascotas_stmt = _filtrar_fecha_datetime(
            mascotas_stmt, AtencionVeterinaria.fecha, desde, hasta
        )
        if filtro_clinica is not None:
            mascotas_stmt = mascotas_stmt.where(AtencionVeterinaria.clinica_id == filtro_clinica)
    mascotas_stmt = mascotas_stmt.where(Mascota.activo.is_(True)).order_by(
        Mascota.nombre, Mascota.id
    )
    mascotas = list(sesion.execute(mascotas_stmt))
    if not mascotas:
        return []

    ids_mascotas = [fila.id for fila in mascotas]
    tratamientos_stmt = (
        select(
            HistoriaClinica.mascota_id,
            AtencionVeterinaria.fecha,
            AtencionVeterinaria.tipo,
            AtencionVeterinaria.tratamiento,
            ClinicaVeterinaria.nombre.label("clinica"),
        )
        .join(
            HistoriaClinica,
            AtencionVeterinaria.historia_clinica_id == HistoriaClinica.id,
        )
        .join(
            ClinicaVeterinaria,
            AtencionVeterinaria.clinica_id == ClinicaVeterinaria.id,
        )
        .where(
            HistoriaClinica.mascota_id.in_(ids_mascotas),
            AtencionVeterinaria.tratamiento.is_not(None),
            func.length(func.trim(AtencionVeterinaria.tratamiento)) > 0,
        )
        .order_by(AtencionVeterinaria.fecha)
    )
    tratamientos_stmt = _filtrar_fecha_datetime(
        tratamientos_stmt, AtencionVeterinaria.fecha, desde, hasta
    )
    if filtro_clinica is not None:
        tratamientos_stmt = tratamientos_stmt.where(
            AtencionVeterinaria.clinica_id == filtro_clinica
        )

    tratamientos_por_mascota: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for fila in sesion.execute(tratamientos_stmt):
        tratamientos_por_mascota[fila.mascota_id].append(
            {
                "fecha": fila.fecha.isoformat(),
                "tipo_atencion": _valor_enum(fila.tipo),
                "tratamiento": fila.tratamiento,
                "clinica": fila.clinica,
            }
        )

    if fecha_referencia is None:
        fecha_referencia = _como_fecha(hasta) if hasta is not None else date.today()

    vacunas = list(
        sesion.execute(
            select(
                Vacuna.id,
                Vacuna.nombre,
                Vacuna.especie_objetivo,
                Vacuna.edad_minima_dias,
                Vacuna.intervalo_refuerzo_dias,
            )
            .where(Vacuna.activa.is_(True), Vacuna.obligatoria.is_(True))
            .order_by(Vacuna.nombre)
        )
    )
    ids_vacunas = [fila.id for fila in vacunas]
    ultima_aplicacion: dict[tuple[UUID, UUID], Any] = {}
    if ids_vacunas:
        aplicaciones_stmt = (
            select(
                AplicacionVacuna.mascota_id,
                AplicacionVacuna.vacuna_id,
                AplicacionVacuna.fecha_aplicacion,
                AplicacionVacuna.proxima_aplicacion,
            )
            .where(
                AplicacionVacuna.mascota_id.in_(ids_mascotas),
                AplicacionVacuna.vacuna_id.in_(ids_vacunas),
                AplicacionVacuna.fecha_aplicacion
                < datetime.combine(fecha_referencia + timedelta(days=1), time.min),
            )
            .order_by(AplicacionVacuna.fecha_aplicacion.desc())
        )
        for aplicacion in sesion.execute(aplicaciones_stmt):
            clave = (aplicacion.mascota_id, aplicacion.vacuna_id)
            ultima_aplicacion.setdefault(clave, aplicacion)

    resultado: list[dict[str, Any]] = []
    for mascota in mascotas:
        pendientes: list[dict[str, Any]] = []
        especie = mascota.especie.strip().casefold()
        for vacuna in vacunas:
            if vacuna.especie_objetivo.strip().casefold() != especie:
                continue

            edad_dias = (
                (fecha_referencia - mascota.fecha_nacimiento).days
                if mascota.fecha_nacimiento is not None
                else None
            )
            if edad_dias is not None and edad_dias < vacuna.edad_minima_dias:
                continue

            aplicacion = ultima_aplicacion.get((mascota.id, vacuna.id))
            fecha_vencida: date | None = None
            motivo: str | None = None
            if aplicacion is None:
                motivo = (
                    "edad no verificable"
                    if edad_dias is None and vacuna.edad_minima_dias > 0
                    else "sin aplicación"
                )
            else:
                fecha_vencida = aplicacion.proxima_aplicacion
                if fecha_vencida is None and vacuna.intervalo_refuerzo_dias is not None:
                    fecha_vencida = aplicacion.fecha_aplicacion.date() + timedelta(
                        days=vacuna.intervalo_refuerzo_dias
                    )
                if fecha_vencida is not None and fecha_vencida <= fecha_referencia:
                    motivo = "refuerzo vencido"

            if motivo is not None:
                pendientes.append(
                    {
                        "vacuna_id": _id_serializable(vacuna.id),
                        "vacuna": vacuna.nombre,
                        "motivo": motivo,
                        "vencida_desde": fecha_vencida.isoformat()
                        if fecha_vencida is not None
                        else None,
                    }
                )

        tratamientos = tratamientos_por_mascota.get(mascota.id, [])
        resultado.append(
            {
                "mascota_id": _id_serializable(mascota.id),
                "mascota": mascota.nombre,
                "especie": mascota.especie,
                "cliente_id": _id_serializable(mascota.cliente_id),
                "responsable": f"{mascota.cliente_nombre} {mascota.cliente_apellido}",
                "fecha_referencia": fecha_referencia.isoformat(),
                "tratamientos": tratamientos,
                "cantidad_tratamientos": len(tratamientos),
                "vacunas_obligatorias_pendientes": pendientes,
                "cantidad_vacunas_pendientes": len(pendientes),
            }
        )
    return resultado


def reporte_facturacion_por_clinica_y_componente(
    sesion: Session,
    *,
    desde: FechaFiltro = None,
    hasta: FechaFiltro = None,
    clinica_id: ClinicaFiltro = None,
    incluir_borradores: bool = False,
) -> list[dict[str, Any]]:
    """Desglosa importes por clínica/tipo y prorratea descuentos de factura.

    Las facturas anuladas nunca forman parte de la facturación. Los borradores
    se excluyen salvo pedido explícito. El prorrateo hace que la suma de importes
    netos por componente coincida con el total de las facturas incluidas.
    """

    sentencia = (
        select(
            Factura.id.label("factura_id"),
            Factura.subtotal.label("factura_subtotal"),
            Factura.descuento.label("factura_descuento"),
            ClinicaVeterinaria.id.label("clinica_id"),
            ClinicaVeterinaria.nombre.label("clinica"),
            ComponenteAtencion.tipo,
            ComponenteAtencion.cantidad,
            ComponenteAtencion.subtotal.label("componente_subtotal"),
        )
        .join(ClinicaVeterinaria, Factura.clinica_id == ClinicaVeterinaria.id)
        .join(ComponenteAtencion, ComponenteAtencion.factura_id == Factura.id)
        .where(Factura.estado != EstadoFactura.ANULADA)
        .order_by(ClinicaVeterinaria.nombre, ComponenteAtencion.tipo)
    )
    if not incluir_borradores:
        sentencia = sentencia.where(Factura.estado != EstadoFactura.BORRADOR)
    sentencia = _filtrar_fecha_date(sentencia, Factura.fecha_emision, desde, hasta)
    filtro_clinica = _id_filtro(clinica_id)
    if filtro_clinica is not None:
        sentencia = sentencia.where(ClinicaVeterinaria.id == filtro_clinica)

    acumulados: dict[tuple[UUID, str], dict[str, Any]] = {}
    for fila in sesion.execute(sentencia):
        tipo = _valor_enum(fila.tipo)
        clave = (fila.clinica_id, tipo)
        grupo = acumulados.setdefault(
            clave,
            {
                "clinica": fila.clinica,
                "facturas": set(),
                "cantidad": Decimal("0"),
                "bruto": Decimal("0"),
                "descuento": Decimal("0"),
            },
        )
        bruto = Decimal(fila.componente_subtotal)
        subtotal_factura = Decimal(fila.factura_subtotal)
        descuento_factura = Decimal(fila.factura_descuento)
        descuento_prorrateado = (
            descuento_factura * bruto / subtotal_factura if subtotal_factura > 0 else Decimal("0")
        )
        grupo["facturas"].add(fila.factura_id)
        grupo["cantidad"] += Decimal(fila.cantidad)
        grupo["bruto"] += bruto
        grupo["descuento"] += descuento_prorrateado

    resultado: list[dict[str, Any]] = []
    for (id_clinica, tipo), grupo in sorted(
        acumulados.items(), key=lambda item: (item[1]["clinica"].casefold(), item[0][1])
    ):
        resultado.append(
            {
                "clinica_id": _id_serializable(id_clinica),
                "clinica": grupo["clinica"],
                "tipo_componente": tipo,
                "facturas": len(grupo["facturas"]),
                "cantidad_unidades": float(grupo["cantidad"]),
                "importe_bruto": _dinero(grupo["bruto"]),
                "descuentos_prorrateados": _dinero(grupo["descuento"]),
                "importe_neto": _dinero(grupo["bruto"] - grupo["descuento"]),
            }
        )
    return resultado


def _estadisticas_horas(valores: Iterable[float]) -> dict[str, float | int | None]:
    horas = list(valores)
    if not horas:
        return {"promedio_horas": None, "minimo_horas": None, "maximo_horas": None}
    return {
        "promedio_horas": round(sum(horas) / len(horas), 2),
        "minimo_horas": round(min(horas), 2),
        "maximo_horas": round(max(horas), 2),
    }


def _horas(desde: datetime, hasta: datetime) -> float:
    return (hasta - desde).total_seconds() / 3600


def reporte_tiempos_logisticos(
    sesion: Session,
    *,
    desde: FechaFiltro = None,
    hasta: FechaFiltro = None,
    clinica_id: ClinicaFiltro = None,
    umbral_transito_horas: float = 24.0,
) -> list[dict[str, Any]]:
    """Calcula promedio/mínimo/máximo y demoras de tránsito/procesamiento.

    El tránsito se mide por envío, entre salida y entrega, y se considera
    demorado al superar ``umbral_transito_horas``. El procesamiento se mide por
    muestra entre recepción y análisis; su SLA es el mayor tiempo estimado de
    los análisis asociados (se asume ejecución en paralelo).
    """

    if umbral_transito_horas <= 0:
        raise ValueError("El umbral de tránsito debe ser positivo")
    filtro_clinica = _id_filtro(clinica_id)

    envios_stmt = (
        select(
            ClinicaVeterinaria.id.label("clinica_id"),
            ClinicaVeterinaria.nombre.label("clinica"),
            Envio.id.label("envio_id"),
            Envio.fecha_salida,
            Envio.fecha_entrega,
        )
        .join(RemitoBiologico, Envio.remito_id == RemitoBiologico.id)
        .join(
            ClinicaVeterinaria,
            RemitoBiologico.clinica_origen_id == ClinicaVeterinaria.id,
        )
        .where(Envio.fecha_salida.is_not(None), Envio.fecha_entrega.is_not(None))
    )
    envios_stmt = _filtrar_fecha_datetime(envios_stmt, Envio.fecha_salida, desde, hasta)
    if filtro_clinica is not None:
        envios_stmt = envios_stmt.where(ClinicaVeterinaria.id == filtro_clinica)

    transitos: dict[UUID, list[float]] = defaultdict(list)
    nombres: dict[UUID, str] = {}
    for fila in sesion.execute(envios_stmt):
        duracion = _horas(fila.fecha_salida, fila.fecha_entrega)
        transitos[fila.clinica_id].append(duracion)
        nombres[fila.clinica_id] = fila.clinica

    procesamiento_stmt = (
        select(
            ClinicaVeterinaria.id.label("clinica_id"),
            ClinicaVeterinaria.nombre.label("clinica"),
            MuestraBiologica.id.label("muestra_id"),
            MuestraBiologica.fecha_recepcion,
            MuestraBiologica.fecha_analisis,
            func.max(Analisis.tiempo_estimado_horas).label("sla_horas"),
        )
        .join(RemitoBiologico, MuestraBiologica.remito_id == RemitoBiologico.id)
        .join(
            ClinicaVeterinaria,
            RemitoBiologico.clinica_origen_id == ClinicaVeterinaria.id,
        )
        .outerjoin(OrdenAnalisis, OrdenAnalisis.muestra_id == MuestraBiologica.id)
        .outerjoin(Analisis, OrdenAnalisis.analisis_id == Analisis.id)
        .where(
            MuestraBiologica.fecha_recepcion.is_not(None),
            MuestraBiologica.fecha_analisis.is_not(None),
        )
        .group_by(
            ClinicaVeterinaria.id,
            ClinicaVeterinaria.nombre,
            MuestraBiologica.id,
            MuestraBiologica.fecha_recepcion,
            MuestraBiologica.fecha_analisis,
        )
    )
    procesamiento_stmt = _filtrar_fecha_datetime(
        procesamiento_stmt, MuestraBiologica.fecha_recepcion, desde, hasta
    )
    if filtro_clinica is not None:
        procesamiento_stmt = procesamiento_stmt.where(ClinicaVeterinaria.id == filtro_clinica)

    procesamientos: dict[UUID, list[tuple[float, float | None]]] = defaultdict(list)
    for fila in sesion.execute(procesamiento_stmt):
        duracion = _horas(fila.fecha_recepcion, fila.fecha_analisis)
        sla = float(fila.sla_horas) if fila.sla_horas is not None else None
        procesamientos[fila.clinica_id].append((duracion, sla))
        nombres[fila.clinica_id] = fila.clinica

    resultado: list[dict[str, Any]] = []
    ids_clinicas = set(transitos) | set(procesamientos)
    for id_clinica in sorted(ids_clinicas, key=lambda valor: nombres[valor].casefold()):
        horas_transito = transitos.get(id_clinica, [])
        demorados_transito = [valor for valor in horas_transito if valor > umbral_transito_horas]
        datos_procesamiento = procesamientos.get(id_clinica, [])
        horas_procesamiento = [valor for valor, _sla in datos_procesamiento]
        con_sla = [(valor, sla) for valor, sla in datos_procesamiento if sla is not None]
        demorados_procesamiento = [valor - sla for valor, sla in con_sla if valor > sla]

        transito = {
            "envios_completados": len(horas_transito),
            **_estadisticas_horas(horas_transito),
            "umbral_demora_horas": umbral_transito_horas,
            "envios_demorados": len(demorados_transito),
            "tasa_demora_pct": _porcentaje(len(demorados_transito), len(horas_transito)),
            "exceso_promedio_horas": round(
                sum(valor - umbral_transito_horas for valor in demorados_transito)
                / len(demorados_transito),
                2,
            )
            if demorados_transito
            else 0.0,
        }
        procesamiento = {
            "muestras_analizadas": len(horas_procesamiento),
            **_estadisticas_horas(horas_procesamiento),
            "muestras_con_sla": len(con_sla),
            "muestras_demoradas": len(demorados_procesamiento),
            "tasa_demora_pct": _porcentaje(len(demorados_procesamiento), len(con_sla)),
            "exceso_promedio_horas": round(
                sum(demorados_procesamiento) / len(demorados_procesamiento), 2
            )
            if demorados_procesamiento
            else 0.0,
        }
        resultado.append(
            {
                "clinica_id": _id_serializable(id_clinica),
                "clinica": nombres[id_clinica],
                "transito": transito,
                "procesamiento": procesamiento,
            }
        )
    return resultado


# Alias concisos para una API de servicios estable.
atenciones_y_derivaciones = reporte_atenciones_y_derivaciones
muestras_rechazadas = reporte_muestras_rechazadas
tratamientos_y_vacunas_pendientes = reporte_tratamientos_y_vacunas_pendientes
facturacion_por_clinica_y_componente = reporte_facturacion_por_clinica_y_componente
tiempos_logisticos = reporte_tiempos_logisticos


__all__ = [
    "atenciones_y_derivaciones",
    "facturacion_por_clinica_y_componente",
    "muestras_rechazadas",
    "reporte_atenciones_y_derivaciones",
    "reporte_facturacion_por_clinica_y_componente",
    "reporte_muestras_rechazadas",
    "reporte_tiempos_logisticos",
    "reporte_tratamientos_y_vacunas_pendientes",
    "tiempos_logisticos",
    "tratamientos_y_vacunas_pendientes",
]
