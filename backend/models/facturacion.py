from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import IdentificadorMixin, MarcaTemporalMixin
from backend.models.enums import EstadoFactura, TipoComponente, enum_sql

if TYPE_CHECKING:
    from backend.models.clinica import AtencionVeterinaria, Cliente, ClinicaVeterinaria
    from backend.models.laboratorio import OrdenAnalisis, OrdenDerivacion


class Factura(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "facturas"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="factura_subtotal_no_negativo"),
        CheckConstraint("descuento >= 0", name="factura_descuento_no_negativo"),
        CheckConstraint("descuento <= subtotal", name="factura_descuento_valido"),
        CheckConstraint("total = subtotal - descuento", name="factura_total_consistente"),
        CheckConstraint(
            "fecha_vencimiento IS NULL OR fecha_vencimiento >= fecha_emision",
            name="factura_vencimiento_valido",
        ),
        Index("ix_facturas_clinica_emision", "clinica_id", "fecha_emision"),
        Index("ix_facturas_estado_emision", "estado", "fecha_emision"),
    )

    numero: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    cliente_id: Mapped[UUID] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    clinica_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinicas_veterinarias.id", ondelete="RESTRICT")
    )
    atencion_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atenciones_veterinarias.id", ondelete="RESTRICT"), unique=True
    )
    orden_derivacion_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ordenes_derivacion.id", ondelete="RESTRICT")
    )
    fecha_emision: Mapped[date] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[EstadoFactura] = mapped_column(
        enum_sql(EstadoFactura, "estado_factura"), default=EstadoFactura.BORRADOR, index=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    descuento: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    emitida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observaciones: Mapped[str | None] = mapped_column(Text)

    cliente: Mapped["Cliente"] = relationship(back_populates="facturas")
    clinica: Mapped["ClinicaVeterinaria"] = relationship(back_populates="facturas")
    atencion: Mapped["AtencionVeterinaria | None"] = relationship(back_populates="facturas")
    orden_derivacion: Mapped["OrdenDerivacion | None"] = relationship(back_populates="facturas")
    componentes: Mapped[list["ComponenteAtencion"]] = relationship(
        back_populates="factura", cascade="all, delete-orphan"
    )


class ComponenteAtencion(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "componentes_atencion"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="componente_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="componente_precio_no_negativo"),
        CheckConstraint(
            "subtotal = round(cantidad * precio_unitario, 2)",
            name="componente_subtotal_consistente",
        ),
    )

    factura_id: Mapped[UUID] = mapped_column(
        ForeignKey("facturas.id", ondelete="RESTRICT"), index=True
    )
    atencion_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atenciones_veterinarias.id", ondelete="RESTRICT")
    )
    orden_analisis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ordenes_analisis.id", ondelete="RESTRICT")
    )
    tipo: Mapped[TipoComponente] = mapped_column(
        enum_sql(TipoComponente, "tipo_componente_atencion")
    )
    descripcion: Mapped[str] = mapped_column(String(250))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    factura: Mapped[Factura] = relationship(back_populates="componentes")
    atencion: Mapped["AtencionVeterinaria | None"] = relationship()
    orden_analisis: Mapped["OrdenAnalisis | None"] = relationship()
