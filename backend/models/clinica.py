from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import IdentificadorMixin, MarcaTemporalMixin
from backend.models.enums import EstadoTurno, SexoMascota, TipoAtencion, TipoDocumento, enum_sql

if TYPE_CHECKING:
    from backend.models.facturacion import Factura
    from backend.models.laboratorio import OrdenDerivacion
    from backend.models.vacunacion import AplicacionVacuna


class Cliente(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("tipo_documento", "numero_documento"),
        CheckConstraint("length(trim(nombre)) > 0", name="cliente_nombre_no_vacio"),
        CheckConstraint("length(trim(apellido)) > 0", name="cliente_apellido_no_vacio"),
    )

    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    tipo_documento: Mapped[TipoDocumento] = mapped_column(
        enum_sql(TipoDocumento, "tipo_documento")
    )
    numero_documento: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    telefono: Mapped[str] = mapped_column(String(40))
    direccion: Mapped[str | None] = mapped_column(String(250))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    mascotas: Mapped[list["Mascota"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )
    facturas: Mapped[list["Factura"]] = relationship(back_populates="cliente")


class Mascota(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "mascotas"
    __table_args__ = (
        CheckConstraint("length(trim(nombre)) > 0", name="mascota_nombre_no_vacio"),
        CheckConstraint("peso_kg IS NULL OR peso_kg > 0", name="mascota_peso_positivo"),
        Index("ix_mascotas_cliente_nombre", "cliente_id", "nombre"),
    )

    cliente_id: Mapped[UUID] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(100))
    especie: Mapped[str] = mapped_column(String(80), index=True)
    raza: Mapped[str | None] = mapped_column(String(100))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    sexo: Mapped[SexoMascota] = mapped_column(
        enum_sql(SexoMascota, "sexo_mascota"), default=SexoMascota.NO_ESPECIFICADO
    )
    peso_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    microchip: Mapped[str | None] = mapped_column(String(80), unique=True)
    color: Mapped[str | None] = mapped_column(String(80))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    cliente: Mapped[Cliente] = relationship(back_populates="mascotas")
    historia_clinica: Mapped["HistoriaClinica"] = relationship(
        back_populates="mascota", cascade="all, delete-orphan", uselist=False
    )
    turnos: Mapped[list["Turno"]] = relationship(back_populates="mascota")
    aplicaciones_vacunas: Mapped[list["AplicacionVacuna"]] = relationship(
        back_populates="mascota"
    )


class HistoriaClinica(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "historias_clinicas"

    mascota_id: Mapped[UUID] = mapped_column(
        ForeignKey("mascotas.id", ondelete="RESTRICT"), unique=True
    )
    fecha_apertura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now
    )
    antecedentes: Mapped[str | None] = mapped_column(Text)
    alergias: Mapped[str | None] = mapped_column(Text)
    observaciones: Mapped[str | None] = mapped_column(Text)

    mascota: Mapped[Mascota] = relationship(back_populates="historia_clinica")
    atenciones: Mapped[list["AtencionVeterinaria"]] = relationship(
        back_populates="historia_clinica"
    )


class ClinicaVeterinaria(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "clinicas_veterinarias"
    __table_args__ = (
        CheckConstraint("length(trim(nombre)) > 0", name="clinica_nombre_no_vacio"),
    )

    nombre: Mapped[str] = mapped_column(String(160))
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    cuit: Mapped[str] = mapped_column(String(20), unique=True)
    direccion: Mapped[str] = mapped_column(String(250))
    telefono: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(254))
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    profesionales: Mapped[list["ProfesionalVeterinario"]] = relationship(
        back_populates="clinica"
    )
    turnos: Mapped[list["Turno"]] = relationship(back_populates="clinica")
    atenciones: Mapped[list["AtencionVeterinaria"]] = relationship(back_populates="clinica")
    facturas: Mapped[list["Factura"]] = relationship(back_populates="clinica")


class ProfesionalVeterinario(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "profesionales_veterinarios"
    __table_args__ = (
        CheckConstraint("length(trim(matricula)) > 0", name="profesional_matricula_no_vacia"),
    )

    clinica_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinicas_veterinarias.id", ondelete="RESTRICT"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    matricula: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    telefono: Mapped[str] = mapped_column(String(40))
    especialidad: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    clinica: Mapped[ClinicaVeterinaria] = relationship(back_populates="profesionales")
    turnos: Mapped[list["Turno"]] = relationship(back_populates="profesional")
    atenciones: Mapped[list["AtencionVeterinaria"]] = relationship(
        back_populates="profesional"
    )
    ordenes_solicitadas: Mapped[list["OrdenDerivacion"]] = relationship(
        back_populates="profesional_solicitante"
    )
    aplicaciones_vacunas: Mapped[list["AplicacionVacuna"]] = relationship(
        back_populates="profesional"
    )


class Turno(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "turnos"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="turno_intervalo_valido"),
        Index("ix_turnos_profesional_inicio", "profesional_id", "inicio"),
        Index("ix_turnos_clinica_inicio", "clinica_id", "inicio"),
    )

    clinica_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinicas_veterinarias.id", ondelete="RESTRICT")
    )
    profesional_id: Mapped[UUID] = mapped_column(
        ForeignKey("profesionales_veterinarios.id", ondelete="RESTRICT")
    )
    mascota_id: Mapped[UUID] = mapped_column(
        ForeignKey("mascotas.id", ondelete="RESTRICT"), index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[EstadoTurno] = mapped_column(
        enum_sql(EstadoTurno, "estado_turno"), default=EstadoTurno.PROGRAMADO, index=True
    )
    motivo: Mapped[str] = mapped_column(String(300))
    observaciones: Mapped[str | None] = mapped_column(Text)

    clinica: Mapped[ClinicaVeterinaria] = relationship(back_populates="turnos")
    profesional: Mapped[ProfesionalVeterinario] = relationship(back_populates="turnos")
    mascota: Mapped[Mascota] = relationship(back_populates="turnos")
    atencion: Mapped["AtencionVeterinaria | None"] = relationship(
        back_populates="turno", uselist=False
    )


class AtencionVeterinaria(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "atenciones_veterinarias"
    __table_args__ = (
        CheckConstraint("peso_kg IS NULL OR peso_kg > 0", name="atencion_peso_positivo"),
        Index("ix_atenciones_clinica_fecha", "clinica_id", "fecha"),
        Index("ix_atenciones_historia_fecha", "historia_clinica_id", "fecha"),
    )

    historia_clinica_id: Mapped[UUID] = mapped_column(
        ForeignKey("historias_clinicas.id", ondelete="RESTRICT")
    )
    turno_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("turnos.id", ondelete="RESTRICT"), unique=True
    )
    clinica_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinicas_veterinarias.id", ondelete="RESTRICT")
    )
    profesional_id: Mapped[UUID] = mapped_column(
        ForeignKey("profesionales_veterinarios.id", ondelete="RESTRICT")
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    tipo: Mapped[TipoAtencion] = mapped_column(enum_sql(TipoAtencion, "tipo_atencion"))
    motivo: Mapped[str] = mapped_column(String(300))
    diagnostico: Mapped[str | None] = mapped_column(Text)
    tratamiento: Mapped[str | None] = mapped_column(Text)
    peso_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperatura_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    observaciones: Mapped[str | None] = mapped_column(Text)
    esquema_vacunacion_al_dia: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    vacunas_pendientes: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)

    historia_clinica: Mapped[HistoriaClinica] = relationship(back_populates="atenciones")
    turno: Mapped[Turno | None] = relationship(back_populates="atencion")
    clinica: Mapped[ClinicaVeterinaria] = relationship(back_populates="atenciones")
    profesional: Mapped[ProfesionalVeterinario] = relationship(back_populates="atenciones")
    ordenes_derivacion: Mapped[list["OrdenDerivacion"]] = relationship(
        back_populates="atencion"
    )
    facturas: Mapped[list["Factura"]] = relationship(back_populates="atencion")
    aplicaciones_vacunas: Mapped[list["AplicacionVacuna"]] = relationship(
        back_populates="atencion"
    )
