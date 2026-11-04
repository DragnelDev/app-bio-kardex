from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Q, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Producto
from apps.core.permissions import TieneRol
from apps.core.utils import hoy, sucursal_de_consulta, sucursales_visibles_ids

from . import services
from .models import MovimientoKardex, StockLote, Traspaso
from .serializers import (
    AjusteEntrada,
    BajaEntrada,
    BloqueoEntrada,
    IngresoEntrada,
    MovimientoKardexSerializer,
    RechazoEntrada,
    RecepcionEntrada,
    StockLoteSerializer,
    TraspasoEntrada,
    TraspasoSerializer,
)

PUEDE_MOVER_STOCK = TieneRol.con("regente", "almacenero")
PUEDE_CORREGIR_STOCK = TieneRol.con("regente")  # bajas, ajustes y bloqueos


def _stock_visible(request):
    sucursal = request.query_params.get("sucursal")
    if sucursal:
        return StockLote.objects.filter(sucursal_id=sucursal_de_consulta(request))
    return StockLote.objects.filter(sucursal_id__in=sucursales_visibles_ids(request.user))


class StockView(APIView):
    """GET /api/inventario/stock/?sucursal=&producto=&q=&estado=&con_stock=1"""

    def get(self, request):
        qs = _stock_visible(request).select_related("lote", "lote__producto")
        p = request.query_params
        if p.get("producto"):
            qs = qs.filter(lote__producto_id=p["producto"])
        if p.get("q"):
            q = p["q"].strip()
            qs = qs.filter(
                Q(lote__producto__nombre_comercial__icontains=q)
                | Q(lote__producto__principio_activo__nombre__icontains=q)
                | Q(lote__numero__icontains=q)
            )
        if p.get("con_stock", "1") in ("1", "true"):
            qs = qs.filter(cantidad__gt=0)
        qs = qs.order_by("lote__fecha_vencimiento", "lote_id")

        paginador = PageNumberPagination()
        paginador.page_size = 50
        pagina = paginador.paginate_queryset(qs, request)
        datos = StockLoteSerializer(pagina, many=True).data
        if p.get("estado"):
            datos = [d for d in datos if d["estado"] == p["estado"]]
        return paginador.get_paginated_response(datos)


class ResumenStockView(APIView):
    """Stock total vendible por producto en una sucursal (para detectar bajo minimo)."""

    def get(self, request):
        sucursal_id = sucursal_de_consulta(request)
        filas = (
            StockLote.objects.filter(
                sucursal_id=sucursal_id, cantidad__gt=0, bloqueado=False,
                lote__fecha_vencimiento__gte=hoy(),
            )
            .values("lote__producto_id")
            .annotate(total=Sum("cantidad"))
        )
        totales = {f["lote__producto_id"]: f["total"] for f in filas}
        bajos = []
        for producto in Producto.objects.filter(activo=True, stock_minimo__gt=0):
            total = totales.get(producto.id, 0)
            if total <= producto.stock_minimo:
                bajos.append(
                    {"producto_id": producto.id, "producto": str(producto),
                     "stock": total, "stock_minimo": producto.stock_minimo}
                )
        return Response({"bajo_minimo": bajos})


class AlertasView(APIView):
    """Lotes vencidos con stock y lotes por vencer en los proximos N dias."""

    def get(self, request):
        qs = _stock_visible(request).select_related("lote", "lote__producto").filter(cantidad__gt=0)
        limite = hoy() + timedelta(days=settings.DIAS_ALERTA_VENCIMIENTO)
        vencidos = qs.filter(lote__fecha_vencimiento__lt=hoy()).order_by("lote__fecha_vencimiento")
        por_vencer = qs.filter(
            lote__fecha_vencimiento__gte=hoy(), lote__fecha_vencimiento__lte=limite
        ).order_by("lote__fecha_vencimiento")
        return Response(
            {
                "dias_alerta": settings.DIAS_ALERTA_VENCIMIENTO,
                "vencidos": StockLoteSerializer(vencidos[:200], many=True).data,
                "por_vencer": StockLoteSerializer(por_vencer[:200], many=True).data,
            }
        )


class IngresoView(APIView):
    permission_classes = [PUEDE_MOVER_STOCK]

    def post(self, request):
        s = IngresoEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        presentacion = d["presentacion"]
        base = d["cantidad"] * presentacion.factor
        costo_unitario = None
        if d.get("costo_total") is not None:
            costo_unitario = (d["costo_total"] / Decimal(base)).quantize(Decimal("0.0001"))
        stock = services.registrar_ingreso(
            usuario=request.user, sucursal_id=d["sucursal"],
            producto_id=presentacion.producto_id, numero_lote=d["numero_lote"],
            fecha_vencimiento=d["fecha_vencimiento"], cantidad=base, costo_unitario=costo_unitario,
        )
        return Response(StockLoteSerializer(stock).data, status=status.HTTP_201_CREATED)


class BajaView(APIView):
    permission_classes = [PUEDE_CORREGIR_STOCK]

    def post(self, request):
        s = BajaEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        stock = services.registrar_baja(
            usuario=request.user, sucursal_id=d["sucursal"], lote_id=d["lote"],
            cantidad=d["cantidad"], motivo=d["motivo"],
        )
        return Response(StockLoteSerializer(stock).data)


class AjusteView(APIView):
    permission_classes = [PUEDE_CORREGIR_STOCK]

    def post(self, request):
        s = AjusteEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        stock = services.ajustar_stock(
            usuario=request.user, sucursal_id=d["sucursal"], lote_id=d["lote"],
            cantidad_real=d["cantidad_real"], motivo=d["motivo"],
        )
        return Response(StockLoteSerializer(stock).data)


class BloqueoView(APIView):
    permission_classes = [PUEDE_CORREGIR_STOCK]

    def post(self, request):
        s = BloqueoEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        stock = services.cambiar_bloqueo(
            usuario=request.user, sucursal_id=d["sucursal"], lote_id=d["lote"],
            bloqueado=d["bloqueado"],
        )
        return Response(StockLoteSerializer(stock).data)


class KardexView(APIView):
    """GET /api/inventario/kardex/?sucursal=&producto=&lote=&tipo=&desde=&hasta="""

    def get(self, request):
        p = request.query_params
        if p.get("sucursal"):
            qs = MovimientoKardex.objects.filter(sucursal_id=sucursal_de_consulta(request))
        else:
            qs = MovimientoKardex.objects.filter(sucursal_id__in=sucursales_visibles_ids(request.user))
        qs = qs.select_related("lote", "lote__producto", "usuario")
        if p.get("producto"):
            qs = qs.filter(lote__producto_id=p["producto"])
        if p.get("lote"):
            qs = qs.filter(lote_id=p["lote"])
        if p.get("tipo"):
            qs = qs.filter(tipo=p["tipo"])
        if p.get("desde"):
            qs = qs.filter(creado_en__date__gte=p["desde"])
        if p.get("hasta"):
            qs = qs.filter(creado_en__date__lte=p["hasta"])
        paginador = PageNumberPagination()
        paginador.page_size = 50
        pagina = paginador.paginate_queryset(qs, request)
        return paginador.get_paginated_response(MovimientoKardexSerializer(pagina, many=True).data)


class TraspasoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = TraspasoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        ids = sucursales_visibles_ids(self.request.user)
        qs = (
            Traspaso.objects.filter(Q(origen_id__in=ids) | Q(destino_id__in=ids))
            .select_related("origen", "destino", "creado_por")
            .prefetch_related("items__lote__producto")
        )
        p = self.request.query_params
        if p.get("estado"):
            qs = qs.filter(estado=p["estado"])
        if p.get("sucursal"):
            qs = qs.filter(Q(origen_id=p["sucursal"]) | Q(destino_id=p["sucursal"]))
        return qs

    def create(self, request):
        if not PUEDE_MOVER_STOCK().has_permission(request, self):
            self.permission_denied(request)
        s = TraspasoEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        traspaso = services.crear_traspaso(
            usuario=request.user, origen_id=d["origen"], destino_id=d["destino"],
            items=d["items"], observacion=d["observacion"],
        )
        return Response(TraspasoSerializer(traspaso).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recibir(self, request, pk=None):
        if not PUEDE_MOVER_STOCK().has_permission(request, self):
            self.permission_denied(request)
        s = RecepcionEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        recibidos = {i["item"]: i["cantidad"] for i in d.get("items", [])}
        traspaso = services.recibir_traspaso(
            usuario=request.user, traspaso_id=int(pk), recibidos=recibidos,
            observacion=d["observacion"],
        )
        return Response(TraspasoSerializer(traspaso).data)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        if not PUEDE_MOVER_STOCK().has_permission(request, self):
            self.permission_denied(request)
        s = RechazoEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        traspaso = services.rechazar_traspaso(
            usuario=request.user, traspaso_id=int(pk), observacion=s.validated_data["observacion"]
        )
        return Response(TraspasoSerializer(traspaso).data)
