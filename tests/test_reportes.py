"""Pruebas integradas de los reportes sobre una base SQLite efímera."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (
    Analisis,
    AtencionVeterinaria,
    Cliente,
    ClinicaVeterinaria,
    ComponenteAtencion,
    Contenedor,
    Envio,
    Factura,
    HistoriaClinica,
    LaboratorioCentral,
    Mascota,
    MuestraBiologica,
    OrdenAnalisis,
    OrdenDerivacion,
    PrecintoSanitario,
    ProfesionalVeterinario,
    RemitoBiologico,
    Vacuna,
)
from app.models.enums import (
    EstadoContenedor,
    EstadoEnvio,
    EstadoFactura,
    EstadoMuestra,
    EstadoOrden,
    EstadoPrecinto,
    EstadoRemito,
    EstadoSolicitudAnalisis,
    SexoMascota,
    TipoAtencion,
    TipoComponente,
    TipoDocumento,
    TipoMuestra,
)
from app.services.reportes import (
    reporte_atenciones_y_derivaciones,
    reporte_facturacion_por_clinica_y_componente,
    reporte_muestras_rechazadas,
    reporte_tiempos_logisticos,
    reporte_tratamientos_y_vacunas_pendientes,
)


@pytest.fixture
def datos() -> dict[str, object]:
    motor = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(motor)

    sesion = Session(motor)
    instante = datetime(2026, 5, 10, 8)
    clinica = ClinicaVeterinaria(
        nombre="Clínica Parque",
        codigo="PARQUE",
        cuit="30-11111111-1",
        direccion="Av. Siempre Viva 123",
        telefono="111111111",
        email="parque@example.com",
        activa=True,
    )
    cliente = Cliente(
        nombre="Ana",
        apellido="Pérez",
        tipo_documento=TipoDocumento.DNI,
        numero_documento="30111222",
        email="ana@example.com",
        telefono="1122223333",
        direccion="Calle 1",
        activo=True,
    )
    mascota = Mascota(
        cliente=cliente,
        nombre="Mora",
        especie="Perro",
        raza="Mestiza",
        fecha_nacimiento=date(2022, 1, 1),
        sexo=SexoMascota.HEMBRA,
        peso_kg=Decimal("12.50"),
        microchip="CHIP-1",
        color="Negro",
        activo=True,
    )
    historia = HistoriaClinica(
        mascota=mascota,
        fecha_apertura=instante - timedelta(days=100),
        antecedentes=None,
        alergias=None,
        observaciones=None,
    )
    profesional = ProfesionalVeterinario(
        clinica=clinica,
        nombre="Laura",
        apellido="Gómez",
        matricula="MV-001",
        email="laura@example.com",
        telefono="1144445555",
        especialidad="Clínica",
        activo=True,
    )
    atencion = AtencionVeterinaria(
        historia_clinica=historia,
        clinica=clinica,
        profesional=profesional,
        turno=None,
        fecha=instante,
        tipo=TipoAtencion.CONSULTA,
        motivo="Decaimiento",
        diagnostico="Gastritis",
        tratamiento="Dieta blanda por 48 horas",
        peso_kg=Decimal("12.50"),
        temperatura_c=Decimal("38.2"),
        observaciones=None,
    )
    laboratorio = LaboratorioCentral(
        nombre="Laboratorio Central",
        codigo="LAB-RED",
        direccion="Ruta 2 km 10",
        telefono="1166667777",
        email="lab@example.com",
        activo=True,
        clave_singleton=1,
    )
    orden = OrdenDerivacion(
        numero="OD-0001",
        atencion=atencion,
        laboratorio=laboratorio,
        profesional_solicitante=profesional,
        fecha_emision=instante + timedelta(minutes=30),
        estado=EstadoOrden.DESPACHADA,
        diagnostico_presuntivo="Gastritis",
        indicaciones="Hemograma",
    )
    analisis = Analisis(
        laboratorio=laboratorio,
        codigo="HEMO",
        nombre="Hemograma completo",
        descripcion=None,
        tipo_muestra=TipoMuestra.SANGRE,
        precio=Decimal("100.00"),
        tiempo_estimado_horas=12,
        requiere_ayuno=False,
        activo=True,
    )
    contenedor = Contenedor(
        codigo="CONT-1",
        descripcion="Conservadora chica",
        capacidad_muestras=5,
        temperatura_min_c=Decimal("2.00"),
        temperatura_max_c=Decimal("8.00"),
        estado=EstadoContenedor.EN_TRANSITO,
        ultima_sanitizacion=instante - timedelta(days=1),
    )
    precinto = PrecintoSanitario(
        codigo="PREC-1",
        estado=EstadoPrecinto.ROTO,
        aplicado_en=instante + timedelta(hours=1),
        verificado_en=instante + timedelta(hours=32),
        observaciones="Dañado durante el traslado",
    )
    salida = instante + timedelta(hours=2)
    entrega = salida + timedelta(hours=30)
    remito = RemitoBiologico(
        numero="RB-0001",
        contenedor=contenedor,
        precinto=precinto,
        clinica_origen=clinica,
        laboratorio_destino=laboratorio,
        fecha_emision=instante + timedelta(hours=1),
        fecha_despacho=salida,
        estado=EstadoRemito.RECHAZADO,
        observaciones=None,
    )
    envio = Envio(
        remito=remito,
        codigo_seguimiento="ENV-0001",
        transportista="Transporte Vet",
        conductor="Juan Ruiz",
        vehiculo="AA000AA",
        fecha_salida=salida,
        fecha_entrega=entrega,
        estado=EstadoEnvio.ENTREGADO,
        temperatura_min_registrada_c=Decimal("3.00"),
        temperatura_max_registrada_c=Decimal("9.00"),
        observaciones=None,
    )
    muestra_analizada = MuestraBiologica(
        codigo="M-OK",
        orden=orden,
        remito=remito,
        tipo=TipoMuestra.SANGRE,
        estado_actual=EstadoMuestra.ANALIZADA,
        fecha_extraccion=instante + timedelta(hours=1),
        fecha_recepcion=entrega,
        fecha_analisis=entrega + timedelta(hours=18),
        volumen_ml=Decimal("5.00"),
        temperatura_min_c=Decimal("2.00"),
        temperatura_max_c=Decimal("8.00"),
        sitio_extraccion="Pata delantera",
        observaciones=None,
        motivo_rechazo=None,
    )
    muestra_rechazada = MuestraBiologica(
        codigo="M-RECH",
        orden=orden,
        remito=remito,
        tipo=TipoMuestra.SANGRE,
        estado_actual=EstadoMuestra.RECHAZADA,
        fecha_extraccion=instante + timedelta(hours=1),
        fecha_recepcion=entrega,
        fecha_analisis=None,
        volumen_ml=Decimal("4.00"),
        temperatura_min_c=Decimal("2.00"),
        temperatura_max_c=Decimal("8.00"),
        sitio_extraccion="Pata delantera",
        observaciones=None,
        motivo_rechazo="Precinto sanitario roto",
    )
    solicitud = OrdenAnalisis(
        orden=orden,
        analisis=analisis,
        muestra=muestra_analizada,
        estado=EstadoSolicitudAnalisis.COMPLETADA,
    )
    vacuna = Vacuna(
        nombre="Antirrábica",
        laboratorio_fabricante="VetPharma",
        especie_objetivo="perro",
        dosis_ml=Decimal("1.00"),
        edad_minima_dias=90,
        intervalo_refuerzo_dias=365,
        obligatoria=True,
        activa=True,
    )
    factura = Factura(
        numero="FC-0001",
        cliente=cliente,
        clinica=clinica,
        atencion=atencion,
        orden_derivacion=orden,
        fecha_emision=instante.date(),
        fecha_vencimiento=instante.date() + timedelta(days=10),
        estado=EstadoFactura.EMITIDA,
        subtotal=Decimal("200.00"),
        descuento=Decimal("20.00"),
        total=Decimal("180.00"),
        emitida_en=instante,
        observaciones=None,
    )
    componente_atencion = ComponenteAtencion(
        factura=factura,
        atencion=atencion,
        orden_analisis=None,
        tipo=TipoComponente.ATENCION,
        descripcion="Consulta clínica",
        cantidad=Decimal("1.00"),
        precio_unitario=Decimal("100.00"),
        subtotal=Decimal("100.00"),
    )
    componente_laboratorio = ComponenteAtencion(
        factura=factura,
        atencion=None,
        orden_analisis=solicitud,
        tipo=TipoComponente.LABORATORIO,
        descripcion="Hemograma",
        cantidad=Decimal("1.00"),
        precio_unitario=Decimal("100.00"),
        subtotal=Decimal("100.00"),
    )

    sesion.add_all(
        [
            envio,
            muestra_rechazada,
            componente_atencion,
            componente_laboratorio,
            vacuna,
        ]
    )
    sesion.commit()
    yield {
        "sesion": sesion,
        "clinica": clinica,
        "mascota": mascota,
        "fecha": instante.date(),
    }
    sesion.close()
    motor.dispose()


def test_atenciones_y_derivaciones_agrupa_y_filtra(datos: dict[str, object]) -> None:
    sesion = datos["sesion"]
    clinica = datos["clinica"]
    assert isinstance(sesion, Session)

    filas = reporte_atenciones_y_derivaciones(
        sesion,
        desde=date(2026, 5, 1),
        hasta=date(2026, 5, 31),
        clinica_id=clinica.id,
    )

    assert filas == [
        {
            "clinica_id": str(clinica.id),
            "clinica": "Clínica Parque",
            "tipo_atencion": "consulta",
            "atenciones": 1,
            "derivaciones": 1,
            "tasa_derivacion_pct": 100.0,
        }
    ]
    assert (
        reporte_atenciones_y_derivaciones(sesion, desde=date(2026, 6, 1), hasta=date(2026, 6, 30))
        == []
    )


def test_muestras_rechazadas_calcula_tasa_sobre_todas_las_enviadas(
    datos: dict[str, object],
) -> None:
    sesion = datos["sesion"]
    assert isinstance(sesion, Session)

    filas = reporte_muestras_rechazadas(sesion, desde=date(2026, 5, 10), hasta=date(2026, 5, 10))

    assert len(filas) == 1
    assert filas[0]["motivo_rechazo"] == "Precinto sanitario roto"
    assert filas[0]["muestras_rechazadas"] == 1
    assert filas[0]["muestras_enviadas"] == 2
    assert filas[0]["tasa_rechazo_pct"] == 50.0


def test_tratamientos_y_vacunas_obligatorias_pendientes(
    datos: dict[str, object],
) -> None:
    sesion = datos["sesion"]
    mascota = datos["mascota"]
    assert isinstance(sesion, Session)

    filas = reporte_tratamientos_y_vacunas_pendientes(
        sesion,
        desde=date(2026, 5, 1),
        hasta=date(2026, 5, 31),
        fecha_referencia=date(2026, 5, 31),
    )

    assert len(filas) == 1
    assert filas[0]["mascota_id"] == str(mascota.id)
    assert filas[0]["tratamientos"][0]["tratamiento"] == "Dieta blanda por 48 horas"
    assert filas[0]["vacunas_obligatorias_pendientes"][0]["vacuna"] == "Antirrábica"
    assert filas[0]["vacunas_obligatorias_pendientes"][0]["motivo"] == "sin aplicación"


def test_facturacion_desglosa_y_prorratea_descuento(datos: dict[str, object]) -> None:
    sesion = datos["sesion"]
    assert isinstance(sesion, Session)

    filas = reporte_facturacion_por_clinica_y_componente(
        sesion, desde=date(2026, 5, 1), hasta=date(2026, 5, 31)
    )

    assert [fila["tipo_componente"] for fila in filas] == ["atencion", "laboratorio"]
    assert sum(fila["importe_bruto"] for fila in filas) == 200.0
    assert sum(fila["descuentos_prorrateados"] for fila in filas) == 20.0
    assert sum(fila["importe_neto"] for fila in filas) == 180.0


def test_tiempos_logisticos_incluye_demoras_y_es_serializable(
    datos: dict[str, object],
) -> None:
    sesion = datos["sesion"]
    assert isinstance(sesion, Session)

    filas = reporte_tiempos_logisticos(
        sesion,
        desde=date(2026, 5, 10),
        hasta=date(2026, 5, 11),
        umbral_transito_horas=24,
    )

    assert len(filas) == 1
    assert filas[0]["transito"]["promedio_horas"] == 30.0
    assert filas[0]["transito"]["envios_demorados"] == 1
    assert filas[0]["transito"]["exceso_promedio_horas"] == 6.0
    assert filas[0]["procesamiento"]["promedio_horas"] == 18.0
    assert filas[0]["procesamiento"]["muestras_demoradas"] == 1
    assert filas[0]["procesamiento"]["exceso_promedio_horas"] == 6.0
    json.dumps(filas)


def test_rango_invalido_es_rechazado(datos: dict[str, object]) -> None:
    sesion = datos["sesion"]
    assert isinstance(sesion, Session)

    with pytest.raises(ValueError, match="fecha desde"):
        reporte_atenciones_y_derivaciones(sesion, desde=date(2026, 6, 1), hasta=date(2026, 5, 1))
