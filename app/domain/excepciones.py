"""Excepciones propias del dominio veterinario."""

from __future__ import annotations


class ErrorDeDominio(Exception):
    """Error base para reglas de negocio que no pueden cumplirse."""


class TransicionEstadoInvalida(ErrorDeDominio):
    """Se intentó ejecutar una acción no permitida por el estado actual."""

    def __init__(self, entidad: str, estado_actual: str, accion: str) -> None:
        self.entidad = entidad
        self.estado_actual = estado_actual
        self.accion = accion
        super().__init__(
            f"No se puede ejecutar '{accion}' sobre {entidad} "
            f"cuando está en estado '{estado_actual}'."
        )
