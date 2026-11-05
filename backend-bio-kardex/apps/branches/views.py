from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import EsAdminOSoloLectura

from .models import Sucursal
from .serializers import SucursalSerializer


class SucursalViewSet(viewsets.ModelViewSet):
    """Admin: crea y edita. Resto de roles: solo ven sus sucursales asignadas."""

    serializer_class = SucursalSerializer
    permission_classes = [EsAdminOSoloLectura]
    # Las sucursales tienen stock y ventas: se desactivan (activa=false), no se borran.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Sucursal.objects.all()
        if user.es_admin:
            return qs
        return qs.filter(usuarios=user)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def destinos(self, request):
        """Todas las sucursales activas (para elegir destino de un traspaso)."""
        datos = Sucursal.objects.filter(activa=True).values("id", "codigo", "nombre")
        return Response(list(datos))
