from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.core.exceptions import ConflictoDeNegocio, RecursoNoEncontrado
from backend.domain import CicloVidaMuestra, CicloVidaRemito, TransicionEstado
from backend.models import (
    Analisis,
    AplicacionVacuna,
    AtencionVeterinaria,
    CadenaCustodia,
    Cliente,
    ClinicaVeterinaria,
    ComponenteAtencion,
    Contenedor,
    Envio,
    EventoCustodia,
    EventoRemito,
    Factura,
    HistoriaClinica,
    LaboratorioCentral,
    Mascota,
    MuestraBiologica,
    OrdenAnalisis,
    OrdenDerivacion,
    PrecintoSanitario,
    ProfesionalVeterinario,
    RecepcionLaboratorio,
    RemitoBiologico,
    ResultadoAnalisis,
    Turno,
    Vacuna,
)
from backend.models.enums import (
    EstadoContenedor,
    EstadoEnvio,
    EstadoFactura,
    EstadoMuestra,
    EstadoOrden,
    EstadoPrecinto,
    EstadoRemito,
    EstadoSolicitudAnalisis,
    EstadoTurno,
    PrioridadOrden,
    SexoMascota,
    TipoAtencion,
    TipoComponente,
    TipoDocumento,
    TipoEventoCustodia,
    TipoEventoRemito,
    TipoMuestra,
)
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

CENTAVO = Decimal("0.01")


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def _numero(prefijo: str) -> str:
    return f"{prefijo}-{ahora_utc():%Y%m%d}-{uuid4().hex[:10].upper()}"


class ServicioPatitas:
    """Orquesta los casos de uso y conserva cada regla dentro de una transacción.

    Los métodos no hacen ``commit``: la API o el consumidor decide el límite de
    la transacción. Sí usan ``flush`` cuando necesitan IDs o relaciones.
    """

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def _obtener(self, modelo: type, identificador: UUID, nombre: str):
        entidad = self.sesion.get(modelo, identificador)
        if entidad is None:
            raise RecursoNoEncontrado(nombre, identificador)
        return entidad

    # ------------------------------------------------------------------
    # Maestros y núcleo clínico
    # ------------------------------------------------------------------
    def crear_cliente(self, datos: ClienteCrear) -> Cliente:
        cliente = Cliente(
            nombre=datos.nombre,
            apellido=datos.apellido,
            tipo_documento=TipoDocumento(datos.tipo_documento),
            numero_documento=datos.numero_documento,
            email=str(datos.email),
            telefono=datos.telefono,
            direccion=datos.direccion,
        )
        self.sesion.add(cliente)
        self.sesion.flush()
        return cliente

    def actualizar_cliente(self, cliente_id: UUID, datos: ClienteActualizar) -> Cliente:
        cliente = self._obtener(Cliente, cliente_id, "cliente")
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            setattr(cliente, campo, str(valor) if campo == "email" and valor else valor)
        self.sesion.flush()
        return cliente

    def crear_mascota(self, datos: MascotaCrear) -> Mascota:
        cliente = self._obtener(Cliente, datos.cliente_id, "cliente")
        if not cliente.activo:
            raise ConflictoDeNegocio("No se puede asociar una mascota a un cliente inactivo")
        mascota = Mascota(
            cliente_id=cliente.id,
            nombre=datos.nombre,
            especie=datos.especie.lower(),
            raza=datos.raza,
            fecha_nacimiento=datos.fecha_nacimiento,
            sexo=datos.sexo,
            microchip=datos.microchip,
            color=datos.color,
            peso_kg=datos.peso_kg,
        )
        mascota.historia_clinica = HistoriaClinica(
            fecha_apertura=ahora_utc(),
            antecedentes=None,
            alergias=None,
            observaciones=None,
        )
        self.sesion.add(mascota)
        self.sesion.flush()
        return mascota

    def actualizar_mascota(
        self, mascota_id: UUID, datos: MascotaActualizar
    ) -> Mascota:
        mascota = self._obtener(Mascota, mascota_id, "mascota")
        cambios = datos.model_dump(exclude_unset=True)
        if "especie" in cambios:
            cambios["especie"] = cambios["especie"].lower()
        if "sexo" in cambios:
            cambios["sexo"] = SexoMascota(cambios["sexo"])
        for campo, valor in cambios.items():
            setattr(mascota, campo, valor)
        self.sesion.flush()
        return mascota

    def actualizar_historia_clinica(
        self, mascota_id: UUID, datos: HistoriaClinicaActualizar
    ) -> HistoriaClinica:
        mascota = self._obtener(Mascota, mascota_id, "mascota")
        if mascota.historia_clinica is None:
            raise ConflictoDeNegocio("La mascota no tiene historia clínica")
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            setattr(mascota.historia_clinica, campo, valor)
        self.sesion.flush()
        return mascota.historia_clinica

    def crear_clinica(self, datos: ClinicaCrear) -> ClinicaVeterinaria:
        clinica = ClinicaVeterinaria(**datos.model_dump(mode="python"))
        if clinica.email is not None:
            clinica.email = str(clinica.email)
        self.sesion.add(clinica)
        self.sesion.flush()
        return clinica

    def crear_laboratorio(self, datos: LaboratorioCrear) -> LaboratorioCentral:
        existente = self.sesion.scalar(select(LaboratorioCentral).limit(1))
        if existente is not None:
            raise ConflictoDeNegocio(
                "La red ya tiene configurado su laboratorio central singleton"
            )
        laboratorio = LaboratorioCentral(**datos.model_dump(mode="python"))
        laboratorio.email = str(laboratorio.email) if laboratorio.email else ""
        self.sesion.add(laboratorio)
        self.sesion.flush()
        return laboratorio

    def crear_profesional(self, datos: ProfesionalCrear) -> ProfesionalVeterinario:
        clinica = self._obtener(ClinicaVeterinaria, datos.clinica_id, "clínica")
        if not clinica.activa:
            raise ConflictoDeNegocio("La clínica indicada está inactiva")
        profesional = ProfesionalVeterinario(
            **datos.model_dump(mode="python", exclude={"email"}),
            email=str(datos.email),
        )
        self.sesion.add(profesional)
        self.sesion.flush()
        return profesional

    def crear_analisis(self, datos: AnalisisCrear) -> Analisis:
        laboratorio = self._obtener(
            LaboratorioCentral, datos.laboratorio_id, "laboratorio"
        )
        if not laboratorio.activo:
            raise ConflictoDeNegocio("El laboratorio central está inactivo")
        analisis = Analisis(
            **datos.model_dump(mode="python", exclude={"tipo_muestra"}),
            tipo_muestra=TipoMuestra(datos.tipo_muestra.lower()),
        )
        self.sesion.add(analisis)
        self.sesion.flush()
        return analisis

    def crear_vacuna(self, datos: VacunaCrear) -> Vacuna:
        vacuna = Vacuna(**datos.model_dump(mode="python"))
        self.sesion.add(vacuna)
        self.sesion.flush()
        return vacuna

    def crear_contenedor(self, datos: ContenedorCrear) -> Contenedor:
        contenedor = Contenedor(**datos.model_dump(mode="python"))
        self.sesion.add(contenedor)
        self.sesion.flush()
        return contenedor

    # ------------------------------------------------------------------
    # Agenda, atención y vacunación
    # ------------------------------------------------------------------
    def programar_turno(self, datos: TurnoCrear) -> Turno:
        profesional = self.sesion.get(
            ProfesionalVeterinario, datos.profesional_id, with_for_update=True
        )
        if profesional is None:
            raise RecursoNoEncontrado("profesional", datos.profesional_id)
        mascota = self._obtener(Mascota, datos.mascota_id, "mascota")
        clinica = self._obtener(ClinicaVeterinaria, datos.clinica_id, "clínica")
        if not profesional.activo:
            raise ConflictoDeNegocio("El profesional está inactivo")
        if not clinica.activa:
            raise ConflictoDeNegocio("La clínica está inactiva")
        if not mascota.activo or not mascota.cliente.activo:
            raise ConflictoDeNegocio("La mascota o su responsable están inactivos")
        if profesional.clinica_id != datos.clinica_id:
            raise ConflictoDeNegocio("El profesional no pertenece a la clínica indicada")

        superpuesto = self.sesion.scalar(
            select(Turno.id)
            .where(
                Turno.profesional_id == datos.profesional_id,
                Turno.estado.notin_([EstadoTurno.CANCELADO, EstadoTurno.AUSENTE]),
                Turno.inicio < datos.fin,
                Turno.fin > datos.inicio,
            )
            .limit(1)
        )
        if superpuesto is not None:
            raise ConflictoDeNegocio(
                "El profesional ya tiene un turno que se superpone con ese horario"
            )

        turno = Turno(**datos.model_dump(mode="python"), estado=EstadoTurno.PROGRAMADO)
        self.sesion.add(turno)
        self.sesion.flush()
        return turno

    def _vacunas_pendientes(self, mascota: Mascota, en_fecha: date) -> list[dict[str, object]]:
        vacunas = self.sesion.scalars(
            select(Vacuna).where(
                Vacuna.activa.is_(True),
                Vacuna.obligatoria.is_(True),
                func.lower(Vacuna.especie_objetivo) == mascota.especie.lower(),
            )
        ).all()
        edad_dias = None
        if mascota.fecha_nacimiento is not None:
            edad_dias = (en_fecha - mascota.fecha_nacimiento).days

        pendientes: list[dict[str, object]] = []
        for vacuna in vacunas:
            if edad_dias is not None and edad_dias < vacuna.edad_minima_dias:
                continue
            ultima = self.sesion.scalar(
                select(AplicacionVacuna)
                .where(
                    AplicacionVacuna.mascota_id == mascota.id,
                    AplicacionVacuna.vacuna_id == vacuna.id,
                )
                .order_by(AplicacionVacuna.fecha_aplicacion.desc())
                .limit(1)
            )
            motivo: str | None = None
            vencida_desde: str | None = None
            if ultima is None:
                motivo = "nunca_aplicada"
            elif vacuna.intervalo_refuerzo_dias:
                vencimiento = ultima.fecha_aplicacion.date() + timedelta(
                    days=vacuna.intervalo_refuerzo_dias
                )
                if vencimiento <= en_fecha:
                    motivo = "refuerzo_vencido"
                    vencida_desde = vencimiento.isoformat()
            if motivo:
                pendientes.append(
                    {
                        "vacuna_id": str(vacuna.id),
                        "vacuna": vacuna.nombre,
                        "motivo": motivo,
                        "vencida_desde": vencida_desde,
                    }
                )
        return pendientes

    def registrar_atencion(self, datos: AtencionCrear) -> AtencionVeterinaria:
        mascota = self._obtener(Mascota, datos.mascota_id, "mascota")
        profesional = self._obtener(
            ProfesionalVeterinario, datos.profesional_id, "profesional"
        )
        clinica = self._obtener(ClinicaVeterinaria, datos.clinica_id, "clínica")
        if not profesional.activo:
            raise ConflictoDeNegocio("El profesional está inactivo")
        if not clinica.activa:
            raise ConflictoDeNegocio("La clínica está inactiva")
        if not mascota.activo or not mascota.cliente.activo:
            raise ConflictoDeNegocio("La mascota o su responsable están inactivos")
        if profesional.clinica_id != datos.clinica_id:
            raise ConflictoDeNegocio("El profesional no pertenece a la clínica indicada")
        if mascota.historia_clinica is None:
            raise ConflictoDeNegocio("La mascota no tiene historia clínica")

        turno = None
        if datos.turno_id is not None:
            turno = self._obtener(Turno, datos.turno_id, "turno")
            if (
                turno.mascota_id != mascota.id
                or turno.profesional_id != profesional.id
                or turno.clinica_id != datos.clinica_id
            ):
                raise ConflictoDeNegocio("El turno no coincide con los datos de la atención")
            if turno.estado in {EstadoTurno.CANCELADO, EstadoTurno.AUSENTE, EstadoTurno.ATENDIDO}:
                raise ConflictoDeNegocio("El turno no está disponible para registrar atención")
            turno.estado = EstadoTurno.ATENDIDO

        pendientes = self._vacunas_pendientes(mascota, ahora_utc().date())
        atencion = AtencionVeterinaria(
            historia_clinica_id=mascota.historia_clinica.id,
            turno_id=datos.turno_id,
            clinica_id=datos.clinica_id,
            profesional_id=datos.profesional_id,
            fecha=ahora_utc(),
            tipo=TipoAtencion(datos.tipo),
            motivo=datos.motivo,
            diagnostico=datos.diagnostico,
            tratamiento=datos.tratamiento,
            peso_kg=datos.peso_kg,
            temperatura_c=datos.temperatura_c,
            observaciones=datos.observaciones,
            esquema_vacunacion_al_dia=not pendientes,
            vacunas_pendientes=pendientes,
        )
        if datos.peso_kg is not None:
            mascota.peso_kg = datos.peso_kg
        self.sesion.add(atencion)
        self.sesion.flush()
        return atencion

    def aplicar_vacuna(self, datos: AplicacionVacunaCrear) -> AplicacionVacuna:
        mascota = self._obtener(Mascota, datos.mascota_id, "mascota")
        vacuna = self._obtener(Vacuna, datos.vacuna_id, "vacuna")
        atencion = self._obtener(AtencionVeterinaria, datos.atencion_id, "atención")
        profesional = self._obtener(
            ProfesionalVeterinario, datos.profesional_id, "profesional"
        )
        if atencion.historia_clinica.mascota_id != mascota.id:
            raise ConflictoDeNegocio("La atención no pertenece a la mascota indicada")
        if not mascota.activo:
            raise ConflictoDeNegocio("La mascota está inactiva")
        if not vacuna.activa:
            raise ConflictoDeNegocio("La vacuna está inactiva")
        if not profesional.activo or profesional.clinica_id != atencion.clinica_id:
            raise ConflictoDeNegocio(
                "El profesional no está activo en la clínica de la atención"
            )
        if vacuna.especie_objetivo.lower() != mascota.especie.lower():
            raise ConflictoDeNegocio("La vacuna no corresponde a la especie de la mascota")
        if (
            mascota.fecha_nacimiento is not None
            and datos.aplicada_en.date() < mascota.fecha_nacimiento
        ):
            raise ConflictoDeNegocio("La vacuna no puede anteceder al nacimiento")
        aplicacion = AplicacionVacuna(
            vacuna_id=vacuna.id,
            mascota_id=mascota.id,
            atencion_id=atencion.id,
            profesional_id=datos.profesional_id,
            fecha_aplicacion=datos.aplicada_en,
            dosis_ml=datos.dosis_ml or vacuna.dosis_ml,
            lote=datos.lote,
            fecha_vencimiento_lote=datos.fecha_vencimiento_lote,
            proxima_aplicacion=datos.proxima_dosis,
            observaciones=datos.observaciones,
        )
        self.sesion.add(aplicacion)
        self.sesion.flush()
        return aplicacion

    # ------------------------------------------------------------------
    # Derivación, muestra y custodia
    # ------------------------------------------------------------------
    def crear_orden_derivacion(self, datos: OrdenDerivacionCrear) -> OrdenDerivacion:
        atencion = self._obtener(AtencionVeterinaria, datos.atencion_id, "atención")
        laboratorio = self._obtener(
            LaboratorioCentral, datos.laboratorio_id, "laboratorio"
        )
        profesional = self._obtener(
            ProfesionalVeterinario,
            datos.profesional_solicitante_id,
            "profesional solicitante",
        )
        if profesional.id != atencion.profesional_id:
            raise ConflictoDeNegocio(
                "La orden debe ser emitida por el profesional que registró la atención"
            )
        if not laboratorio.activo:
            raise ConflictoDeNegocio("El laboratorio central está inactivo")
        if not profesional.activo:
            raise ConflictoDeNegocio("El profesional solicitante está inactivo")
        if len(datos.analisis_ids) != len(set(datos.analisis_ids)):
            raise ConflictoDeNegocio("No se puede solicitar el mismo análisis dos veces")
        analisis = self.sesion.scalars(
            select(Analisis).where(Analisis.id.in_(datos.analisis_ids))
        ).all()
        if len(analisis) != len(set(datos.analisis_ids)):
            raise ConflictoDeNegocio("Uno o más análisis solicitados no existen")
        if any(item.laboratorio_id != laboratorio.id or not item.activo for item in analisis):
            raise ConflictoDeNegocio(
                "Todos los análisis deben estar activos y pertenecer al laboratorio central"
            )
        orden = OrdenDerivacion(
            numero=_numero("ORD"),
            atencion_id=atencion.id,
            laboratorio_id=laboratorio.id,
            profesional_solicitante_id=profesional.id,
            fecha_emision=ahora_utc(),
            estado=EstadoOrden.EMITIDA,
            prioridad=PrioridadOrden(datos.prioridad),
            diagnostico_presuntivo=atencion.diagnostico,
            indicaciones=datos.indicaciones,
        )
        orden.solicitudes_analisis = [
            OrdenAnalisis(analisis_id=item.id, estado=EstadoSolicitudAnalisis.PENDIENTE)
            for item in analisis
        ]
        self.sesion.add(orden)
        self.sesion.flush()
        return orden

    def extraer_muestra(self, datos: MuestraExtraer) -> MuestraBiologica:
        orden = self._obtener(OrdenDerivacion, datos.orden_id, "orden de derivación")
        if orden.estado not in {
            EstadoOrden.EMITIDA,
            EstadoOrden.MUESTRA_EXTRAIDA,
            EstadoOrden.REQUIERE_NUEVA_MUESTRA,
        }:
            raise ConflictoDeNegocio("La orden no admite nuevas muestras")
        tipo = TipoMuestra(datos.tipo.lower())
        solicitudes = self.sesion.scalars(
            select(OrdenAnalisis)
            .join(OrdenAnalisis.analisis)
            .where(
                OrdenAnalisis.orden_id == orden.id,
                OrdenAnalisis.muestra_id.is_(None),
                Analisis.tipo_muestra == tipo,
            )
        ).all()
        if not solicitudes:
            raise ConflictoDeNegocio(
                "La orden no tiene análisis pendientes para ese tipo de muestra"
            )
        muestra = MuestraBiologica(
            codigo=_numero("MUE"),
            orden_id=orden.id,
            tipo=tipo,
            estado_actual=EstadoMuestra.EXTRAIDA,
            fecha_extraccion=ahora_utc(),
            volumen_ml=datos.volumen_ml,
            temperatura_min_c=datos.temperatura_min_c,
            temperatura_max_c=datos.temperatura_max_c,
            sitio_extraccion=datos.sitio_extraccion,
            observaciones=datos.observaciones,
        )
        muestra.cadena_custodia = CadenaCustodia(abierta_en=ahora_utc())
        self.sesion.add(muestra)
        self.sesion.flush()
        for solicitud in solicitudes:
            solicitud.muestra_id = muestra.id
        orden.estado = EstadoOrden.MUESTRA_EXTRAIDA
        self._evento_inicial_muestra(
            muestra,
            actor=datos.extraida_por,
            ubicacion=orden.atencion.clinica.nombre,
            observaciones=datos.observaciones,
        )
        self.sesion.flush()
        return muestra

    def _evento_inicial_muestra(
        self,
        muestra: MuestraBiologica,
        *,
        actor: str,
        ubicacion: str,
        observaciones: str | None,
    ) -> None:
        self.sesion.add(
            EventoCustodia(
                cadena_custodia_id=muestra.cadena_custodia.id,
                muestra_id=muestra.id,
                secuencia=1,
                tipo_evento=TipoEventoCustodia.EXTRACCION,
                estado_anterior=None,
                estado_nuevo=EstadoMuestra.EXTRAIDA,
                ocurrido_en=ahora_utc(),
                actor=actor,
                ubicacion=ubicacion,
                observaciones=observaciones,
            )
        )

    def _agregar_evento_muestra(
        self,
        muestra: MuestraBiologica,
        transicion: TransicionEstado,
        *,
        tipo: TipoEventoCustodia,
        actor: str,
        ubicacion: str,
        envio_id: UUID | None = None,
        temperatura_c: Decimal | None = None,
        observaciones: str | None = None,
    ) -> None:
        secuencia = self.sesion.scalar(
            select(func.coalesce(func.max(EventoCustodia.secuencia), 0)).where(
                EventoCustodia.muestra_id == muestra.id
            )
        )
        muestra.estado_actual = EstadoMuestra(transicion.estado_nuevo)
        self.sesion.add(
            EventoCustodia(
                cadena_custodia_id=muestra.cadena_custodia.id,
                muestra_id=muestra.id,
                envio_id=envio_id,
                secuencia=int(secuencia or 0) + 1,
                tipo_evento=tipo,
                estado_anterior=EstadoMuestra(transicion.estado_anterior),
                estado_nuevo=EstadoMuestra(transicion.estado_nuevo),
                ocurrido_en=transicion.ocurrida_en,
                actor=actor,
                ubicacion=ubicacion,
                temperatura_c=temperatura_c,
                observaciones=observaciones or transicion.detalle,
            )
        )

    def _agregar_evento_remito(
        self,
        remito: RemitoBiologico,
        *,
        tipo: TipoEventoRemito,
        actor: str,
        estado_anterior: EstadoRemito | None,
        estado_nuevo: EstadoRemito,
        observaciones: str | None = None,
    ) -> None:
        secuencia = self.sesion.scalar(
            select(func.coalesce(func.max(EventoRemito.secuencia), 0)).where(
                EventoRemito.remito_id == remito.id
            )
        )
        self.sesion.add(
            EventoRemito(
                remito_id=remito.id,
                secuencia=int(secuencia or 0) + 1,
                tipo_evento=tipo,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                ocurrido_en=ahora_utc(),
                actor=actor,
                observaciones=observaciones,
            )
        )

    def empaquetar_muestras(self, datos: EmpaquetadoCrear) -> RemitoBiologico:
        contenedor = self.sesion.get(Contenedor, datos.contenedor_id, with_for_update=True)
        if contenedor is None:
            raise RecursoNoEncontrado("contenedor", datos.contenedor_id)
        self._obtener(ClinicaVeterinaria, datos.clinica_origen_id, "clínica")
        laboratorio = self._obtener(
            LaboratorioCentral, datos.laboratorio_destino_id, "laboratorio"
        )
        if len(datos.muestra_ids) != len(set(datos.muestra_ids)):
            raise ConflictoDeNegocio("No se puede repetir una muestra en el remito")
        muestras = self.sesion.scalars(
            select(MuestraBiologica)
            .options(selectinload(MuestraBiologica.cadena_custodia))
            .where(MuestraBiologica.id.in_(datos.muestra_ids))
            .with_for_update()
        ).all()
        if len(muestras) != len(set(datos.muestra_ids)):
            raise ConflictoDeNegocio("Una o más muestras no existen")
        if contenedor.estado != EstadoContenedor.DISPONIBLE:
            raise ConflictoDeNegocio("El contenedor no está disponible")
        if len(muestras) > contenedor.capacidad_muestras:
            raise ConflictoDeNegocio("Las muestras superan la capacidad del contenedor")
        if not (
            contenedor.temperatura_min_c
            <= datos.temperatura_salida_c
            <= contenedor.temperatura_max_c
        ):
            raise ConflictoDeNegocio("La temperatura está fuera del rango del contenedor")
        for muestra in muestras:
            if muestra.estado_actual != EstadoMuestra.EXTRAIDA:
                raise ConflictoDeNegocio(f"La muestra {muestra.codigo} no está extraída")
            if muestra.orden.laboratorio_id != laboratorio.id:
                raise ConflictoDeNegocio("Todas las muestras deben tener el mismo destino")
            if muestra.orden.atencion.clinica_id != datos.clinica_origen_id:
                raise ConflictoDeNegocio(
                    f"La muestra {muestra.codigo} no fue extraída en la clínica de origen"
                )
            if not (
                muestra.temperatura_min_c
                <= datos.temperatura_salida_c
                <= muestra.temperatura_max_c
            ):
                raise ConflictoDeNegocio(
                    f"Temperatura incompatible con la muestra {muestra.codigo}"
                )

        precinto = PrecintoSanitario(
            codigo=datos.codigo_precinto,
            estado=EstadoPrecinto.APLICADO,
            aplicado_en=ahora_utc(),
        )
        remito = RemitoBiologico(
            numero=_numero("REM"),
            contenedor_id=contenedor.id,
            precinto=precinto,
            clinica_origen_id=datos.clinica_origen_id,
            laboratorio_destino_id=laboratorio.id,
            fecha_emision=ahora_utc(),
            estado=EstadoRemito.BORRADOR,
        )
        self.sesion.add(remito)
        self.sesion.flush()
        self._agregar_evento_remito(
            remito,
            tipo=TipoEventoRemito.CREACION,
            actor=datos.preparado_por,
            estado_anterior=None,
            estado_nuevo=EstadoRemito.BORRADOR,
        )
        # La emisión agrega un segundo evento en la misma operación. Como la
        # sesión desactiva autoflush, persistimos CREACION antes de calcular la
        # siguiente secuencia para evitar dos eventos con secuencia 1.
        self.sesion.flush()
        maquina_remito = CicloVidaRemito(remito.estado.value)
        cambio_remito = maquina_remito.emitir()
        remito.estado = EstadoRemito(cambio_remito.estado_nuevo)
        self._agregar_evento_remito(
            remito,
            tipo=TipoEventoRemito.EMISION,
            actor=datos.preparado_por,
            estado_anterior=EstadoRemito(cambio_remito.estado_anterior),
            estado_nuevo=EstadoRemito(cambio_remito.estado_nuevo),
            observaciones=cambio_remito.detalle,
        )
        for muestra in muestras:
            cambio = CicloVidaMuestra(muestra.estado_actual.value).empaquetar()
            muestra.remito_id = remito.id
            self._agregar_evento_muestra(
                muestra,
                cambio,
                tipo=TipoEventoCustodia.EMPAQUETADO,
                actor=datos.preparado_por,
                ubicacion=remito.clinica_origen.nombre,
                temperatura_c=datos.temperatura_salida_c,
            )
        contenedor.estado = EstadoContenedor.EN_USO
        self.sesion.flush()
        return remito

    def despachar_remito(self, remito_id: UUID, datos: DespachoCrear) -> Envio:
        remito = self.sesion.scalar(
            select(RemitoBiologico)
            .options(
                selectinload(RemitoBiologico.muestras).selectinload(
                    MuestraBiologica.cadena_custodia
                )
            )
            .where(RemitoBiologico.id == remito_id)
            .with_for_update()
        )
        if remito is None:
            raise RecursoNoEncontrado("remito", remito_id)
        if remito.envio is not None:
            raise ConflictoDeNegocio("El remito ya fue despachado")
        if not (
            remito.contenedor.temperatura_min_c
            <= datos.temperatura_salida_c
            <= remito.contenedor.temperatura_max_c
        ):
            raise ConflictoDeNegocio("La temperatura está fuera del rango del contenedor")
        for muestra in remito.muestras:
            if not (
                muestra.temperatura_min_c
                <= datos.temperatura_salida_c
                <= muestra.temperatura_max_c
            ):
                raise ConflictoDeNegocio(
                    f"Temperatura de despacho incompatible con la muestra {muestra.codigo}"
                )
        cambio_remito = CicloVidaRemito(remito.estado.value).iniciar_transito()
        salida = ahora_utc()
        envio = Envio(
            remito=remito,
            codigo_seguimiento=_numero("ENV"),
            transportista=datos.transportista,
            conductor=datos.conductor,
            vehiculo=datos.vehiculo,
            fecha_salida=salida,
            estado=EstadoEnvio.EN_TRANSITO,
            temperatura_min_registrada_c=datos.temperatura_salida_c,
            temperatura_max_registrada_c=datos.temperatura_salida_c,
        )
        self.sesion.add(envio)
        self.sesion.flush()
        remito.estado = EstadoRemito(cambio_remito.estado_nuevo)
        remito.fecha_despacho = salida
        remito.contenedor.estado = EstadoContenedor.EN_TRANSITO
        self._agregar_evento_remito(
            remito,
            tipo=TipoEventoRemito.DESPACHO,
            actor=datos.conductor,
            estado_anterior=EstadoRemito(cambio_remito.estado_anterior),
            estado_nuevo=EstadoRemito(cambio_remito.estado_nuevo),
            observaciones=cambio_remito.detalle,
        )
        for muestra in remito.muestras:
            cambio = CicloVidaMuestra(muestra.estado_actual.value).iniciar_transito()
            self._agregar_evento_muestra(
                muestra,
                cambio,
                tipo=TipoEventoCustodia.DESPACHO,
                actor=datos.conductor,
                ubicacion=remito.clinica_origen.nombre,
                envio_id=envio.id,
                temperatura_c=datos.temperatura_salida_c,
            )
            muestra.orden.estado = EstadoOrden.DESPACHADA
        self.sesion.flush()
        return envio

    def registrar_transferencia_custodia(
        self, envio_id: UUID, datos: EventoCustodiaCrear
    ) -> list[EventoCustodia]:
        """Registra un traspaso sin alterar el estado EN_TRANSITO de las muestras."""

        envio = self.sesion.scalar(
            select(Envio)
            .options(
                selectinload(Envio.remito)
                .selectinload(RemitoBiologico.muestras)
                .selectinload(MuestraBiologica.cadena_custodia)
            )
            .where(Envio.id == envio_id)
            .with_for_update()
        )
        if envio is None:
            raise RecursoNoEncontrado("envío", envio_id)
        if (
            envio.estado != EstadoEnvio.EN_TRANSITO
            or envio.remito.estado != EstadoRemito.EN_TRANSITO
        ):
            raise ConflictoDeNegocio("Sólo se registran transferencias en envíos en tránsito")

        if datos.temperatura_c is not None:
            envio.temperatura_min_registrada_c = min(
                envio.temperatura_min_registrada_c or datos.temperatura_c,
                datos.temperatura_c,
            )
            envio.temperatura_max_registrada_c = max(
                envio.temperatura_max_registrada_c or datos.temperatura_c,
                datos.temperatura_c,
            )

        instante = ahora_utc()
        eventos: list[EventoCustodia] = []
        for muestra in envio.remito.muestras:
            if muestra.estado_actual != EstadoMuestra.EN_TRANSITO:
                raise ConflictoDeNegocio(
                    f"La muestra {muestra.codigo} no se encuentra en tránsito"
                )
            secuencia = self.sesion.scalar(
                select(func.coalesce(func.max(EventoCustodia.secuencia), 0)).where(
                    EventoCustodia.muestra_id == muestra.id
                )
            )
            evento = EventoCustodia(
                cadena_custodia_id=muestra.cadena_custodia.id,
                muestra_id=muestra.id,
                envio_id=envio.id,
                secuencia=int(secuencia or 0) + 1,
                tipo_evento=TipoEventoCustodia.TRANSFERENCIA,
                estado_anterior=EstadoMuestra.EN_TRANSITO,
                estado_nuevo=EstadoMuestra.EN_TRANSITO,
                ocurrido_en=instante,
                actor=datos.actor,
                ubicacion=datos.ubicacion,
                temperatura_c=datos.temperatura_c,
                observaciones=datos.observaciones,
            )
            self.sesion.add(evento)
            eventos.append(evento)
        self.sesion.flush()
        return eventos

    def recibir_remito(
        self, remito_id: UUID, datos: RecepcionLaboratorioCrear
    ) -> RecepcionLaboratorio:
        remito = self.sesion.scalar(
            select(RemitoBiologico)
            .options(
                selectinload(RemitoBiologico.muestras).selectinload(
                    MuestraBiologica.cadena_custodia
                ),
                selectinload(RemitoBiologico.envio),
            )
            .where(RemitoBiologico.id == remito_id)
            .with_for_update()
        )
        if remito is None:
            raise RecursoNoEncontrado("remito", remito_id)
        if remito.envio is None or remito.envio.estado != EstadoEnvio.EN_TRANSITO:
            raise ConflictoDeNegocio("El remito no tiene un envío en tránsito")
        if remito.recepcion is not None:
            raise ConflictoDeNegocio("El remito ya fue recibido")

        temperatura_recepcion_valida = all(
            muestra.temperatura_min_c
            <= datos.temperatura_recepcion_c
            <= muestra.temperatura_max_c
            for muestra in remito.muestras
        )
        temperatura_transporte_valida = all(
            (
                remito.envio.temperatura_min_registrada_c is None
                or muestra.temperatura_min_c
                <= remito.envio.temperatura_min_registrada_c
            )
            and (
                remito.envio.temperatura_max_registrada_c is None
                or remito.envio.temperatura_max_registrada_c
                <= muestra.temperatura_max_c
            )
            for muestra in remito.muestras
        )
        temperatura_valida = (
            temperatura_recepcion_valida and temperatura_transporte_valida
        )
        viable = datos.precinto_intacto and temperatura_valida
        motivo = None
        if not datos.precinto_intacto:
            motivo = "Precinto sanitario roto al llegar al laboratorio"
        elif not temperatura_valida:
            motivo = "Temperatura fuera del rango de conservación durante el transporte"

        estado_precinto = EstadoPrecinto.INTACTO if datos.precinto_intacto else EstadoPrecinto.ROTO
        recepcion = RecepcionLaboratorio(
            remito_id=remito.id,
            envio_id=remito.envio.id,
            laboratorio_id=remito.laboratorio_destino_id,
            recibido_en=ahora_utc(),
            receptor_nombre=datos.receptor,
            estado_precinto=estado_precinto,
            temperatura_recepcion_c=datos.temperatura_recepcion_c,
            muestra_viable=viable,
            observaciones=datos.observaciones or motivo,
        )
        self.sesion.add(recepcion)
        cambio_remito = CicloVidaRemito(remito.estado.value).registrar_recepcion(
            aceptado=viable
        )
        remito.estado = EstadoRemito(cambio_remito.estado_nuevo)
        remito.precinto.estado = estado_precinto
        remito.precinto.verificado_en = ahora_utc()
        remito.envio.estado = EstadoEnvio.ENTREGADO if viable else EstadoEnvio.CON_INCIDENCIA
        remito.envio.fecha_entrega = ahora_utc()
        remito.envio.temperatura_min_registrada_c = min(
            remito.envio.temperatura_min_registrada_c or datos.temperatura_recepcion_c,
            datos.temperatura_recepcion_c,
        )
        remito.envio.temperatura_max_registrada_c = max(
            remito.envio.temperatura_max_registrada_c or datos.temperatura_recepcion_c,
            datos.temperatura_recepcion_c,
        )
        remito.contenedor.estado = (
            EstadoContenedor.DISPONIBLE if viable else EstadoContenedor.MANTENIMIENTO
        )
        self._agregar_evento_remito(
            remito,
            tipo=TipoEventoRemito.RECEPCION if viable else TipoEventoRemito.RECHAZO,
            actor=datos.receptor,
            estado_anterior=EstadoRemito(cambio_remito.estado_anterior),
            estado_nuevo=EstadoRemito(cambio_remito.estado_nuevo),
            observaciones=motivo or cambio_remito.detalle,
        )
        for muestra in remito.muestras:
            cambio = CicloVidaMuestra(muestra.estado_actual.value).registrar_recepcion(
                precinto_intacto=viable
            )
            muestra.fecha_recepcion = ahora_utc()
            muestra.motivo_rechazo = motivo
            if viable:
                muestra.orden.estado = EstadoOrden.RECIBIDA
            self._agregar_evento_muestra(
                muestra,
                cambio,
                tipo=TipoEventoCustodia.RECEPCION if viable else TipoEventoCustodia.RECHAZO,
                actor=datos.receptor,
                ubicacion=remito.laboratorio_destino.nombre,
                envio_id=remito.envio.id,
                temperatura_c=datos.temperatura_recepcion_c,
                observaciones=motivo,
            )
            if not viable:
                muestra.cadena_custodia.cerrada_en = ahora_utc()
                for solicitud in muestra.solicitudes_analisis:
                    if solicitud.estado != EstadoSolicitudAnalisis.COMPLETADA:
                        solicitud.muestra_id = None
                        solicitud.estado = EstadoSolicitudAnalisis.PENDIENTE
                muestra.orden.estado = EstadoOrden.REQUIERE_NUEVA_MUESTRA
        self.sesion.flush()
        return recepcion

    def registrar_resultado(self, datos: ResultadoCrear) -> ResultadoAnalisis:
        solicitud = self.sesion.scalar(
            select(OrdenAnalisis)
            .options(
                selectinload(OrdenAnalisis.muestra).selectinload(
                    MuestraBiologica.cadena_custodia
                )
            )
            .where(OrdenAnalisis.id == datos.orden_analisis_id)
            .with_for_update()
        )
        if solicitud is None:
            raise RecursoNoEncontrado("análisis solicitado", datos.orden_analisis_id)
        # Serializa los cierres de estudios que comparten muestra u orden. Así,
        # dos resultados simultáneos no pueden dejar ambos agregados sin cerrar.
        self.sesion.scalar(
            select(OrdenDerivacion.id)
            .where(OrdenDerivacion.id == solicitud.orden_id)
            .with_for_update()
        )
        if solicitud.muestra_id is not None:
            self.sesion.scalar(
                select(MuestraBiologica.id)
                .where(MuestraBiologica.id == solicitud.muestra_id)
                .with_for_update()
            )
        if solicitud.resultado is not None:
            raise ConflictoDeNegocio("El análisis ya tiene un resultado")
        if solicitud.muestra is None or solicitud.muestra.estado_actual not in {
            EstadoMuestra.RECIBIDA,
            EstadoMuestra.ANALIZADA,
        }:
            raise ConflictoDeNegocio("La muestra no fue recibida o no es viable")
        resultado = ResultadoAnalisis(
            orden_analisis_id=solicitud.id,
            fecha_resultado=ahora_utc(),
            valores=datos.valores,
            conclusion=datos.conclusion,
            observaciones=datos.observaciones,
            validado_por=datos.validado_por,
            firmado_en=ahora_utc(),
        )
        self.sesion.add(resultado)
        solicitud.estado = EstadoSolicitudAnalisis.COMPLETADA
        self.sesion.flush()

        pendientes_muestra = self.sesion.scalar(
            select(func.count(OrdenAnalisis.id)).where(
                OrdenAnalisis.muestra_id == solicitud.muestra_id,
                OrdenAnalisis.estado != EstadoSolicitudAnalisis.COMPLETADA,
            )
        )
        if not pendientes_muestra and solicitud.muestra.estado_actual == EstadoMuestra.RECIBIDA:
            cambio = CicloVidaMuestra(solicitud.muestra.estado_actual.value).registrar_analisis()
            solicitud.muestra.fecha_analisis = ahora_utc()
            solicitud.muestra.cadena_custodia.cerrada_en = ahora_utc()
            self._agregar_evento_muestra(
                solicitud.muestra,
                cambio,
                tipo=TipoEventoCustodia.ANALISIS,
                actor=datos.validado_por,
                ubicacion=solicitud.orden.laboratorio.nombre,
            )
        pendientes_orden = self.sesion.scalar(
            select(func.count(OrdenAnalisis.id)).where(
                OrdenAnalisis.orden_id == solicitud.orden_id,
                OrdenAnalisis.estado != EstadoSolicitudAnalisis.COMPLETADA,
            )
        )
        if not pendientes_orden:
            solicitud.orden.estado = EstadoOrden.COMPLETADA
        self.sesion.flush()
        return resultado

    # ------------------------------------------------------------------
    # Facturación
    # ------------------------------------------------------------------
    def emitir_factura(self, datos: FacturaCrear) -> Factura:
        self._obtener(Cliente, datos.cliente_id, "cliente")
        self._obtener(ClinicaVeterinaria, datos.clinica_id, "clínica")
        atencion: AtencionVeterinaria | None = None
        orden: OrdenDerivacion | None = None
        if datos.atencion_id is not None:
            atencion = self._obtener(AtencionVeterinaria, datos.atencion_id, "atención")
            if atencion.historia_clinica.mascota.cliente_id != datos.cliente_id:
                raise ConflictoDeNegocio("La atención no pertenece al cliente facturado")
            if atencion.clinica_id != datos.clinica_id:
                raise ConflictoDeNegocio("La atención no pertenece a la clínica facturada")
        if datos.orden_derivacion_id is not None:
            orden = self._obtener(
                OrdenDerivacion, datos.orden_derivacion_id, "orden de derivación"
            )
            if orden.atencion.historia_clinica.mascota.cliente_id != datos.cliente_id:
                raise ConflictoDeNegocio("La orden no pertenece al cliente facturado")
            if orden.atencion.clinica_id != datos.clinica_id:
                raise ConflictoDeNegocio("La orden no pertenece a la clínica facturada")
            if atencion is not None and orden.atencion_id != atencion.id:
                raise ConflictoDeNegocio("La orden no pertenece a la atención facturada")

        componentes_normalizados: list[
            tuple[object, Decimal, Decimal, Decimal, UUID | None]
        ] = []
        for item in datos.componentes:
            if item.tipo == "atencion" and atencion is None:
                raise ConflictoDeNegocio(
                    "Un componente de atención requiere indicar la atención facturada"
                )
            solicitud_id = item.orden_analisis_id
            if solicitud_id is not None:
                solicitud = self._obtener(
                    OrdenAnalisis, solicitud_id, "análisis solicitado"
                )
                if item.tipo != "laboratorio":
                    raise ConflictoDeNegocio(
                        "Sólo un componente de laboratorio puede vincular un análisis"
                    )
                if orden is None or solicitud.orden_id != orden.id:
                    raise ConflictoDeNegocio(
                        "El análisis facturado no pertenece a la orden indicada"
                    )
            elif (
                item.tipo == "laboratorio"
                and orden is not None
                and len(orden.solicitudes_analisis) == 1
            ):
                solicitud_id = orden.solicitudes_analisis[0].id

            cantidad = item.cantidad.quantize(CENTAVO, rounding=ROUND_HALF_UP)
            precio = item.precio_unitario.quantize(CENTAVO, rounding=ROUND_HALF_UP)
            subtotal_item = (cantidad * precio).quantize(
                CENTAVO, rounding=ROUND_HALF_UP
            )
            componentes_normalizados.append(
                (item, cantidad, precio, subtotal_item, solicitud_id)
            )

        subtotales = [componente[3] for componente in componentes_normalizados]
        subtotal = sum(subtotales, Decimal("0"))
        factura = Factura(
            numero=_numero("FAC"),
            cliente_id=datos.cliente_id,
            clinica_id=datos.clinica_id,
            atencion_id=datos.atencion_id,
            orden_derivacion_id=datos.orden_derivacion_id,
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() + timedelta(days=15),
            estado=EstadoFactura.EMITIDA,
            subtotal=subtotal,
            descuento=Decimal("0"),
            total=subtotal,
            emitida_en=ahora_utc(),
        )
        for (
            item,
            cantidad,
            precio,
            subtotal_item,
            solicitud_id,
        ) in componentes_normalizados:
            factura.componentes.append(
                ComponenteAtencion(
                    atencion_id=datos.atencion_id if item.tipo == "atencion" else None,
                    orden_analisis_id=solicitud_id,
                    tipo=TipoComponente(item.tipo),
                    descripcion=item.descripcion,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal_item,
                )
            )
        self.sesion.add(factura)
        self.sesion.flush()
        return factura
