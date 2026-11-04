from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.cash.models import Caja
from apps.cash.services import abrir_turno, calcular_totales, cerrar_turno
from apps.core.exceptions import ErrorNegocio, StockInsuficiente
from apps.inventory import services as inv
from apps.inventory.models import MovimientoKardex, StockLote
from apps.sales import services
from apps.sales.models import EstadoVenta

pytestmark = pytest.mark.django_db


@pytest.fixture
def caja(sucursal_a):
    return Caja.objects.create(sucursal=sucursal_a, nombre="Caja 1")


@pytest.fixture
def turno(cajero, caja):
    return abrir_turno(usuario=cajero, caja_id=caja.id, fondo_inicial=Decimal("100"))


@pytest.fixture
def con_stock(regente, sucursal_a, producto, dias):
    """Dos lotes de 100 tabletas: PRONTO vence antes que TARDE."""
    for numero, d in (("TARDE", dias(400)), ("PRONTO", dias(100))):
        inv.registrar_ingreso(
            usuario=regente, sucursal_id=sucursal_a.id, producto_id=producto.id,
            numero_lote=numero, fecha_vencimiento=d, cantidad=100,
        )


def datos(sucursal, pres, items, pagos, **extra):
    return {
        "sucursal": sucursal.id,
        "items": [{"presentacion": pres[n].id, "cantidad": c} for n, c in items],
        "pagos": pagos,
        **extra,
    }


def stock(sucursal, numero):
    return StockLote.objects.get(sucursal=sucursal, lote__numero=numero).cantidad


# ------------------------------------------------------------------ ventas

def test_venta_fraccionada_descuenta_proporcional_y_calcula_vuelto(
    cajero, sucursal_a, pres, turno, con_stock
):
    # 1 caja (30) + 1 blister (10) + 2 unidades = 42 tabletas; 24 + 9 + 2 = 35.00
    venta = services.crear_venta(
        usuario=cajero,
        datos=datos(
            sucursal_a, pres, [("caja", 1), ("blister", 1), ("unidad", 2)],
            [{"metodo": "efectivo", "monto": Decimal("35.00"), "recibido": Decimal("50.00")}],
        ),
    )
    assert venta.total == Decimal("35.00")
    assert venta.vuelto == Decimal("15.00")
    assert venta.iva == Decimal("4.03")  # 35 * 13 / 113
    assert venta.numero == 1
    assert stock(sucursal_a, "PRONTO") == 100 - 42  # FEFO: sale del lote que vence antes
    assert stock(sucursal_a, "TARDE") == 100


def test_venta_cruza_lotes_y_registra_kardex_por_lote(cajero, sucursal_a, pres, turno, con_stock):
    # 4 cajas = 120 tabletas: 100 del lote PRONTO + 20 del TARDE
    venta = services.crear_venta(
        usuario=cajero,
        datos=datos(sucursal_a, pres, [("caja", 4)], [{"metodo": "qr", "monto": Decimal("96.00")}]),
    )
    assert stock(sucursal_a, "PRONTO") == 0
    assert stock(sucursal_a, "TARDE") == 80
    movs = MovimientoKardex.objects.filter(referencia_tipo="venta", referencia_id=venta.id)
    assert sorted(m.cantidad for m in movs) == [-100, -20]
    assert all(m.usuario == cajero for m in movs)


def test_venta_con_pago_mixto(cajero, sucursal_a, pres, turno, con_stock):
    venta = services.crear_venta(
        usuario=cajero,
        datos=datos(
            sucursal_a, pres, [("caja", 2)],  # 48.00
            [
                {"metodo": "efectivo", "monto": Decimal("20.00"), "recibido": Decimal("20.00")},
                {"metodo": "qr", "monto": Decimal("28.00"), "referencia": "TX-123"},
            ],
        ),
    )
    assert {p.metodo for p in venta.pagos.all()} == {"efectivo", "qr"}
    assert venta.vuelto == 0


def test_pagos_deben_cuadrar_con_el_total(cajero, sucursal_a, pres, turno, con_stock):
    with pytest.raises(ErrorNegocio) as exc:
        services.crear_venta(
            usuario=cajero,
            datos=datos(sucursal_a, pres, [("caja", 1)], [{"metodo": "efectivo", "monto": Decimal("10.00")}]),
        )
    assert exc.value.codigo == "pagos_no_cuadran"
    assert stock(sucursal_a, "PRONTO") == 100  # nada se descuenta si falla


def test_efectivo_recibido_no_puede_ser_menor_al_monto(cajero, sucursal_a, pres, turno, con_stock):
    with pytest.raises(ErrorNegocio):
        services.crear_venta(
            usuario=cajero,
            datos=datos(
                sucursal_a, pres, [("caja", 1)],
                [{"metodo": "efectivo", "monto": Decimal("24.00"), "recibido": Decimal("20.00")}],
            ),
        )


def test_sin_stock_no_vende_y_no_deja_rastro(cajero, sucursal_a, pres, turno, con_stock):
    with pytest.raises(StockInsuficiente):
        services.crear_venta(
            usuario=cajero,
            datos=datos(sucursal_a, pres, [("caja", 7)], [{"metodo": "qr", "monto": Decimal("168.00")}]),
        )
    assert stock(sucursal_a, "PRONTO") == 100
    assert stock(sucursal_a, "TARDE") == 100
    from apps.sales.models import Venta

    assert Venta.objects.count() == 0


def test_no_se_vende_sin_turno_abierto(cajero, sucursal_a, pres, con_stock):
    with pytest.raises(ErrorNegocio) as exc:
        services.crear_venta(
            usuario=cajero,
            datos=datos(sucursal_a, pres, [("unidad", 1)], [{"metodo": "qr", "monto": Decimal("1.00")}]),
        )
    assert exc.value.codigo == "sin_turno"


def test_cajero_no_puede_dar_descuento(
    cajero, regente, sucursal_a, pres, turno, con_stock, caja
):
    base = datos(
        sucursal_a, pres, [("caja", 1)], [{"metodo": "qr", "monto": Decimal("20.00")}],
        descuento=Decimal("4.00"),
    )
    with pytest.raises(ErrorNegocio):
        services.crear_venta(usuario=cajero, datos=base)


def test_referencia_cliente_hace_idempotente_el_reintento(cajero, sucursal_a, pres, turno, con_stock):
    import uuid

    ref = uuid.uuid4()
    d = datos(
        sucursal_a, pres, [("unidad", 1)], [{"metodo": "qr", "monto": Decimal("1.00")}],
        referencia_cliente=ref,
    )
    v1 = services.crear_venta(usuario=cajero, datos=d)
    v2 = services.crear_venta(usuario=cajero, datos=d)
    assert v1.id == v2.id
    assert stock(sucursal_a, "PRONTO") == 99


def test_producto_controlado_exige_receta_medico_y_cliente(cajero, sucursal_a, pres, producto, turno, con_stock):
    producto.es_controlado = True
    producto.save()
    pago = [{"metodo": "qr", "monto": Decimal("24.00")}]
    with pytest.raises(ErrorNegocio) as exc:
        services.crear_venta(usuario=cajero, datos=datos(sucursal_a, pres, [("caja", 1)], pago))
    assert exc.value.codigo == "receta_requerida"
    with pytest.raises(ErrorNegocio) as exc:
        services.crear_venta(
            usuario=cajero, datos=datos(sucursal_a, pres, [("caja", 1)], pago, receta_numero="R-1")
        )
    assert exc.value.codigo == "medico_requerido"
    venta = services.crear_venta(
        usuario=cajero,
        datos=datos(
            sucursal_a, pres, [("caja", 1)], pago, receta_numero="R-1", medico="Dr. Perez",
            cliente={"tipo_documento": "ci", "numero_documento": "1234567", "razon_social": "Ana Rojas"},
        ),
    )
    assert venta.documento_cliente == "1234567"


def test_precio_especifico_de_sucursal_reemplaza_al_base(cajero, sucursal_a, pres, turno, con_stock):
    from apps.catalog.models import PrecioSucursal

    PrecioSucursal.objects.create(presentacion=pres["caja"], sucursal=sucursal_a, precio=Decimal("30.00"))
    venta = services.crear_venta(
        usuario=cajero,
        datos=datos(sucursal_a, pres, [("caja", 1)], [{"metodo": "qr", "monto": Decimal("30.00")}]),
    )
    assert venta.total == Decimal("30.00")


# ---------------------------------------------------- anulacion y devolucion

def _venta_simple(cajero, sucursal_a, pres):
    return services.crear_venta(
        usuario=cajero,
        datos=datos(sucursal_a, pres, [("caja", 1)], [{"metodo": "efectivo", "monto": Decimal("24.00")}]),
    )


def test_anular_devuelve_stock_y_excluye_la_venta_de_la_caja(
    cajero, regente, sucursal_a, pres, caja, con_stock
):
    # el regente abre su propio turno para poder anular; la venta es del turno del cajero
    turno = abrir_turno(usuario=cajero, caja_id=caja.id, fondo_inicial=Decimal("0"))
    venta = _venta_simple(cajero, sucursal_a, pres)
    assert stock(sucursal_a, "PRONTO") == 70
    anulada = services.anular_venta(usuario=regente, venta_id=venta.id, motivo="Error de cobro")
    assert anulada.estado == EstadoVenta.ANULADA
    assert stock(sucursal_a, "PRONTO") == 100
    assert calcular_totales(turno)["ventas_efectivo"] == 0


def test_cajero_no_puede_anular(cajero, sucursal_a, pres, turno, con_stock):
    venta = _venta_simple(cajero, sucursal_a, pres)
    with pytest.raises(ErrorNegocio) as exc:
        services.anular_venta(usuario=cajero, venta_id=venta.id, motivo="x")
    assert exc.value.codigo == "sin_permiso"


def test_no_se_anula_si_el_turno_ya_cerro(cajero, regente, sucursal_a, pres, turno, con_stock):
    venta = _venta_simple(cajero, sucursal_a, pres)
    cerrar_turno(usuario=cajero, turno_id=turno.id, efectivo_contado=Decimal("124.00"), qr_contado=Decimal("0"))
    with pytest.raises(ErrorNegocio) as exc:
        services.anular_venta(usuario=regente, venta_id=venta.id, motivo="x")
    assert exc.value.codigo == "turno_cerrado"


def test_devolucion_parcial_repone_al_mismo_lote_y_resta_de_caja(
    cajero, regente, sucursal_a, sucursal_b, pres, caja, con_stock
):
    from apps.cash.models import Caja

    turno_cajero = abrir_turno(usuario=cajero, caja_id=caja.id, fondo_inicial=Decimal("0"))
    venta = _venta_simple(cajero, sucursal_a, pres)  # 30 tabletas del lote PRONTO por 24.00
    asignacion = venta.items.get().lotes.get()
    # el regente atiende la devolucion en su propio turno
    caja2 = Caja.objects.create(sucursal=sucursal_a, nombre="Caja 2")
    turno_reg = abrir_turno(usuario=regente, caja_id=caja2.id, fondo_inicial=Decimal("0"))
    dev = services.registrar_devolucion(
        usuario=regente, venta_id=venta.id,
        items=[{"venta_item_lote": asignacion.id, "cantidad": 15}],
        motivo="Cliente se arrepintio", metodo_reembolso="efectivo",
    )
    assert dev.monto_total == Decimal("12.00")  # mitad de la caja
    assert stock(sucursal_a, "PRONTO") == 85
    assert calcular_totales(turno_reg)["efectivo_esperado"] == Decimal("-12.00")
    assert calcular_totales(turno_cajero)["efectivo_esperado"] == Decimal("24.00")


def test_no_se_devuelve_mas_de_lo_vendido(cajero, regente, sucursal_a, pres, caja, con_stock):
    from apps.cash.models import Caja

    abrir_turno(usuario=cajero, caja_id=caja.id, fondo_inicial=Decimal("0"))
    venta = _venta_simple(cajero, sucursal_a, pres)
    asignacion = venta.items.get().lotes.get()
    caja2 = Caja.objects.create(sucursal=sucursal_a, nombre="Caja 2")
    abrir_turno(usuario=regente, caja_id=caja2.id, fondo_inicial=Decimal("0"))
    items = [{"venta_item_lote": asignacion.id, "cantidad": 20}]
    services.registrar_devolucion(
        usuario=regente, venta_id=venta.id, items=items, motivo="a", metodo_reembolso="efectivo"
    )
    with pytest.raises(ErrorNegocio) as exc:
        services.registrar_devolucion(
            usuario=regente, venta_id=venta.id, items=items, motivo="b", metodo_reembolso="efectivo"
        )
    assert exc.value.codigo == "cantidad_invalida"


# --------------------------------------------------------------------- caja

def test_arqueo_separa_efectivo_y_qr(cajero, sucursal_a, pres, turno, con_stock):
    services.crear_venta(
        usuario=cajero,
        datos=datos(
            sucursal_a, pres, [("caja", 2)],  # 48.00
            [
                {"metodo": "efectivo", "monto": Decimal("20.00"), "recibido": Decimal("50.00")},
                {"metodo": "qr", "monto": Decimal("28.00")},
            ],
        ),
    )
    totales = calcular_totales(turno)
    assert totales["efectivo_esperado"] == Decimal("120.00")  # fondo 100 + 20 (el vuelto no cuenta)
    assert totales["qr_esperado"] == Decimal("28.00")

    cerrado = cerrar_turno(
        usuario=cajero, turno_id=turno.id, efectivo_contado=Decimal("118.00"), qr_contado=Decimal("28.00")
    )
    assert cerrado.diferencia_efectivo == Decimal("-2.00")
    assert cerrado.diferencia_qr == Decimal("0.00")
    assert not cerrado.abierto


def test_solo_un_turno_abierto_por_caja_y_por_cajero(cajero, regente, caja, turno):
    with pytest.raises(ErrorNegocio) as exc:
        abrir_turno(usuario=regente, caja_id=caja.id, fondo_inicial=Decimal("0"))
    assert exc.value.codigo == "caja_ocupada"
    otra = Caja.objects.create(sucursal=caja.sucursal, nombre="Caja 2")
    with pytest.raises(ErrorNegocio) as exc:
        abrir_turno(usuario=cajero, caja_id=otra.id, fondo_inicial=Decimal("0"))
    assert exc.value.codigo == "turno_abierto"


# ---------------------------------------------------------------------- API

def _cliente_api(usuario):
    from rest_framework_simplejwt.tokens import RefreshToken

    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(usuario).access_token}")
    return c


def test_api_flujo_completo_de_venta(cajero, sucursal_a, pres, producto, turno, con_stock):
    api = _cliente_api(cajero)

    busqueda = api.get("/api/pos/buscar/", {"sucursal": sucursal_a.id, "q": "parace"})
    assert busqueda.status_code == 200
    assert busqueda.data[0]["stock_base"] == 200
    assert {p["nivel"] for p in busqueda.data[0]["presentaciones"]} == {"caja", "blister", "unidad"}

    resp = api.post(
        "/api/ventas/",
        {
            "sucursal": sucursal_a.id,
            "items": [{"presentacion": pres["blister"].id, "cantidad": 2}],
            "pagos": [{"metodo": "efectivo", "monto": "18.00", "recibido": "20.00"}],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["total"] == "18.00"
    assert resp.data["vuelto"] == "2.00"
    assert resp.data["items"][0]["lotes"][0]["numero_lote"] == "PRONTO"


def test_api_stock_insuficiente_devuelve_400_con_detalle(cajero, sucursal_a, pres, turno, con_stock):
    resp = _cliente_api(cajero).post(
        "/api/ventas/",
        {
            "sucursal": sucursal_a.id,
            "items": [{"presentacion": pres["caja"].id, "cantidad": 100}],
            "pagos": [{"metodo": "qr", "monto": "2400.00"}],
        },
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["code"] == "stock_insuficiente"


def test_almacenero_no_puede_vender_por_api(almacenero, sucursal_a, pres, con_stock):
    resp = _cliente_api(almacenero).post(
        "/api/ventas/",
        {
            "sucursal": sucursal_a.id,
            "items": [{"presentacion": pres["unidad"].id, "cantidad": 1}],
            "pagos": [{"metodo": "qr", "monto": "1.00"}],
        },
        format="json",
    )
    assert resp.status_code == 403
