"""Pruebas integradas del esquema real creado por Alembic."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from backend.models import (
    AtencionVeterinaria,
    EventoCustodia,
    MuestraBiologica,
    OrdenAnalisis,
    RemitoBiologico,
    Turno,
)
from backend.models.enums import EstadoMuestra, EstadoRemito, EstadoTurno, TipoAtencion
from backend.schemas import RecepcionLaboratorioCrear, ResultadoCrear
from tests.test_procesos import preparar_escenario

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]


def _configuracion_alembic() -> Config:
    return Config(str(RAIZ_PROYECTO / "alembic.ini"))


def _ejecutar_alembic(
    motor: Engine, operacion: Callable[..., None], *argumentos: str
) -> None:
    configuracion = _configuracion_alembic()
    with motor.begin() as conexion:
        configuracion.attributes["connection"] = conexion
        operacion(configuracion, *argumentos)


@pytest.fixture()
def motor_migrado(tmp_path: Path) -> Generator[Engine, None, None]:
    ruta = (tmp_path / "patitas_migrada.db").as_posix()
    motor = create_engine(
        f"sqlite+pysqlite:///{ruta}",
        connect_args={"check_same_thread": False},
    )
    _ejecutar_alembic(motor, command.upgrade, "head")
    try:
        yield motor
    finally:
        motor.dispose()


def test_migraciones_son_reproducibles_y_sin_diferencias(tmp_path: Path) -> None:
    ruta = (tmp_path / "ciclo_migraciones.db").as_posix()
    motor = create_engine(f"sqlite+pysqlite:///{ruta}")
    try:
        _ejecutar_alembic(motor, command.upgrade, "head")
        _ejecutar_alembic(motor, command.check)

        configuracion = _configuracion_alembic()
        revision_esperada = ScriptDirectory.from_config(
            configuracion
        ).get_current_head()
        with motor.connect() as conexion:
            assert (
                MigrationContext.configure(conexion).get_current_revision()
                == revision_esperada
            )

        _ejecutar_alembic(motor, command.downgrade, "20261013_0001")
        _ejecutar_alembic(motor, command.upgrade, "head")
        _ejecutar_alembic(motor, command.check)
        _ejecutar_alembic(motor, command.downgrade, "base")

        with motor.connect() as conexion:
            tablas = set(
                conexion.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                ).scalars()
            )
        assert tablas == {"alembic_version"}
    finally:
        motor.dispose()


def test_flujo_completo_funciona_sobre_el_esquema_migrado(
    motor_migrado: Engine,
) -> None:
    with Session(motor_migrado, expire_on_commit=False) as sesion:
        with sesion.begin():
            datos = preparar_escenario(sesion)
            datos["servicio"].recibir_remito(
                datos["remito"].id,
                RecepcionLaboratorioCrear(
                    precinto_intacto=True,
                    receptor="Laboratorio de prueba",
                    temperatura_recepcion_c=Decimal("4"),
                ),
            )
            solicitud = sesion.scalar(
                select(OrdenAnalisis).where(
                    OrdenAnalisis.orden_id == datos["orden"].id
                )
            )
            datos["servicio"].registrar_resultado(
                ResultadoCrear(
                    orden_analisis_id=solicitud.id,
                    validado_por="Bioquímica de prueba",
                    valores={"hematocrito": 40},
                    conclusion="Resultado normal",
                )
            )

        muestra = sesion.get(MuestraBiologica, datos["muestra"].id)
        remito = sesion.get(RemitoBiologico, datos["remito"].id)
        assert muestra.estado_actual == EstadoMuestra.ANALIZADA
        assert remito.estado == EstadoRemito.RECIBIDO
        assert [evento.secuencia for evento in muestra.eventos_custodia] == [
            1,
            2,
            3,
            4,
            5,
        ]


def test_sqlite_impide_desincronizar_estados_e_historial(
    motor_migrado: Engine,
) -> None:
    with Session(motor_migrado, expire_on_commit=False) as sesion:
        with sesion.begin():
            datos = preparar_escenario(sesion, despachar=False)
            muestra_id = datos["muestra"].id
            remito_id = datos["remito"].id
            evento_id = sesion.scalar(
                select(EventoCustodia.id)
                .where(EventoCustodia.muestra_id == muestra_id)
                .order_by(EventoCustodia.secuencia)
                .limit(1)
            )

    with pytest.raises(IntegrityError, match="evento de custodia"):
        with motor_migrado.begin() as conexion:
            conexion.execute(
                text(
                    "UPDATE muestras_biologicas "
                    "SET estado_actual = 'analizada' WHERE id = :id"
                ),
                {"id": muestra_id.hex},
            )
    with pytest.raises(IntegrityError, match="evento de remito"):
        with motor_migrado.begin() as conexion:
            conexion.execute(
                text(
                    "UPDATE remitos_biologicos "
                    "SET estado = 'recibido' WHERE id = :id"
                ),
                {"id": remito_id.hex},
            )
    with pytest.raises(IntegrityError, match="inmutable"):
        with motor_migrado.begin() as conexion:
            conexion.execute(
                text("UPDATE eventos_custodia SET actor = 'alterado' WHERE id = :id"),
                {"id": evento_id.hex},
            )
    with pytest.raises(IntegrityError, match="no se puede eliminar"):
        with motor_migrado.begin() as conexion:
            conexion.execute(
                text("DELETE FROM eventos_custodia WHERE id = :id"),
                {"id": evento_id.hex},
            )


def test_sqlite_impide_atencion_incompatible_con_turno(
    motor_migrado: Engine,
) -> None:
    with Session(motor_migrado, expire_on_commit=False) as sesion:
        with sesion.begin():
            datos = preparar_escenario(sesion, despachar=False)
            inicio = datetime.now(UTC) + timedelta(days=1)
            turno = Turno(
                clinica_id=datos["clinica"].id,
                profesional_id=datos["profesional"].id,
                mascota_id=datos["mascota"].id,
                tipo=TipoAtencion.CONTROL,
                inicio=inicio,
                fin=inicio + timedelta(minutes=30),
                estado=EstadoTurno.PROGRAMADO,
                motivo="Control",
            )
            sesion.add(turno)
            sesion.flush()
            sesion.add(
                AtencionVeterinaria(
                    historia_clinica_id=datos["mascota"].historia_clinica.id,
                    turno_id=turno.id,
                    clinica_id=datos["clinica"].id,
                    profesional_id=datos["profesional"].id,
                    fecha=datetime.now(UTC),
                    tipo=TipoAtencion.URGENCIA,
                    motivo="Tipo incompatible",
                    esquema_vacunacion_al_dia=True,
                    vacunas_pendientes=[],
                )
            )
            with pytest.raises(IntegrityError, match="no coincide con su turno"):
                sesion.flush()
