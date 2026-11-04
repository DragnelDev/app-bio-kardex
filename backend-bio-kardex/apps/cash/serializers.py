from rest_framework import serializers

from .models import Caja, TurnoCaja


class CajaSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)

    class Meta:
        model = Caja
        fields = ["id", "sucursal", "sucursal_nombre", "nombre", "activa"]
        read_only_fields = ["id"]


class TurnoCajaSerializer(serializers.ModelSerializer):
    caja_nombre = serializers.CharField(source="caja.nombre", read_only=True)
    sucursal = serializers.IntegerField(source="caja.sucursal_id", read_only=True)
    cajero_nombre = serializers.CharField(source="cajero.username", read_only=True)
    abierto = serializers.BooleanField(read_only=True)

    class Meta:
        model = TurnoCaja
        fields = [
            "id", "caja", "caja_nombre", "sucursal", "cajero", "cajero_nombre",
            "abierto_en", "cerrado_en", "abierto", "fondo_inicial",
            "efectivo_esperado", "qr_esperado", "efectivo_contado", "qr_contado",
            "diferencia_efectivo", "diferencia_qr", "observaciones",
        ]


class AbrirTurnoEntrada(serializers.Serializer):
    caja = serializers.IntegerField()
    fondo_inicial = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class CerrarTurnoEntrada(serializers.Serializer):
    efectivo_contado = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    qr_contado = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, default=0)
    observaciones = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
