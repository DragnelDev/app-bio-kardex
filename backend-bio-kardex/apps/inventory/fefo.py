"""Logica pura de FEFO (First Expired, First Out), sin dependencias de Django.

Se mantiene separada para poder probarla de forma aislada.
"""

from collections.abc import Iterable


class FaltanteFEFO(Exception):
    """No hay stock suficiente para cubrir lo pedido."""

    def __init__(self, faltante: int):
        super().__init__(f"Faltan {faltante} unidades")
        self.faltante = faltante


def asignar_fefo(
    disponibles: Iterable[tuple[int, int]], requerida: int
) -> list[tuple[int, int]]:
    """Reparte `requerida` unidades entre los lotes disponibles.

    `disponibles` es una secuencia de (id_lote, cantidad) YA ORDENADA por fecha de
    vencimiento ascendente (el que vence primero va primero). Devuelve una lista de
    (id_lote, cantidad_a_tomar). Lanza FaltanteFEFO si el stock no alcanza.
    """
    if requerida <= 0:
        raise ValueError("La cantidad requerida debe ser positiva.")

    restante = requerida
    asignacion: list[tuple[int, int]] = []
    for id_lote, cantidad in disponibles:
        if restante == 0:
            break
        if cantidad <= 0:
            continue
        tomar = min(cantidad, restante)
        asignacion.append((id_lote, tomar))
        restante -= tomar

    if restante > 0:
        raise FaltanteFEFO(restante)
    return asignacion
