from django.db.models import Sum
from rest_framework import serializers

from apps.payments.models import Metodo, Pago

from .models import (
    Cliente,
    Devolucion,
    DevolucionItem,
    MetodoReembolso,
    TipoDocumento,
    Venta,
    VentaItem,
    VentaItemLote,
)


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ["id", "tipo_documento", "numero_documento", "razon_social", "email", "telefono"]
        read_only_fields = ["id"]


class PagoSerializer(serializers.ModelSerializer):
    vuelto = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    metodo_display = serializers.CharField(source="get_metodo_display", read_only=True)

    class Meta:
        model = Pago
        fields = ["id", "metodo", "metodo_display", "monto", "recibido", "vuelto", "referencia", "comprobante"]


class VentaItemLoteSerializer(serializers.ModelSerializer):
    numero_lote = serializers.CharField(source="lote.numero", read_only=True)
    fecha_vencimiento = serializers.DateField(source="lote.fecha_vencimiento", read_only=True)
    devuelta = serializers.SerializerMethodField()

    class Meta:
        model = VentaItemLote
        fields = ["id", "lote", "numero_lote", "fecha_vencimiento", "cantidad_base", "devuelta"]

    def get_devuelta(self, obj):
        return DevolucionItem.objects.filter(venta_item_lote=obj).aggregate(t=Sum("cantidad_base"))["t"] or 0


class VentaItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.SerializerMethodField()
    presentacion_nombre = serializers.SerializerMethodField()
    lotes = VentaItemLoteSerializer(many=True, read_only=True)

    class Meta:
        model = VentaItem
        fields = [
            "id", "producto", "producto_nombre", "presentacion", "presentacion_nombre",
            "cantidad", "factor", "cantidad_base", "precio_unitario", "subtotal", "lotes",
        ]

    def get_producto_nombre(self, obj):
        return str(obj.producto)

    def get_presentacion_nombre(self, obj):
        return obj.presentacion.nombre or obj.presentacion.get_nivel_display()


class VentaSerializer(serializers.ModelSerializer):
    items = VentaItemSerializer(many=True, read_only=True)
    pagos = PagoSerializer(many=True, read_only=True)
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    cajero_nombre = serializers.CharField(source="cajero.username", read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id", "numero", "sucursal", "sucursal_nombre", "turno", "cajero", "cajero_nombre",
            "nombre_cliente", "documento_cliente", "subtotal", "descuento", "total", "iva", "vuelto",
            "estado", "creado_en", "receta_numero", "medico", "receta",
            "anulada_en", "motivo_anulacion", "items", "pagos",
        ]


class VentaListaSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    cajero_nombre = serializers.CharField(source="cajero.username", read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id", "numero", "sucursal", "sucursal_nombre", "cajero_nombre", "nombre_cliente",
            "total", "estado", "creado_en",
        ]


class DevolucionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Devolucion
        fields = ["id", "venta", "motivo", "metodo_reembolso", "monto_total", "creado_en"]


# ------------------------------------------------------------- entradas

class ItemEntrada(serializers.Serializer):
    presentacion = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)


class PagoEntrada(serializers.Serializer):
    metodo = serializers.ChoiceField(choices=Metodo.choices)
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    recibido = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    referencia = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class ClienteEntrada(serializers.Serializer):
    tipo_documento = serializers.ChoiceField(choices=TipoDocumento.choices, required=False)
    numero_documento = serializers.CharField(max_length=30, required=False, allow_blank=True)
    razon_social = serializers.CharField(max_length=150, required=False, allow_blank=True)


class VentaEntrada(serializers.Serializer):
    sucursal = serializers.IntegerField()
    referencia_cliente = serializers.UUIDField(required=False)
    items = ItemEntrada(many=True, allow_empty=False)
    pagos = PagoEntrada(many=True, allow_empty=False)
    descuento = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, default=0)
    cliente = ClienteEntrada(required=False)
    receta_numero = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    medico = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class AnulacionEntrada(serializers.Serializer):
    motivo = serializers.CharField(max_length=255)


class DevolucionItemEntrada(serializers.Serializer):
    venta_item_lote = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1, help_text="En unidades base.")


class DevolucionEntrada(serializers.Serializer):
    items = DevolucionItemEntrada(many=True, allow_empty=False)
    motivo = serializers.CharField(max_length=255)
    metodo_reembolso = serializers.ChoiceField(choices=MetodoReembolso.choices, default=MetodoReembolso.EFECTIVO)
