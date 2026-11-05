from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cash.models import Caja
from apps.cash.services import abrir_turno
from apps.inventory import services as inv
from apps.sales import services as ventas

pytestmark = pytest.mark.django_db


def api(usuario):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(usuario).access_token}")
    return c


@pytest.fixture
def escenario(regente, cajero, sucursal_a, producto, pres, dias):
    inv.registrar_ingreso(
        usuario=regente, sucursal_id=sucursal_a.id, producto_id=producto.id, numero_lote="L1",
        fecha_vencimiento=dias(200), cantidad=300, costo_unitario=Decimal("0.5000"),
    )
    caja = Caja.objects.create(sucursal=sucursal_a, nombre="Caja 1")
    abrir_turno(usuario=cajero, caja_id=caja.id, fondo_inicial=Decimal("0"))
    for cantidad, monto, metodo in ((2, "48.00", "efectivo"), (1, "24.00", "qr")):
        ventas.crear_venta(
            usuario=cajero,
            datos={
                "sucursal": sucursal_a.id,
                "items": [{"presentacion": pres["caja"].id, "cantidad": cantidad}],
                "pagos": [{"metodo": metodo, "monto": Decimal(monto)}],
            },
        )


def test_reporte_de_ventas_resume_y_agrupa(regente, sucursal_a, escenario):
    resp = api(regente).get("/api/reportes/ventas/", {"sucursal": sucursal_a.id})
    assert resp.status_code == 200, resp.data
    assert resp.data["resumen"]["ventas"] == 2
    assert resp.data["resumen"]["total"] == Decimal("72.00")
    assert resp.data["resumen"]["ticket_promedio"] == Decimal("36.00")
    metodos = {m["metodo"]: m["total"] for m in resp.data["por_metodo"]}
    assert metodos == {"efectivo": Decimal("48.00"), "qr": Decimal("24.00")}
    assert resp.data["top_productos"][0]["unidades_base"] == 90


def test_reporte_de_ventas_csv(regente, sucursal_a, escenario):
    resp = api(regente).get("/api/reportes/ventas/", {"sucursal": sucursal_a.id, "formato": "csv"})
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    lineas = resp.content.decode("utf-8-sig").strip().splitlines()
    assert lineas[0].startswith("Numero;Fecha")
    assert len(lineas) == 3  # cabecera + 2 ventas


def test_valorizado_usa_el_costo_del_lote(regente, sucursal_a, escenario):
    resp = api(regente).get("/api/reportes/valorizado/", {"sucursal": sucursal_a.id})
    # quedan 300 - 90 = 210 tabletas a Bs 0.50
    assert resp.data["productos"][0]["cantidad"] == 210
    assert resp.data["total"] == Decimal("105.00")
    assert resp.data["lotes_sin_costo"] == 0


def test_libro_de_controlados_solo_incluye_controlados(regente, cajero, sucursal_a, producto, pres, escenario):
    assert api(regente).get("/api/reportes/controlados/", {"sucursal": sucursal_a.id}).data["registros"] == []

    producto.es_controlado = True
    producto.save()
    ventas.crear_venta(
        usuario=cajero,
        datos={
            "sucursal": sucursal_a.id,
            "items": [{"presentacion": pres["blister"].id, "cantidad": 1}],
            "pagos": [{"metodo": "qr", "monto": Decimal("9.00")}],
            "receta_numero": "R-77", "medico": "Dr. Quispe",
            "cliente": {"tipo_documento": "ci", "numero_documento": "998877", "razon_social": "Luis Mamani"},
        },
    )
    registros = api(regente).get("/api/reportes/controlados/", {"sucursal": sucursal_a.id}).data["registros"]
    assert len(registros) == 1
    assert (registros[0]["receta"], registros[0]["medico"], registros[0]["cantidad_base"]) == ("R-77", "Dr. Quispe", 10)


def test_cajero_no_accede_a_reportes(cajero, sucursal_a):
    assert api(cajero).get("/api/reportes/ventas/", {"sucursal": sucursal_a.id}).status_code == 403


def test_rango_invalido_devuelve_400(regente, sucursal_a):
    resp = api(regente).get(
        "/api/reportes/ventas/", {"sucursal": sucursal_a.id, "desde": "2026-02-10", "hasta": "2026-02-01"}
    )
    assert resp.status_code == 400
