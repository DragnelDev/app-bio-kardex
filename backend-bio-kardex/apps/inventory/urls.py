from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("traspasos", views.TraspasoViewSet, basename="traspaso")

urlpatterns = [
    path("inventario/stock/", views.StockView.as_view()),
    path("inventario/resumen/", views.ResumenStockView.as_view()),
    path("inventario/alertas/", views.AlertasView.as_view()),
    path("inventario/ingresos/", views.IngresoView.as_view()),
    path("inventario/bajas/", views.BajaView.as_view()),
    path("inventario/ajustes/", views.AjusteView.as_view()),
    path("inventario/bloqueos/", views.BloqueoView.as_view()),
    path("inventario/kardex/", views.KardexView.as_view()),
    path("inventario/", include(router.urls)),
]
