from rest_framework.permissions import SAFE_METHODS, BasePermission


class TieneRol(BasePermission):
    """Permite el acceso solo a usuarios cuyo rol este en `roles_permitidos`.

    El rol administrador siempre pasa. Uso:

        class MiVista(APIView):
            permission_classes = [TieneRol.con("regente", "almacenero")]
    """

    roles_permitidos: tuple[str, ...] = ()

    @classmethod
    def con(cls, *roles: str):
        return type("TieneRolConfigurado", (cls,), {"roles_permitidos": roles})

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return user.es_admin or user.rol in self.roles_permitidos


class EsAdminOSoloLectura(BasePermission):
    """Lectura para cualquier usuario autenticado; escritura solo administrador."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.es_admin


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.es_admin)
