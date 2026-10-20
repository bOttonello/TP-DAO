from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import IdentificadorMixin, MarcaTemporalMixin

if TYPE_CHECKING:
    from backend.models.clinica import AtencionVeterinaria, Mascota, ProfesionalVeterinario


class Vacuna(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "vacunas"
    __table_args__ = (
        CheckConstraint("dosis_ml > 0", name="vacuna_dosis_positiva"),
        CheckConstraint("edad_minima_dias >= 0", name="vacuna_edad_minima_valida"),
        CheckConstraint(
            "intervalo_refuerzo_dias IS NULL OR intervalo_refuerzo_dias > 0",
            name="vacuna_intervalo_refuerzo_valido",
        ),
    )

    nombre: Mapped[str] = mapped_column(String(160))
    laboratorio_fabricante: Mapped[str] = mapped_column(String(160))
    especie_objetivo: Mapped[str] = mapped_column(String(80), index=True)
    dosis_ml: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    edad_minima_dias: Mapped[int] = mapped_column(default=0, server_default="0")
    intervalo_refuerzo_dias: Mapped[int | None]
    obligatoria: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    aplicaciones: Mapped[list["AplicacionVacuna"]] = relationship(back_populates="vacuna")


class AplicacionVacuna(IdentificadorMixin, MarcaTemporalMixin, Base):
    __tablename__ = "aplicaciones_vacunas"
    __table_args__ = (
        CheckConstraint("dosis_ml > 0", name="aplicacion_dosis_positiva"),
        CheckConstraint(
            "fecha_vencimiento_lote IS NULL "
            "OR fecha_vencimiento_lote >= CAST(fecha_aplicacion AS DATE)",
            name="aplicacion_lote_vigente",
        ),
    )

    vacuna_id: Mapped[UUID] = mapped_column(ForeignKey("vacunas.id", ondelete="RESTRICT"))
    mascota_id: Mapped[UUID] = mapped_column(
        ForeignKey("mascotas.id", ondelete="RESTRICT"), index=True
    )
    atencion_id: Mapped[UUID] = mapped_column(
        ForeignKey("atenciones_veterinarias.id", ondelete="RESTRICT")
    )
    profesional_id: Mapped[UUID] = mapped_column(
        ForeignKey("profesionales_veterinarios.id", ondelete="RESTRICT")
    )
    fecha_aplicacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dosis_ml: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    lote: Mapped[str] = mapped_column(String(80))
    fecha_vencimiento_lote: Mapped[date | None] = mapped_column(Date)
    proxima_aplicacion: Mapped[date | None] = mapped_column(Date)
    observaciones: Mapped[str | None] = mapped_column(Text)

    vacuna: Mapped[Vacuna] = relationship(back_populates="aplicaciones")
    mascota: Mapped["Mascota"] = relationship(back_populates="aplicaciones_vacunas")
    atencion: Mapped["AtencionVeterinaria"] = relationship(
        back_populates="aplicaciones_vacunas"
    )
    profesional: Mapped["ProfesionalVeterinario"] = relationship(
        back_populates="aplicaciones_vacunas"
    )
