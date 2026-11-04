from rest_framework import serializers

from .models import (
    FormaFarmaceutica,
    Nivel,
    PrecioSucursal,
    Presentacion,
    PrincipioActivo,
    Producto,
)


class PrincipioActivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrincipioActivo
        fields = ["id", "nombre", "descripcion"]


class FormaFarmaceuticaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormaFarmaceutica
        fields = ["id", "nombre"]


class PresentacionSerializer(serializers.ModelSerializer):
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = Presentacion
        fields = [
            "id",
            "producto",
            "nivel",
            "nivel_display",
            "nombre",
            "factor",
            "precio",
            "codigo_barras",
            "activa",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        nivel = attrs.get("nivel", getattr(self.instance, "nivel", None))
        factor = attrs.get("factor", getattr(self.instance, "factor", None))
        if nivel == Nivel.UNIDAD and factor != 1:
            raise serializers.ValidationError(
                {"factor": "El nivel unidad debe tener factor 1."}
            )
        producto = attrs.get("producto", getattr(self.instance, "producto", None))
        if self.instance is not None and producto != self.instance.producto:
            raise serializers.ValidationError(
                {"producto": "No se puede cambiar el producto de una presentacion."}
            )
        return attrs


class ProductoSerializer(serializers.ModelSerializer):
    presentaciones = PresentacionSerializer(many=True, read_only=True)
    principio_activo_nombre = serializers.CharField(
        source="principio_activo.nombre", read_only=True
    )
    forma_nombre = serializers.CharField(source="forma.nombre", read_only=True)

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre_comercial",
            "principio_activo",
            "principio_activo_nombre",
            "concentracion",
            "forma",
            "forma_nombre",
            "laboratorio",
            "codigo_barras",
            "registro_sanitario",
            "es_controlado",
            "requiere_receta",
            "unidad_base",
            "stock_minimo",
            "imagen",
            "activo",
            "presentaciones",
        ]
        read_only_fields = ["id"]

    def validate_codigo_barras(self, value):
        return value or None


class PrecioSucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrecioSucursal
        fields = ["id", "presentacion", "sucursal", "precio"]
        read_only_fields = ["id"]
