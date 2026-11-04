from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import EscrituraPorRoles, TieneRol
from apps.core.utils import sucursal_de_consulta, sucursales_visibles_ids

from . import services
from .models import Caja, TurnoCaja
from .serializers import (
    AbrirTurnoEntrada,
    CajaSerializer,
    CerrarTurnoEntrada,
    TurnoCajaSerializer,
)

PUEDE_COBRAR = TieneRol.con("cajero", "regente")


class CajaViewSet(viewsets.ModelViewSet):
    serializer_class = CajaSerializer
    permission_classes = [EscrituraPorRoles.con("regente")]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = Caja.objects.select_related("sucursal").filter(
            sucursal_id__in=sucursales_visibles_ids(self.request.user)
        )
        sucursal = self.request.query_params.get("sucursal")
        return qs.filter(sucursal_id=sucursal) if sucursal else qs


class TurnoCajaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = TurnoCajaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TurnoCaja.objects.select_related("caja", "cajero").filter(
            caja__sucursal_id__in=sucursales_visibles_ids(self.request.user)
        )
        user = self.request.user
        if not (user.es_admin or user.rol == "regente"):
            qs = qs.filter(cajero=user)
        p = self.request.query_params
        if p.get("sucursal"):
            qs = qs.filter(caja__sucursal_id=p["sucursal"])
        if p.get("abierto") in ("1", "true"):
            qs = qs.filter(cerrado_en__isnull=True)
        return qs

    def create(self, request):
        """Abre un turno."""
        if not PUEDE_COBRAR().has_permission(request, self):
            self.permission_denied(request)
        s = AbrirTurnoEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        turno = services.abrir_turno(
            usuario=request.user, caja_id=s.validated_data["caja"],
            fondo_inicial=s.validated_data["fondo_inicial"],
        )
        return Response(TurnoCajaSerializer(turno).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def actual(self, request):
        """Turno abierto del usuario en la sucursal, con los totales en vivo."""
        sucursal_id = sucursal_de_consulta(request)
        turno = (
            TurnoCaja.objects.select_related("caja", "cajero")
            .filter(cajero=request.user, caja__sucursal_id=sucursal_id, cerrado_en__isnull=True)
            .first()
        )
        if turno is None:
            return Response({"turno": None})
        return Response(
            {"turno": TurnoCajaSerializer(turno).data, "totales": services.calcular_totales(turno)}
        )

    @action(detail=True, methods=["get"])
    def totales(self, request, pk=None):
        return Response(services.calcular_totales(self.get_object()))

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        if not PUEDE_COBRAR().has_permission(request, self):
            self.permission_denied(request)
        s = CerrarTurnoEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        turno = services.cerrar_turno(usuario=request.user, turno_id=int(pk), **s.validated_data)
        return Response(
            {"turno": TurnoCajaSerializer(turno).data, "totales": services.calcular_totales(turno)}
        )
