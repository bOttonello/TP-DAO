from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import IdentificadorMixin, MarcaTemporalMixin
from backend.models.enums import (
    EstadoMuestra,
    EstadoOrden,
    EstadoSolicitudAnalisis,
    PrioridadOrden,
    TipoMuestra,
    enum_sql,
)

if TYPE_CHECKING:
    from backend.models.clinica import AtencionVeterinaria, ProfesionalVeterinario
    from backend.models.facturacion import Factura
    from backend.models.transporte import (
        CadenaCustodia,
        EventoCustodia,
        RecepcionLaboratorio,
        RemitoBiologico,
    )


class LaboratorioCentral(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "laboratorios_centrales"
    __table_args__ = (
        CheckConstraint("clave_singleton = 1", name="laboratorio_unico_por_red"),
    )

    nombre: Mapped[str] = mapped_column(String(160))
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    direccion: Mapped[str] = mapped_column(String(250))
    telefono: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(254))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    clave_singleton: Mapped[int] = mapped_column(
        Integer, unique=True, default=1, server_default="1"
    )

    analisis: Mapped[list["Analisis"]] = relationship(back_populates="laboratorio")
    ordenes: Mapped[list["OrdenDerivacion"]] = relationship(back_populates="laboratorio")
    recepciones: Mapped[list["RecepcionLaboratorio"]] = relationship(
        back_populates="laboratorio"
    )


class Analisis(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "analisis"
    __table_args__ = (
        UniqueConstraint("laboratorio_id", "codigo"),
        CheckConstraint("precio >= 0", name="analisis_precio_no_negativo"),
        CheckConstraint(
            "tiempo_estimado_horas > 0", name="analisis_tiempo_estimado_positivo"
        ),
    )

    laboratorio_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratorios_centrales.id", ondelete="RESTRICT")
    )
    codigo: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(160))
    descripcion: Mapped[str | None] = mapped_column(Text)
    tipo_muestra: Mapped[TipoMuestra] = mapped_column(
        enum_sql(TipoMuestra, "tipo_muestra_analisis")
    )
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tiempo_estimado_horas: Mapped[int]
    requiere_ayuno: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    laboratorio: Mapped[LaboratorioCentral] = relationship(back_populates="analisis")
    solicitudes: Mapped[list["OrdenAnalisis"]] = relationship(back_populates="analisis")


class OrdenDerivacion(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "ordenes_derivacion"
    __table_args__ = (
        Index("ix_ordenes_derivacion_estado_emision", "estado", "fecha_emision"),
    )

    numero: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    atencion_id: Mapped[UUID] = mapped_column(
        ForeignKey("atenciones_veterinarias.id", ondelete="RESTRICT"), index=True
    )
    laboratorio_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratorios_centrales.id", ondelete="RESTRICT")
    )
    profesional_solicitante_id: Mapped[UUID] = mapped_column(
        ForeignKey("profesionales_veterinarios.id", ondelete="RESTRICT")
    )
    fecha_emision: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[EstadoOrden] = mapped_column(
        enum_sql(EstadoOrden, "estado_orden"), default=EstadoOrden.EMITIDA, index=True
    )
    prioridad: Mapped[PrioridadOrden] = mapped_column(
        enum_sql(PrioridadOrden, "prioridad_orden"),
        default=PrioridadOrden.NORMAL,
        server_default=PrioridadOrden.NORMAL.value,
        index=True,
    )
    diagnostico_presuntivo: Mapped[str | None] = mapped_column(Text)
    indicaciones: Mapped[str | None] = mapped_column(Text)

    atencion: Mapped["AtencionVeterinaria"] = relationship(
        back_populates="ordenes_derivacion"
    )
    laboratorio: Mapped[LaboratorioCentral] = relationship(back_populates="ordenes")
    profesional_solicitante: Mapped["ProfesionalVeterinario"] = relationship(
        back_populates="ordenes_solicitadas"
    )
    solicitudes_analisis: Mapped[list["OrdenAnalisis"]] = relationship(
        back_populates="orden", cascade="all, delete-orphan"
    )
    muestras: Mapped[list["MuestraBiologica"]] = relationship(back_populates="orden")
    facturas: Mapped[list["Factura"]] = relationship(back_populates="orden_derivacion")


class OrdenAnalisis(IdentificadorMixin, MarcaTemporalMixin, Base):
    """Estudio concreto solicitado dentro de una orden de derivación."""

    __tablename__ = "ordenes_analisis"
    __table_args__ = (
        UniqueConstraint("orden_id", "analisis_id"),
    )

    orden_id: Mapped[UUID] = mapped_column(
        ForeignKey("ordenes_derivacion.id", ondelete="RESTRICT"), index=True
    )
    analisis_id: Mapped[UUID] = mapped_column(ForeignKey("analisis.id", ondelete="RESTRICT"))
    muestra_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("muestras_biologicas.id", ondelete="RESTRICT"), index=True
    )
    estado: Mapped[EstadoSolicitudAnalisis] = mapped_column(
        enum_sql(EstadoSolicitudAnalisis, "estado_solicitud_analisis"),
        default=EstadoSolicitudAnalisis.PENDIENTE,
    )

    orden: Mapped[OrdenDerivacion] = relationship(back_populates="solicitudes_analisis")
    analisis: Mapped[Analisis] = relationship(back_populates="solicitudes")
    muestra: Mapped["MuestraBiologica | None"] = relationship(
        back_populates="solicitudes_analisis"
    )
    resultado: Mapped["ResultadoAnalisis | None"] = relationship(
        back_populates="orden_analisis", uselist=False
    )


class MuestraBiologica(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "muestras_biologicas"
    __table_args__ = (
        CheckConstraint("volumen_ml > 0", name="muestra_volumen_positivo"),
        CheckConstraint(
            "temperatura_min_c <= temperatura_max_c", name="muestra_rango_temperatura_valido"
        ),
        CheckConstraint(
            "estado_actual <> 'rechazada' OR motivo_rechazo IS NOT NULL",
            name="muestra_rechazada_con_motivo",
        ),
        Index("ix_muestras_orden_estado", "orden_id", "estado_actual"),
    )

    codigo: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    orden_id: Mapped[UUID] = mapped_column(
        ForeignKey("ordenes_derivacion.id", ondelete="RESTRICT")
    )
    remito_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("remitos_biologicos.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[TipoMuestra] = mapped_column(enum_sql(TipoMuestra, "tipo_muestra"))
    estado_actual: Mapped[EstadoMuestra] = mapped_column(
        enum_sql(EstadoMuestra, "estado_muestra"), default=EstadoMuestra.EXTRAIDA, index=True
    )
    fecha_extraccion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_recepcion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_analisis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    volumen_ml: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    temperatura_min_c: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    temperatura_max_c: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    sitio_extraccion: Mapped[str | None] = mapped_column(String(160))
    observaciones: Mapped[str | None] = mapped_column(Text)
    motivo_rechazo: Mapped[str | None] = mapped_column(Text)

    orden: Mapped[OrdenDerivacion] = relationship(back_populates="muestras")
    remito: Mapped["RemitoBiologico | None"] = relationship(back_populates="muestras")
    solicitudes_analisis: Mapped[list[OrdenAnalisis]] = relationship(back_populates="muestra")
    cadena_custodia: Mapped["CadenaCustodia"] = relationship(
        back_populates="muestra", cascade="all, delete-orphan", uselist=False
    )
    eventos_custodia: Mapped[list["EventoCustodia"]] = relationship(
        back_populates="muestra"
    )


class ResultadoAnalisis(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "resultados_analisis"

    orden_analisis_id: Mapped[UUID] = mapped_column(
        ForeignKey("ordenes_analisis.id", ondelete="RESTRICT"), unique=True
    )
    fecha_resultado: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valores: Mapped[dict[str, Any]] = mapped_column(JSON)
    conclusion: Mapped[str | None] = mapped_column(Text)
    observaciones: Mapped[str | None] = mapped_column(Text)
    validado_por: Mapped[str] = mapped_column(String(160))
    firmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    orden_analisis: Mapped[OrdenAnalisis] = relationship(back_populates="resultado")
