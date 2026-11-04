from rest_framework import serializers

from .models import Sucursal


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = [
            "id",
            "codigo",
            "nombre",
            "direccion",
            "ciudad",
            "telefono",
            "es_casa_matriz",
            "activa",
        ]
        read_only_fields = ["id"]
