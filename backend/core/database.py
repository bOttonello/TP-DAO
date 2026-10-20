from collections.abc import Generator
from sqlite3 import Connection as ConexionSQLite

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import obtener_configuracion

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


configuracion = obtener_configuracion()
argumentos_conexion = {"check_same_thread": False, "timeout": 30}


@event.listens_for(Engine, "connect")
def configurar_sqlite(conexion_dbapi: object, _registro_conexion: object) -> None:
    """Activa integridad referencial y una espera razonable ante escrituras concurrentes."""

    if not isinstance(conexion_dbapi, ConexionSQLite):
        return
    cursor = conexion_dbapi.cursor()
    cursor.execute("PRAGMA busy_timeout = 30000")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.close()


motor = create_engine(
    configuracion.database_url,
    pool_pre_ping=True,
    connect_args=argumentos_conexion,
)
FabricaSesiones = sessionmaker(
    bind=motor,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def obtener_sesion() -> Generator[Session, None, None]:
    """Entrega una sesión corta por operación o request."""

    with FabricaSesiones() as sesion:
        yield sesion
