"""Impide modificar estados sin su evento de trazabilidad.

Revision ID: 20261110_0003
Revises: 20261020_0002
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261110_0003"
down_revision: str | None = "20261020_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TRIGGER tr_muestras_estado_solo_por_evento
        BEFORE UPDATE OF estado_actual ON muestras_biologicas
        FOR EACH ROW
        WHEN NEW.estado_actual IS NOT OLD.estado_actual
         AND NOT EXISTS (
            SELECT 1
              FROM eventos_custodia AS e
             WHERE e.muestra_id = NEW.id
               AND e.estado_nuevo = NEW.estado_actual
               AND e.secuencia = (
                    SELECT MAX(ultimo.secuencia)
                      FROM eventos_custodia AS ultimo
                     WHERE ultimo.muestra_id = NEW.id
               )
         )
        BEGIN
            SELECT RAISE(
                ABORT,
                'El estado de la muestra requiere un evento de custodia'
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_remitos_estado_solo_por_evento
        BEFORE UPDATE OF estado ON remitos_biologicos
        FOR EACH ROW
        WHEN NEW.estado IS NOT OLD.estado
         AND NOT EXISTS (
            SELECT 1
              FROM eventos_remito AS e
             WHERE e.remito_id = NEW.id
               AND e.estado_nuevo = NEW.estado
               AND e.secuencia = (
                    SELECT MAX(ultimo.secuencia)
                      FROM eventos_remito AS ultimo
                     WHERE ultimo.remito_id = NEW.id
               )
         )
        BEGIN
            SELECT RAISE(
                ABORT,
                'El estado del remito requiere un evento de remito'
            );
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tr_remitos_estado_solo_por_evento")
    op.execute("DROP TRIGGER IF EXISTS tr_muestras_estado_solo_por_evento")
