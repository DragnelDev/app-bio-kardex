from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import ModeloBase


class Caja(ModeloBase):
    """Punto de cobro fisico de una sucursal."""

    sucursal = models.ForeignKey(
        "branches.Sucursal", on_delete=models.PROTECT, related_name="cajas"
    )
    nombre = models.CharField(max_length=60)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "cajas"
        ordering = ["sucursal_id", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["sucursal", "nombre"], name="caja_unica_por_sucursal")
        ]

    def __str__(self):
        return f"{self.sucursal.codigo} - {self.nombre}"


class TurnoCaja(ModeloBase):
    """Apertura de caja de un cajero, con fondo inicial y arqueo al cierre.

    El arqueo separa efectivo fisico y dinero digital (QR).
    """

    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name="turnos")
    cajero = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turnos_caja"
    )
    abierto_en = models.DateTimeField(default=timezone.now)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    fondo_inicial = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )

    efectivo_esperado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    qr_esperado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    efectivo_contado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    qr_contado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    diferencia_efectivo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    diferencia_qr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-abierto_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["caja"], condition=Q(cerrado_en__isnull=True), name="un_turno_abierto_por_caja"
            ),
            models.UniqueConstraint(
                fields=["cajero"], condition=Q(cerrado_en__isnull=True), name="un_turno_abierto_por_cajero"
            ),
        ]

    @property
    def abierto(self) -> bool:
        return self.cerrado_en is None
