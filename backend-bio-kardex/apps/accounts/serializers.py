from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.branches.serializers import SucursalSerializer

from .models import Rol, Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """Lectura del usuario autenticado (endpoint /me)."""

    sucursales = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "rol",
            "ci",
            "telefono",
            "sucursales",
        ]
        read_only_fields = fields

    def get_sucursales(self, obj):
        """El administrador opera en todas las sucursales activas."""
        from apps.branches.models import Sucursal

        qs = Sucursal.objects.filter(activa=True) if obj.es_admin else obj.sucursales.all()
        return SucursalSerializer(qs, many=True).data


class UsuarioAdminSerializer(serializers.ModelSerializer):
    """CRUD de usuarios por el administrador."""

    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "rol",
            "ci",
            "telefono",
            "sucursales",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_rol(self, value):
        if value not in Rol.values:
            raise serializers.ValidationError("Rol invalido.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "La contrasena es obligatoria al crear un usuario."}
            )
        # Un administrador no puede quitarse a si mismo el acceso ni el rol.
        request = self.context.get("request")
        if self.instance is not None and request and request.user.pk == self.instance.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError(
                    {"is_active": "No puedes desactivar tu propio usuario."}
                )
            if "rol" in attrs and attrs["rol"] != self.instance.rol:
                raise serializers.ValidationError({"rol": "No puedes cambiar tu propio rol."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        sucursales = validated_data.pop("sucursales", [])
        user = Usuario(**validated_data)
        user.set_password(password)
        user.save()
        user.sucursales.set(sucursales)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        sucursales = validated_data.pop("sucursales", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if sucursales is not None:
            instance.sucursales.set(sucursales)
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    """Devuelve ademas del par de tokens los datos del usuario."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["rol"] = user.rol
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = UsuarioSerializer(self.user).data
        return data


class CambiarClaveEntrada(serializers.Serializer):
    clave_actual = serializers.CharField(write_only=True)
    clave_nueva = serializers.CharField(write_only=True)

    def validate_clave_actual(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("La contrasena actual es incorrecta.")
        return value

    def validate_clave_nueva(self, value):
        validate_password(value, self.context["request"].user)
        return value
