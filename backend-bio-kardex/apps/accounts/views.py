from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import EsAdmin

from .models import Usuario
from .serializers import (
    CambiarClaveEntrada,
    LoginSerializer,
    UsuarioAdminSerializer,
    UsuarioSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(APIView):
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)


class CambiarClaveView(APIView):
    """Cualquier usuario autenticado cambia su propia contrasena."""

    def post(self, request):
        s = CambiarClaveEntrada(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        request.user.set_password(s.validated_data["clave_nueva"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuarioViewSet(viewsets.ModelViewSet):
    """Los usuarios no se borran (tienen historial): se desactivan con is_active=false."""

    serializer_class = UsuarioAdminSerializer
    permission_classes = [EsAdmin]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = Usuario.objects.prefetch_related("sucursales").order_by("username")
        p = self.request.query_params
        q = p.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(ci__icontains=q)
            )
        if p.get("rol"):
            qs = qs.filter(rol=p["rol"])
        if p.get("activo") in ("1", "true"):
            qs = qs.filter(is_active=True)
        elif p.get("activo") in ("0", "false"):
            qs = qs.filter(is_active=False)
        return qs
