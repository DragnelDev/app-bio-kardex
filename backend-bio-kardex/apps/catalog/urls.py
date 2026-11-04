from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("principios-activos", views.PrincipioActivoViewSet, basename="principio-activo")
router.register("formas-farmaceuticas", views.FormaFarmaceuticaViewSet, basename="forma")
router.register("productos", views.ProductoViewSet, basename="producto")
router.register("presentaciones", views.PresentacionViewSet, basename="presentacion")
router.register("precios-sucursal", views.PrecioSucursalViewSet, basename="precio-sucursal")

urlpatterns = router.urls
