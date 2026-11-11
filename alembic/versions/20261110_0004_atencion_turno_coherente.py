"""Garantiza la coherencia entre una atención y su turno.

Revision ID: 20261110_0004
Revises: 20261110_0003
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261110_0004"
down_revision: str | None = "20261110_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _crear_trigger(nombre: str, operacion: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER {nombre}
        BEFORE {operacion} ON atenciones_veterinarias
        FOR EACH ROW
        WHEN NEW.turno_id IS NOT NULL
        BEGIN
            SELECT RAISE(ABORT, 'La atencion no coincide con su turno')
             WHERE NOT EXISTS (
                SELECT 1
                  FROM turnos AS t
                  JOIN historias_clinicas AS h
                    ON h.id = NEW.historia_clinica_id
                 WHERE t.id = NEW.turno_id
                   AND t.mascota_id = h.mascota_id
                   AND t.clinica_id = NEW.clinica_id
                   AND t.profesional_id = NEW.profesional_id
                   AND t.tipo = NEW.tipo
             );
        END
        """
    )


def upgrade() -> None:
    _crear_trigger("tr_atenciones_turno_coherente_insert", "INSERT")
    _crear_trigger(
        "tr_atenciones_turno_coherente_update",
        "UPDATE OF turno_id, historia_clinica_id, clinica_id, profesional_id, tipo",
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tr_atenciones_turno_coherente_update")
    op.execute("DROP TRIGGER IF EXISTS tr_atenciones_turno_coherente_insert")
