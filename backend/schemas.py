from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

TipoMuestraEntrada = Literal[
    "sangre", "orina", "materia_fecal", "tejido", "hisopado", "otro"
]


class EsquemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class ClienteCrear(EsquemaBase):
    nombre: str = Field(min_length=2, max_length=120)
    apellido: str = Field(min_length=2, max_length=120)
    tipo_documento: Literal["dni", "pasaporte", "cuit"] = "dni"
    numero_documento: str = Field(min_length=5, max_length=30)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=40)
    direccion: str | None = Field(default=None, max_length=250)


class ClienteActualizar(EsquemaBase):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    apellido: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, min_length=6, max_length=40)
    direccion: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def impedir_nulos_en_campos_obligatorios(self) -> "ClienteActualizar":
        obligatorios = {"nombre", "apellido", "email", "telefono"}
        nulos = [
            campo
            for campo in obligatorios & self.model_fields_set
            if getattr(self, campo) is None
        ]
        if nulos:
            raise ValueError(f"No se admite null en: {', '.join(sorted(nulos))}")
        return self


class MascotaCrear(EsquemaBase):
    cliente_id: UUID
    nombre: str = Field(min_length=1, max_length=100)
    especie: str = Field(min_length=2, max_length=60)
    raza: str | None = Field(default=None, max_length=80)
    sexo: Literal["macho", "hembra", "no_especificado"] = "no_especificado"
    fecha_nacimiento: date | None = None
    color: str | None = Field(default=None, max_length=60)
    microchip: str | None = Field(default=None, max_length=80)
    peso_kg: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)

    @model_validator(mode="after")
    def impedir_nacimiento_futuro(self) -> "MascotaCrear":
        if self.fecha_nacimiento is not None and self.fecha_nacimiento > date.today():
            raise ValueError("La fecha de nacimiento no puede estar en el futuro")
        return self


class MascotaActualizar(EsquemaBase):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    especie: str | None = Field(default=None, min_length=2, max_length=60)
    raza: str | None = Field(default=None, max_length=80)
    sexo: Literal["macho", "hembra", "no_especificado"] | None = None
    fecha_nacimiento: date | None = None
    color: str | None = Field(default=None, max_length=60)
    microchip: str | None = Field(default=None, max_length=80)
    peso_kg: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    activo: bool | None = None

    @model_validator(mode="after")
    def validar_actualizacion(self) -> "MascotaActualizar":
        no_nulos = {"nombre", "especie", "sexo", "activo"}
        nulos = [
            campo for campo in no_nulos & self.model_fields_set if getattr(self, campo) is None
        ]
        if nulos:
            raise ValueError(f"No se admite null en: {', '.join(sorted(nulos))}")
        if self.fecha_nacimiento is not None and self.fecha_nacimiento > date.today():
            raise ValueError("La fecha de nacimiento no puede estar en el futuro")
        return self


class HistoriaClinicaActualizar(EsquemaBase):
    antecedentes: str | None = None
    alergias: str | None = None
    observaciones: str | None = None


class ClinicaCrear(EsquemaBase):
    nombre: str = Field(min_length=2, max_length=160)
    codigo: str = Field(min_length=2, max_length=30)
    cuit: str = Field(min_length=8, max_length=20)
    direccion: str = Field(min_length=5, max_length=250)
    telefono: str = Field(min_length=6, max_length=40)
    email: EmailStr


class LaboratorioCrear(EsquemaBase):
    nombre: str = Field(min_length=2, max_length=160)
    codigo: str = Field(min_length=2, max_length=30)
    direccion: str = Field(min_length=5, max_length=250)
    telefono: str = Field(min_length=6, max_length=40)
    email: EmailStr


class ProfesionalCrear(EsquemaBase):
    clinica_id: UUID
    matricula: str = Field(min_length=3, max_length=50)
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    especialidad: str | None = Field(default=None, max_length=100)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=40)

class TurnoCrear(EsquemaBase):
    clinica_id: UUID
    profesional_id: UUID
    mascota_id: UUID
    tipo: Literal["consulta", "control", "urgencia"] = "consulta"
    inicio: datetime
    fin: datetime
    motivo: str = Field(min_length=2, max_length=300)
    observaciones: str | None = None

    @model_validator(mode="after")
    def validar_intervalo(self) -> "TurnoCrear":
        if self.fin <= self.inicio:
            raise ValueError("El fin del turno debe ser posterior al inicio")
        return self


class AtencionCrear(EsquemaBase):
    mascota_id: UUID
    clinica_id: UUID
    profesional_id: UUID
    turno_id: UUID | None = None
    tipo: Literal["consulta", "control", "urgencia"]
    motivo: str = Field(min_length=2, max_length=500)
    diagnostico: str | None = None
    tratamiento: str | None = None
    peso_kg: Decimal | None = Field(default=None, gt=0)
    temperatura_c: Decimal | None = Field(default=None, ge=24, le=45)
    observaciones: str | None = None


class VacunaCrear(EsquemaBase):
    nombre: str = Field(min_length=2, max_length=120)
    laboratorio_fabricante: str = Field(min_length=2, max_length=160)
    especie_objetivo: str = Field(min_length=2, max_length=60)
    dosis_ml: Decimal = Field(gt=0)
    obligatoria: bool = True
    edad_minima_dias: int = Field(default=0, ge=0)
    intervalo_refuerzo_dias: int | None = Field(default=None, gt=0)


class AplicacionVacunaCrear(EsquemaBase):
    mascota_id: UUID
    vacuna_id: UUID
    profesional_id: UUID
    atencion_id: UUID
    aplicada_en: datetime
    dosis_ml: Decimal | None = Field(default=None, gt=0)
    lote: str = Field(min_length=1, max_length=80)
    fecha_vencimiento_lote: date | None = None
    proxima_dosis: date | None = None
    observaciones: str | None = None

    @model_validator(mode="after")
    def validar_fechas(self) -> "AplicacionVacunaCrear":
        fecha_aplicacion = self.aplicada_en.date()
        if (
            self.fecha_vencimiento_lote is not None
            and self.fecha_vencimiento_lote < fecha_aplicacion
        ):
            raise ValueError("El lote estaba vencido al aplicar la vacuna")
        if self.proxima_dosis is not None and self.proxima_dosis <= fecha_aplicacion:
            raise ValueError("La próxima dosis debe ser posterior a la aplicación")
        return self


class AnalisisCrear(EsquemaBase):
    laboratorio_id: UUID
    codigo: str = Field(min_length=2, max_length=30)
    nombre: str = Field(min_length=2, max_length=160)
    descripcion: str | None = None
    tipo_muestra: TipoMuestraEntrada
    precio: Decimal = Field(ge=0)
    tiempo_estimado_horas: int = Field(gt=0)
    requiere_ayuno: bool = False


class OrdenDerivacionCrear(EsquemaBase):
    atencion_id: UUID
    laboratorio_id: UUID
    profesional_solicitante_id: UUID
    analisis_ids: list[UUID] = Field(min_length=1)
    prioridad: Literal["normal", "urgente"] = "normal"
    indicaciones: str | None = None


class MuestraExtraer(EsquemaBase):
    orden_id: UUID
    tipo: TipoMuestraEntrada
    volumen_ml: Decimal = Field(gt=0)
    temperatura_min_c: Decimal
    temperatura_max_c: Decimal
    sitio_extraccion: str | None = Field(default=None, max_length=160)
    extraida_por: str = Field(min_length=2, max_length=160)
    observaciones: str | None = None

    @model_validator(mode="after")
    def validar_rango_temperatura(self) -> "MuestraExtraer":
        if self.temperatura_max_c < self.temperatura_min_c:
            raise ValueError("La temperatura máxima no puede ser menor a la mínima")
        return self


class ContenedorCrear(EsquemaBase):
    codigo: str = Field(min_length=2, max_length=50)
    descripcion: str | None = Field(default=None, max_length=200)
    temperatura_min_c: Decimal
    temperatura_max_c: Decimal
    capacidad_muestras: int = Field(gt=0)

    @model_validator(mode="after")
    def validar_temperaturas(self) -> "ContenedorCrear":
        if self.temperatura_max_c <= self.temperatura_min_c:
            raise ValueError("La temperatura máxima debe superar a la mínima")
        return self


class EmpaquetadoCrear(EsquemaBase):
    muestra_ids: list[UUID] = Field(min_length=1)
    contenedor_id: UUID
    codigo_precinto: str = Field(min_length=4, max_length=80)
    clinica_origen_id: UUID
    laboratorio_destino_id: UUID
    temperatura_salida_c: Decimal
    preparado_por: str = Field(min_length=2, max_length=160)


class DespachoCrear(EsquemaBase):
    transportista: str = Field(min_length=2, max_length=160)
    conductor: str = Field(min_length=2, max_length=160)
    vehiculo: str = Field(min_length=2, max_length=100)
    temperatura_salida_c: Decimal


class EventoCustodiaCrear(EsquemaBase):
    tipo_evento: Literal["transferencia"] = "transferencia"
    actor: str = Field(min_length=2, max_length=160)
    ubicacion: str = Field(min_length=2, max_length=250)
    temperatura_c: Decimal | None = None
    observaciones: str | None = None


class RecepcionLaboratorioCrear(EsquemaBase):
    precinto_intacto: bool
    receptor: str = Field(min_length=2, max_length=160)
    temperatura_recepcion_c: Decimal
    observaciones: str | None = None


class ResultadoCrear(EsquemaBase):
    orden_analisis_id: UUID
    validado_por: str = Field(min_length=2, max_length=160)
    valores: dict[str, Any]
    conclusion: str = Field(min_length=2)
    observaciones: str | None = None


class ComponenteFacturaCrear(EsquemaBase):
    descripcion: str = Field(min_length=2, max_length=250)
    tipo: Literal["atencion", "laboratorio", "vacuna", "insumo", "otro"]
    cantidad: Decimal = Field(
        default=Decimal("1"), gt=0, max_digits=10, decimal_places=2
    )
    precio_unitario: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    orden_analisis_id: UUID | None = None


class FacturaCrear(EsquemaBase):
    cliente_id: UUID
    clinica_id: UUID
    atencion_id: UUID | None = None
    orden_derivacion_id: UUID | None = None
    componentes: list[ComponenteFacturaCrear] = Field(min_length=1)


class RangoReporte(EsquemaBase):
    desde: date
    hasta: date
    clinica_id: UUID | None = None

    @model_validator(mode="after")
    def validar_rango(self) -> "RangoReporte":
        if self.hasta < self.desde:
            raise ValueError("La fecha hasta no puede ser anterior a desde")
        return self
