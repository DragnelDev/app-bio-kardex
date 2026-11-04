from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Rol, Usuario
from apps.branches.models import Sucursal
from apps.catalog.models import (
    FormaFarmaceutica,
    Nivel,
    Presentacion,
    PrincipioActivo,
    Producto,
)

CLAVE = "Clave-Segura-123"


@pytest.fixture
def sucursal_a(db):
    return Sucursal.objects.create(codigo="CEN", nombre="Central", es_casa_matriz=True)


@pytest.fixture
def sucursal_b(db):
    return Sucursal.objects.create(codigo="SUR", nombre="Sur")


def _usuario(username, rol, sucursales):
    u = Usuario.objects.create_user(username, password=CLAVE, rol=rol)
    u.sucursales.set(sucursales)
    return u


@pytest.fixture
def admin(sucursal_a, sucursal_b):
    return _usuario("admin1", Rol.ADMIN, [])


@pytest.fixture
def regente(sucursal_a, sucursal_b):
    return _usuario("reg1", Rol.REGENTE, [sucursal_a, sucursal_b])


@pytest.fixture
def almacenero(sucursal_a):
    return _usuario("alm1", Rol.ALMACENERO, [sucursal_a])


@pytest.fixture
def cajero(sucursal_a):
    return _usuario("caja1", Rol.CAJERO, [sucursal_a])


@pytest.fixture
def producto(db):
    """Paracetamol: caja = 30 unidades, blister = 10, unidad = 1."""
    p = Producto.objects.create(
        nombre_comercial="Paracetamol",
        principio_activo=PrincipioActivo.objects.create(nombre="Paracetamol"),
        concentracion="500 mg",
        forma=FormaFarmaceutica.objects.create(nombre="Tableta"),
        unidad_base="tableta",
    )
    Presentacion.objects.create(producto=p, nivel=Nivel.CAJA, factor=30, precio=Decimal("24.00"))
    Presentacion.objects.create(producto=p, nivel=Nivel.BLISTER, factor=10, precio=Decimal("9.00"))
    Presentacion.objects.create(producto=p, nivel=Nivel.UNIDAD, factor=1, precio=Decimal("1.00"))
    return p


@pytest.fixture
def pres(producto):
    return {x.nivel: x for x in producto.presentaciones.all()}


@pytest.fixture
def dias():
    """Fecha de vencimiento a N dias desde hoy."""
    return lambda n: timezone.localdate() + timedelta(days=n)
