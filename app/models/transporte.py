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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdentificadorMixin, MarcaTemporalMixin
from app.models.enums import (
    EstadoContenedor,
    EstadoEnvio,
    EstadoMuestra,
    EstadoPrecinto,
    EstadoRemito,
    TipoEventoCustodia,
    TipoEventoRemito,
    enum_sql,
)

if TYPE_CHECKING:
    from app.models.clinica import ClinicaVeterinaria
    from app.models.laboratorio import LaboratorioCentral, MuestraBiologica


class Contenedor(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "contenedores"
    __table_args__ = (
        CheckConstraint("capacidad_muestras > 0", name="contenedor_capacidad_positiva"),
        CheckConstraint(
            "temperatura_min_c < temperatura_max_c",
            name="contenedor_rango_temperatura_valido",
        ),
    )

    codigo: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(250))
    capacidad_muestras: Mapped[int]
    temperatura_min_c: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    temperatura_max_c: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    estado: Mapped[EstadoContenedor] = mapped_column(
        enum_sql(EstadoContenedor, "estado_contenedor"),
        default=EstadoContenedor.DISPONIBLE,
        index=True,
    )
    ultima_sanitizacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    remitos: Mapped[list["RemitoBiologico"]] = relationship(back_populates="contenedor")


class PrecintoSanitario(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "precintos_sanitarios"

    codigo: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    estado: Mapped[EstadoPrecinto] = mapped_column(
        enum_sql(EstadoPrecinto, "estado_precinto"),
        default=EstadoPrecinto.DISPONIBLE,
        index=True,
    )
    aplicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observaciones: Mapped[str | None] = mapped_column(Text)

    remito: Mapped["RemitoBiologico | None"] = relationship(
        back_populates="precinto", uselist=False
    )


class RemitoBiologico(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "remitos_biologicos"
    __table_args__ = (
        CheckConstraint(
            "fecha_despacho IS NULL OR fecha_despacho >= fecha_emision",
            name="remito_despacho_posterior_emision",
        ),
        Index("ix_remitos_origen_emision", "clinica_origen_id", "fecha_emision"),
        Index("ix_remitos_estado_emision", "estado", "fecha_emision"),
    )

    numero: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    contenedor_id: Mapped[UUID] = mapped_column(
        ForeignKey("contenedores.id", ondelete="RESTRICT")
    )
    precinto_id: Mapped[UUID] = mapped_column(
        ForeignKey("precintos_sanitarios.id", ondelete="RESTRICT"), unique=True
    )
    clinica_origen_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinicas_veterinarias.id", ondelete="RESTRICT")
    )
    laboratorio_destino_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratorios_centrales.id", ondelete="RESTRICT")
    )
    fecha_emision: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_despacho: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[EstadoRemito] = mapped_column(
        enum_sql(EstadoRemito, "estado_remito"), default=EstadoRemito.BORRADOR, index=True
    )
    observaciones: Mapped[str | None] = mapped_column(Text)

    contenedor: Mapped[Contenedor] = relationship(back_populates="remitos")
    precinto: Mapped[PrecintoSanitario] = relationship(back_populates="remito")
    clinica_origen: Mapped["ClinicaVeterinaria"] = relationship()
    laboratorio_destino: Mapped["LaboratorioCentral"] = relationship()
    muestras: Mapped[list["MuestraBiologica"]] = relationship(back_populates="remito")
    envio: Mapped["Envio | None"] = relationship(back_populates="remito", uselist=False)
    recepcion: Mapped["RecepcionLaboratorio | None"] = relationship(
        back_populates="remito", uselist=False
    )
    eventos: Mapped[list["EventoRemito"]] = relationship(
        back_populates="remito", order_by="EventoRemito.secuencia"
    )


class Envio(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "envios"
    __table_args__ = (
        CheckConstraint(
            "fecha_entrega IS NULL OR fecha_salida IS NULL OR fecha_entrega >= fecha_salida",
            name="envio_entrega_posterior_salida",
        ),
        CheckConstraint(
            "temperatura_min_registrada_c IS NULL OR temperatura_max_registrada_c IS NULL "
            "OR temperatura_min_registrada_c <= temperatura_max_registrada_c",
            name="envio_rango_temperatura_valido",
        ),
        Index("ix_envios_estado_salida", "estado", "fecha_salida"),
    )

    remito_id: Mapped[UUID] = mapped_column(
        ForeignKey("remitos_biologicos.id", ondelete="RESTRICT"), unique=True
    )
    codigo_seguimiento: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    transportista: Mapped[str] = mapped_column(String(160))
    conductor: Mapped[str] = mapped_column(String(160))
    vehiculo: Mapped[str] = mapped_column(String(100))
    fecha_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[EstadoEnvio] = mapped_column(
        enum_sql(EstadoEnvio, "estado_envio"), default=EstadoEnvio.PREPARADO, index=True
    )
    temperatura_min_registrada_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    temperatura_max_registrada_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    observaciones: Mapped[str | None] = mapped_column(Text)

    remito: Mapped[RemitoBiologico] = relationship(back_populates="envio")
    recepcion: Mapped["RecepcionLaboratorio | None"] = relationship(
        back_populates="envio", uselist=False
    )
    eventos_custodia: Mapped[list["EventoCustodia"]] = relationship(back_populates="envio")


class RecepcionLaboratorio(IdentificadorMixin, Base):
    __tablename__ = "recepciones_laboratorio"
    __table_args__ = (
        CheckConstraint(
            "estado_precinto <> 'roto' OR muestra_viable = false",
            name="recepcion_precinto_roto_no_viable",
        ),
    )

    remito_id: Mapped[UUID] = mapped_column(
        ForeignKey("remitos_biologicos.id", ondelete="RESTRICT"), unique=True
    )
    envio_id: Mapped[UUID] = mapped_column(
        ForeignKey("envios.id", ondelete="RESTRICT"), unique=True
    )
    laboratorio_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratorios_centrales.id", ondelete="RESTRICT")
    )
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    receptor_nombre: Mapped[str] = mapped_column(String(160))
    estado_precinto: Mapped[EstadoPrecinto] = mapped_column(
        enum_sql(EstadoPrecinto, "estado_precinto_recepcion")
    )
    temperatura_recepcion_c: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    muestra_viable: Mapped[bool] = mapped_column(Boolean)
    observaciones: Mapped[str | None] = mapped_column(Text)

    remito: Mapped[RemitoBiologico] = relationship(back_populates="recepcion")
    envio: Mapped[Envio] = relationship(back_populates="recepcion")
    laboratorio: Mapped["LaboratorioCentral"] = relationship(back_populates="recepciones")


class CadenaCustodia(IdentificadorMixin, Base):
    __tablename__ = "cadenas_custodia"

    muestra_id: Mapped[UUID] = mapped_column(
        ForeignKey("muestras_biologicas.id", ondelete="RESTRICT"), unique=True
    )
    abierta_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    muestra: Mapped["MuestraBiologica"] = relationship(back_populates="cadena_custodia")
    eventos: Mapped[list["EventoCustodia"]] = relationship(
        back_populates="cadena_custodia", order_by="EventoCustodia.secuencia"
    )


class EventoCustodia(IdentificadorMixin, Base):
    __tablename__ = "eventos_custodia"
    __table_args__ = (
        UniqueConstraint("muestra_id", "secuencia"),
        CheckConstraint("secuencia > 0", name="evento_custodia_secuencia_positiva"),
        CheckConstraint(
            "estado_anterior IS NULL OR estado_anterior <> estado_nuevo "
            "OR (tipo_evento = 'transferencia' AND estado_nuevo = 'en_transito')",
            name="evento_custodia_cambio_real",
        ),
        Index("ix_eventos_custodia_muestra_ocurrido", "muestra_id", "ocurrido_en"),
    )

    cadena_custodia_id: Mapped[UUID] = mapped_column(
        ForeignKey("cadenas_custodia.id", ondelete="RESTRICT")
    )
    muestra_id: Mapped[UUID] = mapped_column(
        ForeignKey("muestras_biologicas.id", ondelete="RESTRICT")
    )
    envio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("envios.id", ondelete="RESTRICT")
    )
    secuencia: Mapped[int]
    tipo_evento: Mapped[TipoEventoCustodia] = mapped_column(
        enum_sql(TipoEventoCustodia, "tipo_evento_custodia")
    )
    estado_anterior: Mapped[EstadoMuestra | None] = mapped_column(
        enum_sql(EstadoMuestra, "estado_muestra_anterior"), nullable=True
    )
    estado_nuevo: Mapped[EstadoMuestra] = mapped_column(
        enum_sql(EstadoMuestra, "estado_muestra_nuevo")
    )
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(160))
    ubicacion: Mapped[str] = mapped_column(String(250))
    temperatura_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    observaciones: Mapped[str | None] = mapped_column(Text)
    datos_adicionales: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    cadena_custodia: Mapped[CadenaCustodia] = relationship(back_populates="eventos")
    muestra: Mapped["MuestraBiologica"] = relationship(back_populates="eventos_custodia")
    envio: Mapped[Envio | None] = relationship(back_populates="eventos_custodia")


class EventoRemito(IdentificadorMixin, Base):
    __tablename__ = "eventos_remito"
    __table_args__ = (
        UniqueConstraint("remito_id", "secuencia"),
        CheckConstraint("secuencia > 0", name="evento_remito_secuencia_positiva"),
        CheckConstraint(
            "estado_anterior IS NULL OR estado_anterior <> estado_nuevo",
            name="evento_remito_cambio_real",
        ),
        Index("ix_eventos_remito_remito_ocurrido", "remito_id", "ocurrido_en"),
    )

    remito_id: Mapped[UUID] = mapped_column(
        ForeignKey("remitos_biologicos.id", ondelete="RESTRICT")
    )
    secuencia: Mapped[int]
    tipo_evento: Mapped[TipoEventoRemito] = mapped_column(
        enum_sql(TipoEventoRemito, "tipo_evento_remito")
    )
    estado_anterior: Mapped[EstadoRemito | None] = mapped_column(
        enum_sql(EstadoRemito, "estado_remito_anterior"), nullable=True
    )
    estado_nuevo: Mapped[EstadoRemito] = mapped_column(
        enum_sql(EstadoRemito, "estado_remito_nuevo")
    )
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(160))
    observaciones: Mapped[str | None] = mapped_column(Text)

    remito: Mapped[RemitoBiologico] = relationship(back_populates="eventos")


def _evitar_mutacion_historial(_mapper: object, _connection: object, target: object) -> None:
    raise ValueError(f"{type(target).__name__} es inmutable; agregá un nuevo evento")


event.listen(EventoCustodia, "before_update", _evitar_mutacion_historial)
event.listen(EventoCustodia, "before_delete", _evitar_mutacion_historial)
event.listen(EventoRemito, "before_update", _evitar_mutacion_historial)
event.listen(EventoRemito, "before_delete", _evitar_mutacion_historial)
