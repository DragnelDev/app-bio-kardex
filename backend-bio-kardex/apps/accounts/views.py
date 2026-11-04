from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import EsAdmin

from .models import Usuario
from .serializers import LoginSerializer, UsuarioAdminSerializer, UsuarioSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(APIView):
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.prefetch_related("sucursales").order_by("username")
    serializer_class = UsuarioAdminSerializer
    permission_classes = [EsAdmin]
