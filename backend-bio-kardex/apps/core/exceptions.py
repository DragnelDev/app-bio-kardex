from rest_framework.response import Response
from rest_framework.views import exception_handler


class ErrorNegocio(Exception):
    """Violacion de una regla de negocio. Se responde como HTTP 400."""

    codigo = "error_negocio"

    def __init__(self, mensaje: str, codigo: str | None = None, **extra):
        super().__init__(mensaje)
        self.mensaje = mensaje
        if codigo:
            self.codigo = codigo
        self.extra = extra


class StockInsuficiente(ErrorNegocio):
    codigo = "stock_insuficiente"


class KardexInalterable(Exception):
    """Se intento modificar o borrar un movimiento del Kardex."""


def manejador_excepciones(exc, context):
    if isinstance(exc, ErrorNegocio):
        return Response(
            {"detail": exc.mensaje, "code": exc.codigo, **exc.extra}, status=400
        )
    return exception_handler(exc, context)
