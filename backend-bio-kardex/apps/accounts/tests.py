from django.core.management import call_command, CommandError
from django.test import override_settings
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Rol, Usuario
from apps.branches.models import Sucursal

pytestmark = pytest.mark.django_db


@pytest.fixture
def sucursales():
    return (
        Sucursal.objects.create(codigo="CEN", nombre="Central", es_casa_matriz=True),
        Sucursal.objects.create(codigo="SUR", nombre="Sur"),
    )


@pytest.fixture
def admin(sucursales):
    return Usuario.objects.create_user("admin1", password="Clave-Segura-123", rol=Rol.ADMIN)


@pytest.fixture
def cajero(sucursales):
    u = Usuario.objects.create_user("caja1", password="Clave-Segura-123", rol=Rol.CAJERO)
    u.sucursales.add(sucursales[0])
    return u


def login(username, password="Clave-Segura-123"):
    client = APIClient()
    resp = client.post("/api/auth/login/", {"username": username, "password": password})
    return client, resp


def autenticado(username):
    client, resp = login(username)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return client


def test_login_devuelve_tokens_y_usuario(cajero):
    _, resp = login("caja1")
    assert resp.status_code == 200
    assert {"access", "refresh", "usuario"} <= set(resp.data)
    assert resp.data["usuario"]["rol"] == Rol.CAJERO
    assert [s["codigo"] for s in resp.data["usuario"]["sucursales"]] == ["CEN"]


def test_login_con_clave_incorrecta_falla(cajero):
    _, resp = login("caja1", "mala")
    assert resp.status_code == 401


def test_me_requiere_autenticacion():
    assert APIClient().get("/api/auth/me/").status_code == 401


def test_me_devuelve_usuario_actual(cajero):
    resp = autenticado("caja1").get("/api/auth/me/")
    assert resp.status_code == 200
    assert resp.data["username"] == "caja1"


def test_refresh_devuelve_nuevo_access(cajero):
    client, resp = login("caja1")
    r = client.post("/api/auth/refresh/", {"refresh": resp.data["refresh"]})
    assert r.status_code == 200
    assert "access" in r.data


def test_cajero_solo_ve_sus_sucursales(cajero):
    resp = autenticado("caja1").get("/api/sucursales/")
    assert resp.status_code == 200
    assert [s["codigo"] for s in resp.data["results"]] == ["CEN"]


def test_admin_ve_todas_las_sucursales(admin):
    resp = autenticado("admin1").get("/api/sucursales/")
    assert len(resp.data["results"]) == 2


def test_cajero_no_puede_crear_sucursal(cajero):
    resp = autenticado("caja1").post(
        "/api/sucursales/", {"codigo": "X", "nombre": "X"}
    )
    assert resp.status_code == 403


def test_admin_crea_usuario_con_sucursales(admin, sucursales):
    resp = autenticado("admin1").post(
        "/api/auth/usuarios/",
        {
            "username": "alm1",
            "password": "Clave-Segura-123",
            "rol": Rol.ALMACENERO,
            "sucursales": [sucursales[1].id],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    nuevo = Usuario.objects.get(username="alm1")
    assert nuevo.check_password("Clave-Segura-123")
    assert nuevo.puede_operar_en(sucursales[1].id)
    assert not nuevo.puede_operar_en(sucursales[0].id)


def test_cajero_no_gestiona_usuarios(cajero):
    assert autenticado("caja1").get("/api/auth/usuarios/").status_code == 403


@override_settings(
    DEBUG=True,
    DEV_ADMIN_USERNAME="devadmin",
    DEV_ADMIN_EMAIL="devadmin@example.com",
    DEV_ADMIN_PASSWORD="Desarrollo-Seguro-123!",
)
def test_create_dev_admin_crea_superusuario():
    call_command("create_dev_admin")

    admin = Usuario.objects.get(username="devadmin")
    assert admin.is_superuser
    assert admin.is_staff
    assert admin.rol == Rol.ADMIN
    assert admin.email == "devadmin@example.com"
    assert admin.check_password("Desarrollo-Seguro-123!")


@override_settings(
    DEBUG=True,
    DEV_ADMIN_USERNAME="devadmin",
    DEV_ADMIN_EMAIL="devadmin@example.com",
    DEV_ADMIN_PASSWORD="Desarrollo-Seguro-123!",
)
def test_create_dev_admin_no_cambia_un_superusuario_existente():
    admin = Usuario.objects.create_superuser(
        username="devadmin",
        email="devadmin@example.com",
        password="Otra-Clave-Segura-456!",
        rol=Rol.ADMIN,
    )

    call_command("create_dev_admin")

    admin.refresh_from_db()
    assert admin.check_password("Otra-Clave-Segura-456!")
    assert Usuario.objects.filter(username="devadmin").count() == 1


@override_settings(DEBUG=False)
def test_create_dev_admin_no_se_ejecuta_fuera_de_desarrollo():
    with pytest.raises(CommandError, match="DEBUG=True"):
        call_command("create_dev_admin")


@override_settings(DEBUG=True, DEV_ADMIN_PASSWORD="")
def test_create_dev_admin_requiere_password_configurado():
    with pytest.raises(CommandError, match="DEV_ADMIN_PASSWORD"):
        call_command("create_dev_admin")


# ------------------------------------------------- gestion desde la app

def test_admin_no_puede_desactivarse_ni_cambiar_su_propio_rol(admin):
    api = autenticado("admin1")
    r = api.patch(f"/api/auth/usuarios/{admin.id}/", {"is_active": False}, format="json")
    assert r.status_code == 400
    r = api.patch(f"/api/auth/usuarios/{admin.id}/", {"rol": Rol.CAJERO}, format="json")
    assert r.status_code == 400
    admin.refresh_from_db()
    assert admin.is_active and admin.rol == Rol.ADMIN


def test_admin_puede_desactivar_a_otro_usuario(admin, cajero):
    r = autenticado("admin1").patch(f"/api/auth/usuarios/{cajero.id}/", {"is_active": False}, format="json")
    assert r.status_code == 200
    cajero.refresh_from_db()
    assert not cajero.is_active
    _, resp = login("caja1")
    assert resp.status_code == 401


def test_usuarios_y_sucursales_no_se_borran(admin, cajero, sucursales):
    api = autenticado("admin1")
    assert api.delete(f"/api/auth/usuarios/{cajero.id}/").status_code == 405
    assert api.delete(f"/api/sucursales/{sucursales[0].id}/").status_code == 405


def test_admin_filtra_usuarios_por_rol(admin, cajero):
    r = autenticado("admin1").get("/api/auth/usuarios/", {"rol": Rol.CAJERO})
    assert [u["username"] for u in r.data["results"]] == ["caja1"]


def test_admin_crea_y_desactiva_sucursal(admin):
    api = autenticado("admin1")
    r = api.post("/api/sucursales/", {"codigo": "NOR", "nombre": "Norte"}, format="json")
    assert r.status_code == 201
    r = api.patch(f"/api/sucursales/{r.data['id']}/", {"activa": False}, format="json")
    assert r.status_code == 200 and r.data["activa"] is False


def test_usuario_cambia_su_propia_clave(cajero):
    api = autenticado("caja1")
    r = api.post(
        "/api/auth/cambiar-clave/",
        {"clave_actual": "Clave-Segura-123", "clave_nueva": "Nueva-Clave-456"},
        format="json",
    )
    assert r.status_code == 204
    assert login("caja1", "Nueva-Clave-456")[1].status_code == 200
    assert login("caja1")[1].status_code == 401


def test_cambiar_clave_exige_la_actual_correcta(cajero):
    r = autenticado("caja1").post(
        "/api/auth/cambiar-clave/",
        {"clave_actual": "incorrecta", "clave_nueva": "Nueva-Clave-456"},
        format="json",
    )
    assert r.status_code == 400
    assert login("caja1")[1].status_code == 200
