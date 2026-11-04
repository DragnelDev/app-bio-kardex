from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Rol
from apps.core.exceptions import ErrorNegocio
from apps.core.utils import exigir_sucursal, redondear

from .models import Caja, TurnoCaja

CERO = Decimal("0.00")


def calcular_totales(turno: TurnoCaja) -> dict:
    """Totales del turno. Excluye ventas anuladas y descuenta devoluciones."""
    from apps.payments.models import Metodo, Pago
    from apps.sales.models import Devolucion, EstadoVenta, MetodoReembolso

    pagos = {
        f["metodo"]: f["total"]
        for f in Pago.objects.filter(venta__turno=turno, venta__estado=EstadoVenta.COMPLETADA)
        .values("metodo")
        .annotate(total=Sum("monto"))
    }
    devoluciones = {
        f["metodo_reembolso"]: f["total"]
        for f in Devolucion.objects.filter(turno=turno)
        .values("metodo_reembolso")
        .annotate(total=Sum("monto_total"))
    }
    ventas_efectivo = pagos.get(Metodo.EFECTIVO, CERO)
    ventas_qr = pagos.get(Metodo.QR, CERO)
    dev_efectivo = devoluciones.get(MetodoReembolso.EFECTIVO, CERO)
    dev_qr = devoluciones.get(MetodoReembolso.QR, CERO)
    return {
        "fondo_inicial": turno.fondo_inicial,
        "ventas_efectivo": ventas_efectivo,
        "ventas_qr": ventas_qr,
        "devoluciones_efectivo": dev_efectivo,
        "devoluciones_qr": dev_qr,
        "efectivo_esperado": turno.fondo_inicial + ventas_efectivo - dev_efectivo,
        "qr_esperado": ventas_qr - dev_qr,
    }


@transaction.atomic
def abrir_turno(*, usuario, caja_id, fondo_inicial):
    try:
        caja = Caja.objects.select_related("sucursal").get(pk=caja_id, activa=True)
    except Caja.DoesNotExist:
        raise ErrorNegocio("La caja no existe o esta inactiva.", "no_encontrado")
    exigir_sucursal(usuario, caja.sucursal_id)
    fondo = redondear(fondo_inicial)
    if fondo < 0:
        raise ErrorNegocio("El fondo inicial no puede ser negativo.")
    try:
        with transaction.atomic():
            return TurnoCaja.objects.create(caja=caja, cajero=usuario, fondo_inicial=fondo)
    except IntegrityError:
        if TurnoCaja.objects.filter(caja=caja, cerrado_en__isnull=True).exists():
            raise ErrorNegocio("Esta caja ya tiene un turno abierto.", "caja_ocupada")
        raise ErrorNegocio("Ya tienes un turno abierto. Cierralo antes de abrir otro.", "turno_abierto")


@transaction.atomic
def cerrar_turno(*, usuario, turno_id, efectivo_contado, qr_contado, observaciones=""):
    """Cierra el turno y registra el arqueo (efectivo fisico y QR por separado)."""
    try:
        turno = TurnoCaja.objects.select_for_update().select_related("caja").get(pk=turno_id)
    except TurnoCaja.DoesNotExist:
        raise ErrorNegocio("El turno no existe.", "no_encontrado")
    if not turno.abierto:
        raise ErrorNegocio("El turno ya esta cerrado.", "turno_cerrado")
    exigir_sucursal(usuario, turno.caja.sucursal_id)
    es_supervisor = usuario.es_admin or usuario.rol == Rol.REGENTE
    if turno.cajero_id != usuario.id and not es_supervisor:
        raise ErrorNegocio("Solo el cajero del turno o un supervisor puede cerrarlo.", "sin_permiso")

    totales = calcular_totales(turno)
    efectivo = redondear(efectivo_contado)
    qr = redondear(qr_contado)
    if efectivo < 0 or qr < 0:
        raise ErrorNegocio("Los montos contados no pueden ser negativos.")

    turno.efectivo_esperado = redondear(totales["efectivo_esperado"])
    turno.qr_esperado = redondear(totales["qr_esperado"])
    turno.efectivo_contado = efectivo
    turno.qr_contado = qr
    turno.diferencia_efectivo = efectivo - turno.efectivo_esperado
    turno.diferencia_qr = qr - turno.qr_esperado
    turno.observaciones = observaciones or ""
    turno.cerrado_en = timezone.now()
    turno.save()
    return turno
