from django.db.models import Q
from rest_framework import viewsets

from apps.core.permissions import EscrituraPorRoles

from .models import (
    FormaFarmaceutica,
    PrecioSucursal,
    Presentacion,
    PrincipioActivo,
    Producto,
)
from .serializers import (
    FormaFarmaceuticaSerializer,
    PrecioSucursalSerializer,
    PresentacionSerializer,
    PrincipioActivoSerializer,
    ProductoSerializer,
)

PERMISO_CATALOGO = EscrituraPorRoles.con("regente", "almacenero")
SIN_BORRADO = ["get", "post", "put", "patch", "head", "options"]


def _como_bool(valor):
    return str(valor).lower() in ("1", "true", "si", "yes")


class PrincipioActivoViewSet(viewsets.ModelViewSet):
    serializer_class = PrincipioActivoSerializer
    permission_classes = [PERMISO_CATALOGO]
    http_method_names = SIN_BORRADO

    def get_queryset(self):
        qs = PrincipioActivo.objects.all()
        q = self.request.query_params.get("q", "").strip()
        return qs.filter(nombre__icontains=q) if q else qs


class FormaFarmaceuticaViewSet(viewsets.ModelViewSet):
    queryset = FormaFarmaceutica.objects.all()
    serializer_class = FormaFarmaceuticaSerializer
    permission_classes = [PERMISO_CATALOGO]
    http_method_names = SIN_BORRADO


class ProductoViewSet(viewsets.ModelViewSet):
    """Los productos no se borran: se desactivan (`activo=false`)."""

    serializer_class = ProductoSerializer
    permission_classes = [PERMISO_CATALOGO]
    http_method_names = SIN_BORRADO

    def get_queryset(self):
        qs = Producto.objects.select_related("principio_activo", "forma").prefetch_related(
            "presentaciones"
        )
        params = self.request.query_params
        q = params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(nombre_comercial__icontains=q)
                | Q(principio_activo__nombre__icontains=q)
                | Q(codigo_barras=q)
                | Q(presentaciones__codigo_barras=q)
            ).distinct()
        if "activo" in params:
            qs = qs.filter(activo=_como_bool(params["activo"]))
        return qs


class PresentacionViewSet(viewsets.ModelViewSet):
    serializer_class = PresentacionSerializer
    permission_classes = [PERMISO_CATALOGO]
    http_method_names = SIN_BORRADO

    def get_queryset(self):
        qs = Presentacion.objects.select_related("producto")
        producto = self.request.query_params.get("producto")
        return qs.filter(producto_id=producto) if producto else qs


class PrecioSucursalViewSet(viewsets.ModelViewSet):
    serializer_class = PrecioSucursalSerializer
    permission_classes = [PERMISO_CATALOGO]

    def get_queryset(self):
        qs = PrecioSucursal.objects.all()
        params = self.request.query_params
        if params.get("presentacion"):
            qs = qs.filter(presentacion_id=params["presentacion"])
        if params.get("sucursal"):
            qs = qs.filter(sucursal_id=params["sucursal"])
        return qs
