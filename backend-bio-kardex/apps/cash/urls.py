from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("cajas", views.CajaViewSet, basename="caja")
router.register("turnos", views.TurnoCajaViewSet, basename="turno")

urlpatterns = router.urls
