from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    nombre_aplicacion: str = "HuellaVet"
    ambiente: str = "desarrollo"
    database_url: str = "sqlite+pysqlite:///./huellavet.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
