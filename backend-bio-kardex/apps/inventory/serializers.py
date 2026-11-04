from datetime import timedelta

from django.conf import settings
from rest_framework import serializers

from apps.catalog.models import Presentacion
from apps.core.utils import hoy

from .models import MovimientoKardex, StockLote, Traspaso, TraspasoItem


def estado_lote(stock: StockLote) -> str:
    """vencido | bloqueado | por_vencer | ok  (vencido tiene prioridad)."""
    fecha = stock.lote.fecha_vencimiento
    if fecha < hoy():
        return "vencido"
    if stock.bloqueado:
        return "bloqueado"
    if fecha <= hoy() + timedelta(days=settings.DIAS_ALERTA_VENCIMIENTO):
        return "por_vencer"
    return "ok"


class StockLoteSerializer(serializers.ModelSerializer):
    lote_id = serializers.IntegerField(source="lote.id", read_only=True)
    numero_lote = serializers.CharField(source="lote.numero", read_only=True)
    fecha_vencimiento = serializers.DateField(source="lote.fecha_vencimiento", read_only=True)
    producto_id = serializers.IntegerField(source="lote.producto_id", read_only=True)
    producto = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()
    dias_para_vencer = serializers.SerializerMethodField()

    class Meta:
        model = StockLote
        fields = [
            "id", "sucursal", "lote_id", "numero_lote", "fecha_vencimiento",
            "producto_id", "producto", "cantidad", "bloqueado", "estado", "dias_para_vencer",
        ]

    def get_producto(self, obj):
        return str(obj.lote.producto)

    def get_estado(self, obj):
        return estado_lote(obj)

    def get_dias_para_vencer(self, obj):
        return (obj.lote.fecha_vencimiento - hoy()).days


class MovimientoKardexSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    numero_lote = serializers.CharField(source="lote.numero", read_only=True)
    producto = serializers.SerializerMethodField()
    usuario_nombre = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = MovimientoKardex
        fields = [
            "id", "sucursal", "lote", "numero_lote", "producto", "tipo", "tipo_display",
            "cantidad", "saldo", "usuario", "usuario_nombre",
            "referencia_tipo", "referencia_id", "motivo", "creado_en",
        ]

    def get_producto(self, obj):
        return str(obj.lote.producto)


class TraspasoItemSerializer(serializers.ModelSerializer):
    numero_lote = serializers.CharField(source="lote.numero", read_only=True)
    producto = serializers.SerializerMethodField()
    fecha_vencimiento = serializers.DateField(source="lote.fecha_vencimiento", read_only=True)
    diferencia = serializers.IntegerField(read_only=True)

    class Meta:
        model = TraspasoItem
        fields = [
            "id", "lote", "numero_lote", "producto", "fecha_vencimiento",
            "cantidad_enviada", "cantidad_recibida", "diferencia",
        ]

    def get_producto(self, obj):
        return str(obj.lote.producto)


class TraspasoSerializer(serializers.ModelSerializer):
    items = TraspasoItemSerializer(many=True, read_only=True)
    origen_nombre = serializers.CharField(source="origen.nombre", read_only=True)
    destino_nombre = serializers.CharField(source="destino.nombre", read_only=True)
    creado_por_nombre = serializers.CharField(source="creado_por.username", read_only=True)

    class Meta:
        model = Traspaso
        fields = [
            "id", "origen", "origen_nombre", "destino", "destino_nombre", "estado",
            "creado_por", "creado_por_nombre", "resuelto_por", "resuelto_en",
            "observacion", "observacion_recepcion", "creado_en", "items",
        ]


# ------------------------------------------------------------- entradas

class IngresoEntrada(serializers.Serializer):
    sucursal = serializers.IntegerField()
    presentacion = serializers.PrimaryKeyRelatedField(queryset=Presentacion.objects.select_related("producto"))
    cantidad = serializers.IntegerField(min_value=1, help_text="En unidades de la presentacion.")
    numero_lote = serializers.CharField(max_length=60)
    fecha_vencimiento = serializers.DateField()
    costo_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, min_value=0,
        help_text="Costo total de lo ingresado; se convierte a costo por unidad base.",
    )


class BajaEntrada(serializers.Serializer):
    sucursal = serializers.IntegerField()
    lote = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1, help_text="En unidades base.")
    motivo = serializers.CharField(max_length=255)


class AjusteEntrada(serializers.Serializer):
    sucursal = serializers.IntegerField()
    lote = serializers.IntegerField()
    cantidad_real = serializers.IntegerField(min_value=0, help_text="En unidades base.")
    motivo = serializers.CharField(max_length=255)


class BloqueoEntrada(serializers.Serializer):
    sucursal = serializers.IntegerField()
    lote = serializers.IntegerField()
    bloqueado = serializers.BooleanField()


class TraspasoItemEntrada(serializers.Serializer):
    lote = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1, help_text="En unidades base.")


class TraspasoEntrada(serializers.Serializer):
    origen = serializers.IntegerField()
    destino = serializers.IntegerField()
    observacion = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    items = TraspasoItemEntrada(many=True, allow_empty=False)


class RecepcionItemEntrada(serializers.Serializer):
    item = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=0)


class RecepcionEntrada(serializers.Serializer):
    items = RecepcionItemEntrada(many=True, required=False)
    observacion = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class RechazoEntrada(serializers.Serializer):
    observacion = serializers.CharField(max_length=255)
