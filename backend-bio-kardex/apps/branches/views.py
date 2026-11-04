from rest_framework import viewsets

from apps.core.permissions import EsAdminOSoloLectura

from .models import Sucursal
from .serializers import SucursalSerializer


class SucursalViewSet(viewsets.ModelViewSet):
    """Admin: CRUD completo. Resto de roles: solo ven sus sucursales asignadas."""

    serializer_class = SucursalSerializer
    permission_classes = [EsAdminOSoloLectura]

    def get_queryset(self):
        user = self.request.user
        qs = Sucursal.objects.all()
        if user.es_admin:
            return qs
        return qs.filter(usuarios=user)
