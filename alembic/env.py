from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401
from alembic import context
from app.core.config import obtener_configuracion
from app.core.database import Base

config = context.config
# ``ConfigParser`` interpreta ``%`` como interpolación. Las URL de conexión
# suelen contenerlo al codificar caracteres especiales de la contraseña
# (por ejemplo, ``%40`` para ``@``), por lo que Alembic necesita recibirlo
# duplicado. Al leer la opción, ConfigParser lo vuelve a convertir en un único
# carácter y SQLAlchemy recibe la URL original.
url_base_datos = obtener_configuracion().database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", url_base_datos)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def ejecutar_migraciones_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def ejecutar_migraciones_online() -> None:
    conectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with conectable.connect() as conexion:
        context.configure(
            connection=conexion,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=conexion.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    ejecutar_migraciones_offline()
else:
    ejecutar_migraciones_online()
