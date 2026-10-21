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
            nullable=False,
            server_default="consulta",
        ),
    )


def downgrade() -> None:
    columnas = {columna["name"] for columna in sa.inspect(op.get_bind()).get_columns("turnos")}
    if "tipo" in columnas:
        op.drop_column("turnos", "tipo")
