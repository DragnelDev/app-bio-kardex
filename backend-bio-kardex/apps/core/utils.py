from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

CENTAVO = Decimal("0.01")


def redondear(valor) -> Decimal:
    """Redondea a 2 decimales (centavos de Boliviano), mitad hacia arriba."""
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def hoy():
    return timezone.localdate()


def sucursal_de_consulta(request, nombre="sucursal") -> int:
    """Lee el id de sucursal de la query y verifica que el usuario pueda operar en ella."""
    bruto = request.query_params.get(nombre)
    try:
        sucursal_id = int(bruto)
    except (TypeError, ValueError):
        raise ValidationError({nombre: "Indica la sucursal."})
    exigir_sucursal(request.user, sucursal_id)
    return sucursal_id


def exigir_sucursal(user, sucursal_id: int) -> None:
    if not user.puede_operar_en(sucursal_id):
        raise PermissionDenied("No tienes acceso a esta sucursal.")


def sucursales_visibles_ids(user):
    """Ids de las sucursales que el usuario puede consultar."""
    from apps.branches.models import Sucursal

    qs = Sucursal.objects.all()
    if not user.es_admin:
        qs = qs.filter(usuarios=user)
    return list(qs.values_list("id", flat=True))
