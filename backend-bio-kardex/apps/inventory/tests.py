import pytest
from django.db import connection

from apps.core.exceptions import ErrorNegocio, KardexInalterable, StockInsuficiente
from apps.inventory import services
from apps.inventory.models import (
    EstadoTraspaso,
    Lote,
    MovimientoKardex,
    StockLote,
    TipoMovimiento,
)

pytestmark = pytest.mark.django_db


def ingresar(usuario, sucursal, producto, numero, vence, cantidad):
    return services.registrar_ingreso(
        usuario=usuario, sucursal_id=sucursal.id, producto_id=producto.id,
        numero_lote=numero, fecha_vencimiento=vence, cantidad=cantidad,
    )


def vender(usuario, sucursal, producto, cantidad):
    from django.db import transaction

    with transaction.atomic():
        return services.descontar_fefo(
            usuario=usuario, sucursal_id=sucursal.id, producto_id=producto.id,
            cantidad=cantidad, tipo=TipoMovimiento.VENTA,
        )


def stock(sucursal, numero):
    return StockLote.objects.get(sucursal=sucursal, lote__numero=numero).cantidad


# ------------------------------------------------------------- ingresos

def test_ingreso_crea_lote_stock_y_kardex(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(200), 100)
    assert stock(sucursal_a, "L1") == 100
    mov = MovimientoKardex.objects.get()
    assert (mov.tipo, mov.cantidad, mov.saldo, mov.usuario) == ("ingreso", 100, 100, regente)


def test_ingreso_suma_al_mismo_lote(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(200), 100)
    ingresar(regente, sucursal_a, producto, "L1", dias(200), 50)
    assert stock(sucursal_a, "L1") == 150
    assert Lote.objects.count() == 1


def test_ingreso_rechaza_lote_vencido(regente, sucursal_a, producto, dias):
    with pytest.raises(ErrorNegocio):
        ingresar(regente, sucursal_a, producto, "L1", dias(-1), 10)


def test_ingreso_rechaza_vencimiento_distinto_para_mismo_lote(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(200), 10)
    with pytest.raises(ErrorNegocio):
        ingresar(regente, sucursal_a, producto, "L1", dias(300), 10)


def test_ingreso_exige_lote(regente, sucursal_a, producto, dias):
    with pytest.raises(ErrorNegocio):
        ingresar(regente, sucursal_a, producto, "  ", dias(200), 10)


# ------------------------------------------------------------------ FEFO

def test_fefo_descuenta_primero_el_que_vence_antes(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "TARDE", dias(400), 50)
    ingresar(regente, sucursal_a, producto, "PRONTO", dias(100), 50)
    vender(regente, sucursal_a, producto, 20)
    assert stock(sucursal_a, "PRONTO") == 30
    assert stock(sucursal_a, "TARDE") == 50


def test_fefo_cruza_lotes_cuando_uno_no_alcanza(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "PRONTO", dias(100), 10)
    ingresar(regente, sucursal_a, producto, "TARDE", dias(400), 50)
    plan = vender(regente, sucursal_a, producto, 25)
    assert [c for _, c in plan] == [10, 15]
    assert stock(sucursal_a, "PRONTO") == 0
    assert stock(sucursal_a, "TARDE") == 35


def test_fefo_ignora_lotes_vencidos(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "VIEJO", dias(5), 50)
    ingresar(regente, sucursal_a, producto, "NUEVO", dias(400), 50)
    Lote.objects.filter(numero="VIEJO").update(fecha_vencimiento=dias(-1))  # vence "ayer"
    vender(regente, sucursal_a, producto, 10)
    assert stock(sucursal_a, "VIEJO") == 50
    assert stock(sucursal_a, "NUEVO") == 40


def test_fefo_ignora_lotes_bloqueados(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "PRONTO", dias(100), 50)
    ingresar(regente, sucursal_a, producto, "TARDE", dias(400), 50)
    lote = Lote.objects.get(numero="PRONTO")
    services.cambiar_bloqueo(usuario=regente, sucursal_id=sucursal_a.id, lote_id=lote.id, bloqueado=True)
    vender(regente, sucursal_a, producto, 10)
    assert stock(sucursal_a, "PRONTO") == 50
    assert stock(sucursal_a, "TARDE") == 40


def test_stock_insuficiente_no_descuenta_nada(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    with pytest.raises(StockInsuficiente):
        vender(regente, sucursal_a, producto, 11)
    assert stock(sucursal_a, "L1") == 10


def test_fefo_no_mezcla_sucursales(regente, sucursal_a, sucursal_b, producto, dias):
    ingresar(regente, sucursal_b, producto, "L1", dias(100), 50)
    with pytest.raises(StockInsuficiente):
        vender(regente, sucursal_a, producto, 1)


def test_cada_descuento_genera_movimiento_con_saldo(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    vender(regente, sucursal_a, producto, 4)
    mov = MovimientoKardex.objects.filter(tipo=TipoMovimiento.VENTA).get()
    assert (mov.cantidad, mov.saldo) == (-4, 6)


# --------------------------------------------------------- bajas y ajustes

def test_baja_exige_motivo_y_descuenta(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    lote = Lote.objects.get()
    with pytest.raises(ErrorNegocio):
        services.registrar_baja(usuario=regente, sucursal_id=sucursal_a.id, lote_id=lote.id, cantidad=3, motivo=" ")
    services.registrar_baja(usuario=regente, sucursal_id=sucursal_a.id, lote_id=lote.id, cantidad=3, motivo="Danado")
    assert stock(sucursal_a, "L1") == 7


def test_baja_no_deja_stock_negativo(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 5)
    lote = Lote.objects.get()
    with pytest.raises(StockInsuficiente):
        services.registrar_baja(usuario=regente, sucursal_id=sucursal_a.id, lote_id=lote.id, cantidad=6, motivo="x")


def test_ajuste_registra_diferencia_con_signo(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    lote = Lote.objects.get()
    services.ajustar_stock(usuario=regente, sucursal_id=sucursal_a.id, lote_id=lote.id, cantidad_real=7, motivo="Conteo")
    mov = MovimientoKardex.objects.filter(tipo=TipoMovimiento.AJUSTE).get()
    assert (mov.cantidad, mov.saldo) == (-3, 7)


# ---------------------------------------------------------- inalterabilidad

def test_kardex_no_se_puede_modificar_ni_borrar_desde_django(regente, sucursal_a, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    mov = MovimientoKardex.objects.get()
    mov.cantidad = 999
    with pytest.raises(KardexInalterable):
        mov.save()
    with pytest.raises(KardexInalterable):
        mov.delete()
    with pytest.raises(KardexInalterable):
        MovimientoKardex.objects.all().update(cantidad=1)
    with pytest.raises(KardexInalterable):
        MovimientoKardex.objects.all().delete()


def test_trigger_de_postgres_rechaza_update_y_delete(regente, sucursal_a, producto, dias):
    from django.db import DatabaseError, transaction

    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    with pytest.raises(DatabaseError):
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute("UPDATE inventory_movimientokardex SET cantidad = 5")
    with pytest.raises(DatabaseError):
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute("DELETE FROM inventory_movimientokardex")
    assert MovimientoKardex.objects.get().cantidad == 10


# ---------------------------------------------------------------- traspasos

def _traspaso(regente, a, b, producto, dias):
    ingresar(regente, a, producto, "L1", dias(100), 40)
    lote = Lote.objects.get()
    traspaso = services.crear_traspaso(
        usuario=regente, origen_id=a.id, destino_id=b.id,
        items=[{"lote": lote.id, "cantidad": 15}],
    )
    return traspaso, lote


def test_traspaso_descuenta_origen_al_enviar(regente, sucursal_a, sucursal_b, producto, dias):
    traspaso, _ = _traspaso(regente, sucursal_a, sucursal_b, producto, dias)
    assert traspaso.estado == EstadoTraspaso.ENVIADO
    assert stock(sucursal_a, "L1") == 25
    assert not StockLote.objects.filter(sucursal=sucursal_b).exists()


def test_recepcion_completa_suma_al_destino(regente, sucursal_a, sucursal_b, producto, dias):
    traspaso, _ = _traspaso(regente, sucursal_a, sucursal_b, producto, dias)
    services.recibir_traspaso(usuario=regente, traspaso_id=traspaso.id)
    assert stock(sucursal_b, "L1") == 15
    traspaso.refresh_from_db()
    assert traspaso.estado == EstadoTraspaso.RECIBIDO


def test_recepcion_con_diferencia_exige_observacion(regente, sucursal_a, sucursal_b, producto, dias):
    traspaso, _ = _traspaso(regente, sucursal_a, sucursal_b, producto, dias)
    item = traspaso.items.get()
    with pytest.raises(ErrorNegocio):
        services.recibir_traspaso(usuario=regente, traspaso_id=traspaso.id, recibidos={item.id: 10})
    # la transaccion se revirtio: nada llego al destino y sigue enviado
    assert not StockLote.objects.filter(sucursal=sucursal_b).exists()
    services.recibir_traspaso(
        usuario=regente, traspaso_id=traspaso.id, recibidos={item.id: 10}, observacion="Faltaron 5"
    )
    assert stock(sucursal_b, "L1") == 10
    item.refresh_from_db()
    assert item.diferencia == 5


def test_rechazo_devuelve_stock_al_origen(regente, sucursal_a, sucursal_b, producto, dias):
    traspaso, _ = _traspaso(regente, sucursal_a, sucursal_b, producto, dias)
    services.rechazar_traspaso(usuario=regente, traspaso_id=traspaso.id, observacion="Caja danada")
    assert stock(sucursal_a, "L1") == 40
    traspaso.refresh_from_db()
    assert traspaso.estado == EstadoTraspaso.RECHAZADO


def test_traspaso_resuelto_no_se_puede_resolver_dos_veces(regente, sucursal_a, sucursal_b, producto, dias):
    traspaso, _ = _traspaso(regente, sucursal_a, sucursal_b, producto, dias)
    services.recibir_traspaso(usuario=regente, traspaso_id=traspaso.id)
    with pytest.raises(ErrorNegocio):
        services.recibir_traspaso(usuario=regente, traspaso_id=traspaso.id)


def test_traspaso_no_acepta_lotes_vencidos(regente, sucursal_a, sucursal_b, producto, dias):
    ingresar(regente, sucursal_a, producto, "L1", dias(100), 10)
    lote = Lote.objects.get()
    Lote.objects.filter(pk=lote.pk).update(fecha_vencimiento=dias(-1))
    with pytest.raises(ErrorNegocio):
        services.crear_traspaso(
            usuario=regente, origen_id=sucursal_a.id, destino_id=sucursal_b.id,
            items=[{"lote": lote.id, "cantidad": 1}],
        )


def test_almacenero_sin_acceso_a_la_sucursal_no_puede_ingresar(almacenero, sucursal_b, producto, dias):
    from rest_framework.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        ingresar(almacenero, sucursal_b, producto, "L1", dias(100), 10)


# -------------------------------------------------------------- concurrencia

@pytest.mark.django_db(transaction=True)
def test_ventas_concurrentes_no_sobrevenden(regente, sucursal_a, producto, dias):
    """6 hilos intentan vender 30 de un stock de 100: solo 3 pueden tener exito."""
    import threading

    from django.db import transaction

    ingresar(regente, sucursal_a, producto, "L1", dias(100), 100)
    resultados = []

    def vender_30():
        try:
            with transaction.atomic():
                services.descontar_fefo(
                    usuario=regente, sucursal_id=sucursal_a.id, producto_id=producto.id,
                    cantidad=30, tipo=TipoMovimiento.VENTA,
                )
            resultados.append("ok")
        except StockInsuficiente:
            resultados.append("sin_stock")
        finally:
            connection.close()

    hilos = [threading.Thread(target=vender_30) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados.count("ok") == 3
    assert resultados.count("sin_stock") == 3
    assert stock(sucursal_a, "L1") == 10
    assert MovimientoKardex.objects.filter(tipo=TipoMovimiento.VENTA).count() == 3
