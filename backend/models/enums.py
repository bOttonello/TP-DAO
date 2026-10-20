from enum import StrEnum

from sqlalchemy import Enum as EnumSQL


def enum_sql(clase_enum: type[StrEnum], nombre: str) -> EnumSQL:
    """Enum con valores legibles almacenados como texto validado en SQLite."""

    return EnumSQL(
        clase_enum,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda clase: [miembro.value for miembro in clase],
    )


class TipoDocumento(StrEnum):
    DNI = "dni"
    PASAPORTE = "pasaporte"
    CUIT = "cuit"


class SexoMascota(StrEnum):
    MACHO = "macho"
    HEMBRA = "hembra"
    NO_ESPECIFICADO = "no_especificado"


class EstadoTurno(StrEnum):
    PROGRAMADO = "programado"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"
    ATENDIDO = "atendido"
    AUSENTE = "ausente"


class TipoAtencion(StrEnum):
    CONSULTA = "consulta"
    CONTROL = "control"
    URGENCIA = "urgencia"


class EstadoOrden(StrEnum):
    EMITIDA = "emitida"
    MUESTRA_EXTRAIDA = "muestra_extraida"
    DESPACHADA = "despachada"
    RECIBIDA = "recibida"
    REQUIERE_NUEVA_MUESTRA = "requiere_nueva_muestra"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class PrioridadOrden(StrEnum):
    NORMAL = "normal"
    URGENTE = "urgente"


class EstadoSolicitudAnalisis(StrEnum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class TipoMuestra(StrEnum):
    SANGRE = "sangre"
    ORINA = "orina"
    MATERIA_FECAL = "materia_fecal"
    TEJIDO = "tejido"
    HISOPADO = "hisopado"
    OTRO = "otro"


class EstadoMuestra(StrEnum):
    EXTRAIDA = "extraida"
    EMPAQUETADA = "empaquetada"
    EN_TRANSITO = "en_transito"
    RECIBIDA = "recibida"
    ANALIZADA = "analizada"
    RECHAZADA = "rechazada"


class EstadoContenedor(StrEnum):
    DISPONIBLE = "disponible"
    EN_USO = "en_uso"
    EN_TRANSITO = "en_transito"
    MANTENIMIENTO = "mantenimiento"
    BAJA = "baja"


class EstadoPrecinto(StrEnum):
    DISPONIBLE = "disponible"
    APLICADO = "aplicado"
    INTACTO = "intacto"
    ROTO = "roto"
    INVALIDADO = "invalidado"


class EstadoRemito(StrEnum):
    BORRADOR = "borrador"
    EMITIDO = "emitido"
    EN_TRANSITO = "en_transito"
    RECIBIDO = "recibido"
    RECHAZADO = "rechazado"


class EstadoEnvio(StrEnum):
    PREPARADO = "preparado"
    EN_TRANSITO = "en_transito"
    ENTREGADO = "entregado"
    CON_INCIDENCIA = "con_incidencia"


class TipoEventoCustodia(StrEnum):
    EXTRACCION = "extraccion"
    EMPAQUETADO = "empaquetado"
    DESPACHO = "despacho"
    TRANSFERENCIA = "transferencia"
    RECEPCION = "recepcion"
    RECHAZO = "rechazo"
    ANALISIS = "analisis"


class TipoEventoRemito(StrEnum):
    CREACION = "creacion"
    EMISION = "emision"
    DESPACHO = "despacho"
    RECEPCION = "recepcion"
    RECHAZO = "rechazo"


class EstadoFactura(StrEnum):
    BORRADOR = "borrador"
    EMITIDA = "emitida"
    PAGADA = "pagada"
    ANULADA = "anulada"
    VENCIDA = "vencida"


class TipoComponente(StrEnum):
    ATENCION = "atencion"
    LABORATORIO = "laboratorio"
    VACUNA = "vacuna"
    INSUMO = "insumo"
    OTRO = "otro"
