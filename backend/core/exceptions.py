class ErrorDominio(Exception):
    """Error esperado provocado por una regla del negocio."""

    def __init__(self, mensaje: str, codigo: str = "regla_negocio") -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


class RecursoNoEncontrado(ErrorDominio):
    def __init__(self, recurso: str, identificador: object) -> None:
        super().__init__(
            f"No se encontró {recurso} con identificador {identificador}",
            "recurso_no_encontrado",
        )


class ConflictoDeNegocio(ErrorDominio):
    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, "conflicto_negocio")

