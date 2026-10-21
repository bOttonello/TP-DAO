from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import obtener_sesion
from backend.core.exceptions import ConflictoDeNegocio
from backend.main import app
from backend.models import EventoCustodia, OrdenAnalisis, Turno
from backend.models.enums import EstadoMuestra, EstadoRemito, TipoAtencion
from backend.schemas import (
    AnalisisCrear,
    AtencionCrear,
    ClienteCrear,
    ClinicaCrear,
    ComponenteFacturaCrear,
    ContenedorCrear,
    DespachoCrear,
    EmpaquetadoCrear,
    EventoCustodiaCrear,
    FacturaCrear,
    LaboratorioCrear,
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


def preparar_escenario(sesion: Session, *, despachar: bool = True) -> dict:
    servicio = ServicioPatitas(sesion)
    cliente = servicio.crear_cliente(
        ClienteCrear(
            nombre="Ana",
            apellido="Pérez",
            tipo_documento="dni",
            numero_documento="30111222",
            email="ana@example.com",
            telefono="3515550000",
            direccion="Córdoba 123",
        )
    )
    mascota = servicio.crear_mascota(
        MascotaCrear(
            cliente_id=cliente.id,
            nombre="Luna",
            especie="perro",
            raza="mestiza",
            sexo="hembra",
            fecha_nacimiento=date.today() - timedelta(days=900),
        )
    )
    clinica = servicio.crear_clinica(
        ClinicaCrear(
            nombre="Clínica Centro",
            codigo="CLI-CEN",
            cuit="30-71111111-1",
            direccion="Centro 100",
            telefono="3514440000",
            email="centro@patitas.com.ar",
        )
    )
    laboratorio = servicio.crear_laboratorio(
        LaboratorioCrear(
            nombre="Laboratorio Central",
            codigo="LAB-01",
            direccion="Parque Industrial 50",
            telefono="3514550000",
            email="laboratorio@patitas.com.ar",
        )
    )
    profesional = servicio.crear_profesional(
        ProfesionalCrear(
            clinica_id=clinica.id,
            matricula="MP-1234",
            nombre="Sofía",
            apellido="López",
            especialidad="Clínica general",
            email="sofia@patitas.com.ar",
            telefono="3514660000",
        )
    )
    analisis = servicio.crear_analisis(
        AnalisisCrear(
            laboratorio_id=laboratorio.id,
            codigo="HEM-01",
            nombre="Hemograma completo",
            descripcion="Recuento celular",
            tipo_muestra="sangre",
            precio=Decimal("14000"),
            tiempo_estimado_horas=12,
        )
    )
    vacuna = servicio.crear_vacuna(
        VacunaCrear(
            nombre="Antirrábica",
            laboratorio_fabricante="VetLab",
            especie_objetivo="perro",
            dosis_ml=Decimal("1"),
            obligatoria=True,
            edad_minima_dias=90,
            intervalo_refuerzo_dias=365,
        )
    )
    contenedor = servicio.crear_contenedor(
        ContenedorCrear(
            codigo="ISO-001",
            descripcion="Conservadora isotérmica chica",
            temperatura_min_c=Decimal("2"),
            temperatura_max_c=Decimal("8"),
            capacidad_muestras=10,
        )
    )
    atencion = servicio.registrar_atencion(
        AtencionCrear(
            mascota_id=mascota.id,
            clinica_id=clinica.id,
            profesional_id=profesional.id,
            tipo="consulta",
            motivo="Decaimiento",
            diagnostico="Anemia a confirmar",
            tratamiento="Reposo e hidratación",
            peso_kg=Decimal("18.5"),
            temperatura_c=Decimal("38.6"),
        )
    )
    orden = servicio.crear_orden_derivacion(
        OrdenDerivacionCrear(
            atencion_id=atencion.id,
            laboratorio_id=laboratorio.id,
            profesional_solicitante_id=profesional.id,
            analisis_ids=[analisis.id],
            indicaciones="Procesar dentro de las 12 horas",
        )
    )
    muestra = servicio.extraer_muestra(
        MuestraExtraer(
            orden_id=orden.id,
            tipo="sangre",
            volumen_ml=Decimal("4"),
            temperatura_min_c=Decimal("2"),
            temperatura_max_c=Decimal("8"),
            sitio_extraccion="Vena cefálica",
            extraida_por="Sofía López",
        )
    )
    remito = servicio.empaquetar_muestras(
        EmpaquetadoCrear(
            muestra_ids=[muestra.id],
            contenedor_id=contenedor.id,
            codigo_precinto="PREC-0001",
            clinica_origen_id=clinica.id,
            laboratorio_destino_id=laboratorio.id,
            temperatura_salida_c=Decimal("4"),
            preparado_por="Sofía López",
        )
    )
    envio = None
    if despachar:
        envio = servicio.despachar_remito(
            remito.id,
            DespachoCrear(
                transportista="TransVet",
                conductor="Mario Gómez",
                vehiculo="AA123BB",
                temperatura_salida_c=Decimal("4"),
            ),
        )
    return {
        "servicio": servicio,
        "cliente": cliente,
        "mascota": mascota,
        "clinica": clinica,
        "laboratorio": laboratorio,
        "profesional": profesional,
        "vacuna": vacuna,
        "atencion": atencion,
        "orden": orden,
        "muestra": muestra,
        "remito": remito,
        "envio": envio,
    }


def test_impide_superposicion_de_turnos(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        inicio = datetime.now(UTC) + timedelta(days=1)
        base = TurnoCrear(
            clinica_id=datos["clinica"].id,
            profesional_id=datos["profesional"].id,
            mascota_id=datos["mascota"].id,
            tipo="control",
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
            motivo="Control",
        )
        turno = datos["servicio"].programar_turno(base)
        assert turno.tipo == TipoAtencion.CONTROL
        with pytest.raises(ConflictoDeNegocio, match="superpone"):
            datos["servicio"].programar_turno(
                TurnoCrear(
                    **base.model_dump(exclude={"inicio", "fin"}),
                    inicio=inicio + timedelta(minutes=15),
                    fin=inicio + timedelta(minutes=45),
                )
            )


def test_impide_programar_un_turno_en_el_pasado(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion, despachar=False)
        inicio = datetime.now(UTC) - timedelta(days=1)
        cantidad_antes = len(sesion.scalars(select(Turno)).all())

        with pytest.raises(ConflictoDeNegocio, match="pasado"):
            datos["servicio"].programar_turno(
                TurnoCrear(
                    clinica_id=datos["clinica"].id,
                    profesional_id=datos["profesional"].id,
                    mascota_id=datos["mascota"].id,
                    tipo="consulta",
                    inicio=inicio,
                    fin=inicio + timedelta(minutes=30),
                    motivo="Control fuera de fecha",
                )
            )

        assert len(sesion.scalars(select(Turno)).all()) == cantidad_antes


def test_valida_peso_y_rango_de_temperatura_en_atencion(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion, despachar=False)
        base = {
            "mascota_id": datos["mascota"].id,
            "clinica_id": datos["clinica"].id,
            "profesional_id": datos["profesional"].id,
            "tipo": "consulta",
            "motivo": "Control térmico",
        }

        assert AtencionCrear(**base, temperatura_c=Decimal("24")).temperatura_c == 24
        assert AtencionCrear(**base, temperatura_c=Decimal("45")).temperatura_c == 45
        with pytest.raises(ValidationError):
            AtencionCrear(**base, temperatura_c=Decimal("23.9"))
        with pytest.raises(ValidationError):
            AtencionCrear(**base, temperatura_c=Decimal("45.1"))
        with pytest.raises(ValidationError):
            AtencionCrear(**base, peso_kg=Decimal("-1"))


def test_listado_de_atenciones_incluye_paciente_para_facturacion(
    sesion: Session,
) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion, despachar=False)
        atencion_id = str(datos["atencion"].id)
        mascota_id = str(datos["mascota"].id)

    def reemplazar_sesion():
        yield sesion

    app.dependency_overrides[obtener_sesion] = reemplazar_sesion
    try:
        with TestClient(app) as cliente:
            respuesta = cliente.get("/api/atenciones")
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 200
    atencion = next(item for item in respuesta.json() if item["id"] == atencion_id)
    assert atencion["mascota_id"] == mascota_id


def test_atencion_conserva_alerta_de_vacuna_obligatoria(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        atencion = datos["atencion"]
        assert atencion.esquema_vacunacion_al_dia is False
        assert atencion.vacunas_pendientes[0]["vacuna"] == "Antirrábica"
        assert atencion.vacunas_pendientes[0]["motivo"] == "nunca_aplicada"


def test_precinto_roto_rechaza_muestra_y_bloquea_resultado(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        recepcion = datos["servicio"].recibir_remito(
            datos["remito"].id,
            RecepcionLaboratorioCrear(
                precinto_intacto=False,
                receptor="Laura Díaz",
                temperatura_recepcion_c=Decimal("4.5"),
            ),
        )
        assert recepcion.muestra_viable is False
        assert datos["muestra"].estado_actual == EstadoMuestra.RECHAZADA
        assert datos["remito"].estado == EstadoRemito.RECHAZADO
        solicitud = sesion.scalar(
            select(OrdenAnalisis).where(OrdenAnalisis.orden_id == datos["orden"].id)
        )
        with pytest.raises(ConflictoDeNegocio, match="viable"):
            datos["servicio"].registrar_resultado(
                ResultadoCrear(
                    orden_analisis_id=solicitud.id,
                    validado_por="Bioq. Laura Díaz",
                    valores={"hematocrito": 32},
                    conclusion="Anemia leve",
                )
            )


def test_flujo_completo_deja_eventos_inmutables(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        datos["servicio"].recibir_remito(
            datos["remito"].id,
            RecepcionLaboratorioCrear(
                precinto_intacto=True,
                receptor="Laura Díaz",
                temperatura_recepcion_c=Decimal("4.5"),
            ),
        )
        solicitud = sesion.scalar(
            select(OrdenAnalisis).where(OrdenAnalisis.orden_id == datos["orden"].id)
        )
        datos["servicio"].registrar_resultado(
            ResultadoCrear(
                orden_analisis_id=solicitud.id,
                validado_por="Bioq. Laura Díaz",
                valores={"hematocrito": 32, "hemoglobina": 11.5},
                conclusion="Anemia leve",
            )
        )
        assert datos["muestra"].estado_actual == EstadoMuestra.ANALIZADA
        assert datos["muestra"].cadena_custodia.cerrada_en is not None
        eventos = sesion.scalars(
            select(EventoCustodia)
            .where(EventoCustodia.muestra_id == datos["muestra"].id)
            .order_by(EventoCustodia.secuencia)
        ).all()
        assert [evento.estado_nuevo for evento in eventos] == [
            EstadoMuestra.EXTRAIDA,
            EstadoMuestra.EMPAQUETADA,
            EstadoMuestra.EN_TRANSITO,
            EstadoMuestra.RECIBIDA,
            EstadoMuestra.ANALIZADA,
        ]

    evento = sesion.scalar(select(EventoCustodia).limit(1))
    evento.actor = "valor alterado"
    with pytest.raises(ValueError, match="inmutable"):
        sesion.flush()
    sesion.rollback()


def test_excursion_termica_rechaza_y_habilita_nueva_extraccion(
    sesion: Session,
) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        eventos = datos["servicio"].registrar_transferencia_custodia(
            datos["envio"].id,
            EventoCustodiaCrear(
                actor="Mario Gómez",
                ubicacion="Centro de transferencia",
                temperatura_c=Decimal("12"),
                observaciones="Lectura del datalogger",
            ),
        )
        assert len(eventos) == 1
        assert eventos[0].estado_anterior == EstadoMuestra.EN_TRANSITO
        assert eventos[0].estado_nuevo == EstadoMuestra.EN_TRANSITO

        recepcion = datos["servicio"].recibir_remito(
            datos["remito"].id,
            RecepcionLaboratorioCrear(
                precinto_intacto=True,
                receptor="Laura Díaz",
                temperatura_recepcion_c=Decimal("4"),
            ),
        )
        assert recepcion.muestra_viable is False
        assert "Temperatura" in recepcion.observaciones
        assert datos["muestra"].estado_actual == EstadoMuestra.RECHAZADA

        solicitud = sesion.scalar(
            select(OrdenAnalisis).where(OrdenAnalisis.orden_id == datos["orden"].id)
        )
        assert solicitud.muestra_id is None
        reemplazo = datos["servicio"].extraer_muestra(
            MuestraExtraer(
                orden_id=datos["orden"].id,
                tipo="sangre",
                volumen_ml=Decimal("4"),
                temperatura_min_c=Decimal("2"),
                temperatura_max_c=Decimal("8"),
                sitio_extraccion="Vena cefálica",
                extraida_por="Sofía López",
            )
        )
        assert reemplazo.id != datos["muestra"].id
        assert reemplazo.estado_actual == EstadoMuestra.EXTRAIDA


def test_impide_despacho_con_temperatura_incompatible(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion, despachar=False)
        with pytest.raises(ConflictoDeNegocio, match="temperatura"):
            datos["servicio"].despachar_remito(
                datos["remito"].id,
                DespachoCrear(
                    transportista="TransVet",
                    conductor="Mario Gómez",
                    vehiculo="AA123BB",
                    temperatura_salida_c=Decimal("20"),
                ),
            )


def test_factura_redondea_y_vincula_el_analisis(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        factura = datos["servicio"].emitir_factura(
            FacturaCrear(
                cliente_id=datos["cliente"].id,
                clinica_id=datos["clinica"].id,
                atencion_id=datos["atencion"].id,
                orden_derivacion_id=datos["orden"].id,
                componentes=[
                    ComponenteFacturaCrear(
                        tipo="laboratorio",
                        descripcion="Procesamiento de hemograma",
                        cantidad=Decimal("1.25"),
                        precio_unitario=Decimal("2.25"),
                    )
                ],
            )
        )
        assert factura.subtotal == Decimal("2.81")
        assert factura.total == Decimal("2.81")
        assert factura.componentes[0].subtotal == Decimal("2.81")
        assert factura.componentes[0].orden_analisis_id is not None

        otra_clinica = datos["servicio"].crear_clinica(
            ClinicaCrear(
                nombre="Clínica Norte",
                codigo="CLI-NOR",
                cuit="30-72222222-2",
                direccion="Norte 200",
                telefono="3514770000",
                email="norte@patitas.com.ar",
            )
        )
        with pytest.raises(ConflictoDeNegocio, match="clínica facturada"):
            datos["servicio"].emitir_factura(
                FacturaCrear(
                    cliente_id=datos["cliente"].id,
                    clinica_id=otra_clinica.id,
                    orden_derivacion_id=datos["orden"].id,
                    componentes=[
                        ComponenteFacturaCrear(
                            tipo="otro",
                            descripcion="Servicio adicional",
                            precio_unitario=Decimal("1"),
                        )
                    ],
                )
            )


def test_api_expone_ids_de_analisis_solicitados(sesion: Session) -> None:
    with sesion.begin():
        datos = preparar_escenario(sesion)
        orden_id = datos["orden"].id

    def reemplazar_sesion():
        yield sesion

    app.dependency_overrides[obtener_sesion] = reemplazar_sesion
    try:
        respuesta = TestClient(app).get(f"/api/ordenes-derivacion/{orden_id}")
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["orden"]["id"] == str(orden_id)
    assert cuerpo["analisis_solicitados"][0]["id"]
    assert (
        cuerpo["analisis_solicitados"][0]["analisis"]["nombre"]
        == "Hemograma completo"
    )
    sesion.rollback()
