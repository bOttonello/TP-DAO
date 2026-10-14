"""Patrones State y Singleton para muestras y remitos biológicos.

El módulo es deliberadamente independiente de SQLAlchemy. Los servicios de la
aplicación pueden reconstruir una máquina desde el string guardado en la base,
ejecutar una acción y persistir ``maquina.estado.value`` junto con la última
transición del historial.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from types import MappingProxyType
from typing import Protocol

from .excepciones import TransicionEstadoInvalida


class EstadoMuestra(StrEnum):
    """Valores persistibles del ciclo de vida de una muestra biológica."""

    EXTRAIDA = "extraida"
    EMPAQUETADA = "empaquetada"
    EN_TRANSITO = "en_transito"
    RECIBIDA = "recibida"
    ANALIZADA = "analizada"
    RECHAZADA = "rechazada"


class EstadoRemito(StrEnum):
    """Valores persistibles del ciclo de vida de un remito biológico."""

    BORRADOR = "borrador"
    EMITIDO = "emitido"
    EN_TRANSITO = "en_transito"
    RECIBIDO = "recibido"
    RECHAZADO = "rechazado"


@dataclass(frozen=True, slots=True)
class TransicionEstado:
    """Registro inmutable de un cambio de estado realizado por la máquina."""

    entidad: str
    estado_anterior: str
    estado_nuevo: str
    accion: str
    detalle: str | None = None
    ocurrida_en: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


class ContextoMuestra(Protocol):
    """Puerto mínimo que utilizan los estados concretos de muestra."""

    def _cambiar_estado(
        self,
        nuevo_estado: EstadoMuestra,
        *,
        accion: str,
        detalle: str | None = None,
    ) -> None: ...


class ContextoRemito(Protocol):
    """Puerto mínimo que utilizan los estados concretos de remito."""

    def _cambiar_estado(
        self,
        nuevo_estado: EstadoRemito,
        *,
        accion: str,
        detalle: str | None = None,
    ) -> None: ...


class EstadoMuestraBase(ABC):
    """State base: por defecto toda acción es inválida."""

    codigo: EstadoMuestra

    def _rechazar(self, accion: str) -> None:
        raise TransicionEstadoInvalida("la muestra", self.codigo.value, accion)

    def empaquetar(self, contexto: ContextoMuestra) -> None:
        self._rechazar("empaquetar")

    def iniciar_transito(self, contexto: ContextoMuestra) -> None:
        self._rechazar("iniciar_transito")

    def registrar_recepcion(
        self, contexto: ContextoMuestra, *, precinto_intacto: bool
    ) -> None:
        self._rechazar("registrar_recepcion")

    def registrar_analisis(self, contexto: ContextoMuestra) -> None:
        self._rechazar("registrar_analisis")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(codigo={self.codigo.value!r})"


class MuestraExtraida(EstadoMuestraBase):
    codigo = EstadoMuestra.EXTRAIDA

    def empaquetar(self, contexto: ContextoMuestra) -> None:
        contexto._cambiar_estado(
            EstadoMuestra.EMPAQUETADA,
            accion="empaquetar",
            detalle="Muestra acondicionada en un contenedor isotérmico.",
        )


class MuestraEmpaquetada(EstadoMuestraBase):
    codigo = EstadoMuestra.EMPAQUETADA

    def iniciar_transito(self, contexto: ContextoMuestra) -> None:
        contexto._cambiar_estado(
            EstadoMuestra.EN_TRANSITO,
            accion="iniciar_transito",
            detalle="Muestra despachada hacia el laboratorio central.",
        )


class MuestraEnTransito(EstadoMuestraBase):
    codigo = EstadoMuestra.EN_TRANSITO

    def registrar_recepcion(
        self, contexto: ContextoMuestra, *, precinto_intacto: bool
    ) -> None:
        if precinto_intacto:
            contexto._cambiar_estado(
                EstadoMuestra.RECIBIDA,
                accion="registrar_recepcion",
                detalle="Precinto sanitario verificado sin alteraciones.",
            )
            return

        contexto._cambiar_estado(
            EstadoMuestra.RECHAZADA,
            accion="registrar_recepcion",
            detalle="Muestra rechazada: el precinto sanitario llegó roto.",
        )


class MuestraRecibida(EstadoMuestraBase):
    codigo = EstadoMuestra.RECIBIDA

    def registrar_analisis(self, contexto: ContextoMuestra) -> None:
        contexto._cambiar_estado(
            EstadoMuestra.ANALIZADA,
            accion="registrar_analisis",
            detalle="Análisis de laboratorio finalizado.",
        )


class MuestraAnalizada(EstadoMuestraBase):
    codigo = EstadoMuestra.ANALIZADA


class MuestraRechazada(EstadoMuestraBase):
    codigo = EstadoMuestra.RECHAZADA


class EstadoRemitoBase(ABC):
    """State base para el remito biológico."""

    codigo: EstadoRemito

    def _rechazar(self, accion: str) -> None:
        raise TransicionEstadoInvalida("el remito", self.codigo.value, accion)

    def emitir(self, contexto: ContextoRemito) -> None:
        self._rechazar("emitir")

    def iniciar_transito(self, contexto: ContextoRemito) -> None:
        self._rechazar("iniciar_transito")

    def registrar_recepcion(
        self, contexto: ContextoRemito, *, aceptado: bool
    ) -> None:
        self._rechazar("registrar_recepcion")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(codigo={self.codigo.value!r})"


class RemitoBorrador(EstadoRemitoBase):
    codigo = EstadoRemito.BORRADOR

    def emitir(self, contexto: ContextoRemito) -> None:
        contexto._cambiar_estado(
            EstadoRemito.EMITIDO,
            accion="emitir",
            detalle="Remito biológico emitido.",
        )


class RemitoEmitido(EstadoRemitoBase):
    codigo = EstadoRemito.EMITIDO

    def iniciar_transito(self, contexto: ContextoRemito) -> None:
        contexto._cambiar_estado(
            EstadoRemito.EN_TRANSITO,
            accion="iniciar_transito",
            detalle="Remito asociado al envío en curso.",
        )


class RemitoEnTransito(EstadoRemitoBase):
    codigo = EstadoRemito.EN_TRANSITO

    def registrar_recepcion(
        self, contexto: ContextoRemito, *, aceptado: bool
    ) -> None:
        if aceptado:
            contexto._cambiar_estado(
                EstadoRemito.RECIBIDO,
                accion="registrar_recepcion",
                detalle="Remito recibido y validado por el laboratorio.",
            )
            return

        contexto._cambiar_estado(
            EstadoRemito.RECHAZADO,
            accion="registrar_recepcion",
            detalle="Remito rechazado durante la recepción del envío.",
        )


class RemitoRecibido(EstadoRemitoBase):
    codigo = EstadoRemito.RECIBIDO


class RemitoRechazado(EstadoRemitoBase):
    codigo = EstadoRemito.RECHAZADO


def _normalizar_codigo[EnumT: (EstadoMuestra, EstadoRemito)](
    tipo: type[EnumT], valor: EnumT | str
) -> EnumT:
    """Convierte enums o strings persistidos a un miembro canónico."""

    if isinstance(valor, tipo):
        return valor
    if not isinstance(valor, str):
        raise ValueError(f"Estado inválido: {valor!r}")

    normalizado = valor.strip().upper().replace(" ", "_").replace("-", "_")
    try:
        return tipo[normalizado]
    except KeyError as error:
        permitidos = ", ".join(estado.value for estado in tipo)
        raise ValueError(
            f"Estado {valor!r} desconocido. Valores permitidos: {permitidos}."
        ) from error


class RegistroEstados:
    """Singleton thread-safe que conserva una instancia por cada State.

    Centralizar los objetos de estado evita crearlos en cada petición y asegura
    que todo el sistema use el mismo catálogo de estados canónicos.
    """

    _instancia: RegistroEstados | None = None
    _cerrojo = Lock()

    def __new__(cls) -> RegistroEstados:
        if cls._instancia is None:
            with cls._cerrojo:
                if cls._instancia is None:
                    instancia = super().__new__(cls)
                    instancia._inicializar_catalogos()
                    cls._instancia = instancia
        return cls._instancia

    @classmethod
    def instancia(cls) -> RegistroEstados:
        """Devuelve la única instancia del registro."""

        return cls()

    def _inicializar_catalogos(self) -> None:
        estados_muestra: dict[EstadoMuestra, EstadoMuestraBase] = {
            EstadoMuestra.EXTRAIDA: MuestraExtraida(),
            EstadoMuestra.EMPAQUETADA: MuestraEmpaquetada(),
            EstadoMuestra.EN_TRANSITO: MuestraEnTransito(),
            EstadoMuestra.RECIBIDA: MuestraRecibida(),
            EstadoMuestra.ANALIZADA: MuestraAnalizada(),
            EstadoMuestra.RECHAZADA: MuestraRechazada(),
        }
        estados_remito: dict[EstadoRemito, EstadoRemitoBase] = {
            EstadoRemito.BORRADOR: RemitoBorrador(),
            EstadoRemito.EMITIDO: RemitoEmitido(),
            EstadoRemito.EN_TRANSITO: RemitoEnTransito(),
            EstadoRemito.RECIBIDO: RemitoRecibido(),
            EstadoRemito.RECHAZADO: RemitoRechazado(),
        }
        self._estados_muestra = MappingProxyType(estados_muestra)
        self._estados_remito = MappingProxyType(estados_remito)

    @property
    def estados_muestra(self) -> Mapping[EstadoMuestra, EstadoMuestraBase]:
        return self._estados_muestra

    @property
    def estados_remito(self) -> Mapping[EstadoRemito, EstadoRemitoBase]:
        return self._estados_remito

    def obtener_estado_muestra(
        self, codigo: EstadoMuestra | str
    ) -> EstadoMuestraBase:
        return self._estados_muestra[_normalizar_codigo(EstadoMuestra, codigo)]

    def obtener_estado_remito(self, codigo: EstadoRemito | str) -> EstadoRemitoBase:
        return self._estados_remito[_normalizar_codigo(EstadoRemito, codigo)]


ObservadorTransicion = Callable[[TransicionEstado], None]


class CicloVidaMuestra:
    """Context del patrón State para una muestra biológica."""

    def __init__(
        self,
        estado_inicial: EstadoMuestra | str = EstadoMuestra.EXTRAIDA,
        *,
        observador: ObservadorTransicion | None = None,
    ) -> None:
        self._registro = RegistroEstados.instancia()
        self._estado_objeto = self._registro.obtener_estado_muestra(estado_inicial)
        self._historial: tuple[TransicionEstado, ...] = ()
        self._observador = observador

    @property
    def estado(self) -> EstadoMuestra:
        return self._estado_objeto.codigo

    @property
    def historial(self) -> tuple[TransicionEstado, ...]:
        return self._historial

    @property
    def ultima_transicion(self) -> TransicionEstado | None:
        return self._historial[-1] if self._historial else None

    def _cambiar_estado(
        self,
        nuevo_estado: EstadoMuestra,
        *,
        accion: str,
        detalle: str | None = None,
    ) -> None:
        transicion = TransicionEstado(
            entidad="MUESTRA",
            estado_anterior=self.estado.value,
            estado_nuevo=nuevo_estado.value,
            accion=accion,
            detalle=detalle,
        )
        self._estado_objeto = self._registro.obtener_estado_muestra(nuevo_estado)
        self._historial = (*self._historial, transicion)
        if self._observador is not None:
            self._observador(transicion)

    def empaquetar(self) -> TransicionEstado:
        self._estado_objeto.empaquetar(self)
        return self._historial[-1]

    def iniciar_transito(self) -> TransicionEstado:
        self._estado_objeto.iniciar_transito(self)
        return self._historial[-1]

    def registrar_recepcion(self, *, precinto_intacto: bool) -> TransicionEstado:
        self._estado_objeto.registrar_recepcion(
            self, precinto_intacto=precinto_intacto
        )
        return self._historial[-1]

    def registrar_analisis(self) -> TransicionEstado:
        self._estado_objeto.registrar_analisis(self)
        return self._historial[-1]


class CicloVidaRemito:
    """Context del patrón State para un remito biológico."""

    def __init__(
        self,
        estado_inicial: EstadoRemito | str = EstadoRemito.BORRADOR,
        *,
        observador: ObservadorTransicion | None = None,
    ) -> None:
        self._registro = RegistroEstados.instancia()
        self._estado_objeto = self._registro.obtener_estado_remito(estado_inicial)
        self._historial: tuple[TransicionEstado, ...] = ()
        self._observador = observador

    @property
    def estado(self) -> EstadoRemito:
        return self._estado_objeto.codigo

    @property
    def historial(self) -> tuple[TransicionEstado, ...]:
        return self._historial

    @property
    def ultima_transicion(self) -> TransicionEstado | None:
        return self._historial[-1] if self._historial else None

    def _cambiar_estado(
        self,
        nuevo_estado: EstadoRemito,
        *,
        accion: str,
        detalle: str | None = None,
    ) -> None:
        transicion = TransicionEstado(
            entidad="REMITO",
            estado_anterior=self.estado.value,
            estado_nuevo=nuevo_estado.value,
            accion=accion,
            detalle=detalle,
        )
        self._estado_objeto = self._registro.obtener_estado_remito(nuevo_estado)
        self._historial = (*self._historial, transicion)
        if self._observador is not None:
            self._observador(transicion)

    def emitir(self) -> TransicionEstado:
        self._estado_objeto.emitir(self)
        return self._historial[-1]

    def iniciar_transito(self) -> TransicionEstado:
        self._estado_objeto.iniciar_transito(self)
        return self._historial[-1]

    def registrar_recepcion(self, *, aceptado: bool) -> TransicionEstado:
        self._estado_objeto.registrar_recepcion(self, aceptado=aceptado)
        return self._historial[-1]
