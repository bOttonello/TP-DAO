"""Agrega el tipo de atención a los turnos.

Revision ID: 20261020_0002
Revises: 20261013_0001
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261020_0002"
down_revision: str | None = "20261013_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columnas = {columna["name"] for columna in sa.inspect(op.get_bind()).get_columns("turnos")}
    if "tipo" in columnas:
        return
    op.add_column(
        "turnos",
        sa.Column(
            "tipo",
            sa.String(length=8),
            sa.CheckConstraint(
                "tipo IN ('consulta', 'control', 'urgencia')",
                name=op.f("ck_turnos_tipo_atencion_turno"),
            ),
            nullable=False,
            server_default="consulta",
        ),
    )


def _crear_triggers_superposicion() -> None:
    op.execute(
        """
        CREATE TRIGGER tr_turnos_sin_superposicion_insert
        BEFORE INSERT ON turnos
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'El profesional no pertenece a la clinica')
             WHERE NOT EXISTS (
                SELECT 1 FROM profesionales_veterinarios AS p
                 WHERE p.id = NEW.profesional_id AND p.clinica_id = NEW.clinica_id
             );
            SELECT RAISE(ABORT, 'El profesional ya tiene un turno superpuesto')
             WHERE NEW.estado IN ('programado', 'confirmado')
               AND EXISTS (
                SELECT 1 FROM turnos AS t
                 WHERE t.profesional_id = NEW.profesional_id
                   AND t.estado IN ('programado', 'confirmado')
                   AND t.inicio < NEW.fin
                   AND t.fin > NEW.inicio
             );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_turnos_sin_superposicion_update
        BEFORE UPDATE OF profesional_id, clinica_id, inicio, fin, estado ON turnos
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'El profesional no pertenece a la clinica')
             WHERE NOT EXISTS (
                SELECT 1 FROM profesionales_veterinarios AS p
                 WHERE p.id = NEW.profesional_id AND p.clinica_id = NEW.clinica_id
             );
            SELECT RAISE(ABORT, 'El profesional ya tiene un turno superpuesto')
             WHERE NEW.estado IN ('programado', 'confirmado')
               AND EXISTS (
                SELECT 1 FROM turnos AS t
                 WHERE t.profesional_id = NEW.profesional_id
                   AND t.id <> NEW.id
                   AND t.estado IN ('programado', 'confirmado')
                   AND t.inicio < NEW.fin
                   AND t.fin > NEW.inicio
             );
        END
        """
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columnas = {columna["name"] for columna in inspector.get_columns("turnos")}
    if "tipo" in columnas:
        check_tipo = next(
            (
                restriccion["name"]
                for restriccion in inspector.get_check_constraints("turnos")
                if restriccion["name"]
                and restriccion["name"].endswith("tipo_atencion_turno")
            ),
            None,
        )
        with op.batch_alter_table("turnos", recreate="always") as lote:
            if check_tipo is not None:
                lote.drop_constraint(op.f(check_tipo), type_="check")
            lote.drop_column("tipo")
        # La recreación por lotes de SQLite no conserva triggers externos.
        _crear_triggers_superposicion()
