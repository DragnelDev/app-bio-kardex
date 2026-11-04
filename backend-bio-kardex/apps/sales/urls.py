from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("ventas", views.VentaViewSet, basename="venta")
router.register("clientes", views.ClienteViewSet, basename="cliente")

urlpatterns = [path("pos/buscar/", views.BuscarPOSView.as_view())] + router.urls
