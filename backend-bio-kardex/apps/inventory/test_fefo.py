import pytest

from apps.inventory.fefo import FaltanteFEFO, asignar_fefo


def test_toma_primero_el_lote_que_vence_antes():
    # (id, cantidad) ya ordenado por vencimiento
    assert asignar_fefo([(1, 10), (2, 50)], 4) == [(1, 4)]


def test_reparte_entre_varios_lotes_en_orden():
    assert asignar_fefo([(1, 3), (2, 5), (3, 9)], 10) == [(1, 3), (2, 5), (3, 2)]


def test_agota_exactamente_el_stock():
    assert asignar_fefo([(1, 3), (2, 2)], 5) == [(1, 3), (2, 2)]


def test_ignora_lotes_sin_stock():
    assert asignar_fefo([(1, 0), (2, 4)], 2) == [(2, 2)]


def test_stock_insuficiente_informa_el_faltante():
    with pytest.raises(FaltanteFEFO) as exc:
        asignar_fefo([(1, 3), (2, 2)], 8)
    assert exc.value.faltante == 3


def test_sin_lotes_falta_todo():
    with pytest.raises(FaltanteFEFO) as exc:
        asignar_fefo([], 1)
    assert exc.value.faltante == 1


@pytest.mark.parametrize("cantidad", [0, -1])
def test_cantidad_no_positiva_es_invalida(cantidad):
    with pytest.raises(ValueError):
        asignar_fefo([(1, 5)], cantidad)
