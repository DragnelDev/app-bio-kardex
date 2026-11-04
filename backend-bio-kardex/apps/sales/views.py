from django.db.models import Min, Q, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import PrecioSucursal, Producto
from apps.core.permissions import TieneRol
from apps.core.utils import hoy, sucursal_de_consulta, sucursales_visibles_ids
from apps.inventory.models import StockLote

from . import services
from .models import Cliente, Venta
from .serializers import (
    AnulacionEntrada,
    ClienteSerializer,
    DevolucionEntrada,
    DevolucionSerializer,
    VentaEntrada,
    VentaListaSerializer,
    VentaSerializer,
)

PUEDE_VENDER = TieneRol.con("cajero", "regente")


class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer
    permission_classes = [PUEDE_VENDER]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = Cliente.objects.order_by("razon_social")
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(numero_documento__icontains=q) | Q(razon_social__icontains=q))
        return qs


class VentaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return VentaListaSerializer if self.action == "list" else VentaSerializer

    def get_queryset(self):
        qs = (
            Venta.objects.filter(sucursal_id__in=sucursales_visibles_ids(self.request.user))
            .select_related("sucursal", "cajero")
            .prefetch_related("items__lotes__lote", "items__producto", "items__presentacion", "pagos")
        )
        user = self.request.user
        if not (user.es_admin or user.rol == "regente"):
            qs = qs.filter(cajero=user)
        p = self.request.query_params
        if p.get("sucursal"):
            qs = qs.filter(sucursal_id=p["sucursal"])
        if p.get("estado"):
            qs = qs.filter(estado=p["estado"])
        if p.get("turno"):
            qs = qs.filter(turno_id=p["turno"])
        if p.get("numero"):
            qs = qs.filter(numero=p["numero"])
        if p.get("desde"):
            qs = qs.filter(creado_en__date__gte=p["desde"])
        if p.get("hasta"):
            qs = qs.filter(creado_en__date__lte=p["hasta"])
        return qs

    def create(self, request):
        if not PUEDE_VENDER().has_permission(request, self):
            self.permission_denied(request)
        s = VentaEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        venta = services.crear_venta(usuario=request.user, datos=s.validated_data)
        return Response(
            VentaSerializer(venta, context={"request": request}).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        s = AnulacionEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        venta = services.anular_venta(usuario=request.user, venta_id=int(pk), motivo=s.validated_data["motivo"])
        return Response(VentaSerializer(venta, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def devolucion(self, request, pk=None):
        s = DevolucionEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        devolucion = services.registrar_devolucion(
            usuario=request.user, venta_id=int(pk), items=d["items"], motivo=d["motivo"],
            metodo_reembolso=d["metodo_reembolso"],
        )
        return Response(DevolucionSerializer(devolucion).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def receta(self, request, pk=None):
        """Adjunta la foto de la receta (multipart, campo `receta`)."""
        if not PUEDE_VENDER().has_permission(request, self):
            self.permission_denied(request)
        venta = self.get_object()
        archivo = request.FILES.get("receta")
        if archivo is None:
            return Response({"receta": "Adjunta una imagen."}, status=status.HTTP_400_BAD_REQUEST)
        venta.receta = archivo
        venta.save(update_fields=["receta"])
        return Response(VentaSerializer(venta, context={"request": request}).data)


class BuscarPOSView(APIView):
    """GET /api/pos/buscar/?sucursal=&q=  Busqueda rapida con stock vendible en tiempo real."""

    permission_classes = [PUEDE_VENDER]

    def get(self, request):
        sucursal_id = sucursal_de_consulta(request)
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])

        productos = list(
            Producto.objects.filter(activo=True)
            .filter(
                Q(nombre_comercial__icontains=q)
                | Q(principio_activo__nombre__icontains=q)
                | Q(codigo_barras=q)
                | Q(presentaciones__codigo_barras=q)
            )
            .select_related("principio_activo", "forma")
            .prefetch_related("presentaciones")
            .distinct()[:20]
        )
        ids = [p.id for p in productos]
        stock = {
            f["lote__producto_id"]: f
            for f in StockLote.objects.filter(
                sucursal_id=sucursal_id, lote__producto_id__in=ids, cantidad__gt=0,
                bloqueado=False, lote__fecha_vencimiento__gte=hoy(),
            )
            .values("lote__producto_id")
            .annotate(total=Sum("cantidad"), proximo=Min("lote__fecha_vencimiento"))
        }
        especificos = {
            (ps.presentacion_id): ps.precio
            for ps in PrecioSucursal.objects.filter(
                sucursal_id=sucursal_id, presentacion__producto_id__in=ids
            )
        }
        resultado = []
        for p in productos:
            s = stock.get(p.id)
            total = s["total"] if s else 0
            resultado.append(
                {
                    "id": p.id,
                    "nombre": p.nombre_comercial,
                    "concentracion": p.concentracion,
                    "forma": p.forma.nombre,
                    "principio_activo": p.principio_activo.nombre,
                    "laboratorio": p.laboratorio,
                    "imagen": request.build_absolute_uri(p.imagen.url) if p.imagen else None,
                    "es_controlado": p.es_controlado,
                    "requiere_receta": p.requiere_receta,
                    "unidad_base": p.unidad_base,
                    "stock_base": total,
                    "proximo_vencimiento": s["proximo"] if s else None,
                    "presentaciones": [
                        {
                            "id": x.id,
                            "nivel": x.nivel,
                            "nombre": x.nombre or x.get_nivel_display(),
                            "factor": x.factor,
                            "precio": str(especificos.get(x.id, x.precio)),
                            "codigo_barras": x.codigo_barras,
                            "disponible": total // x.factor,
                        }
                        for x in p.presentaciones.all()
                        if x.activa
                    ],
                }
            )
        return Response(resultado)
