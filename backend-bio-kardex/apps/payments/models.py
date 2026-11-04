from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Metodo(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    QR = "qr", "QR / Transferencia"


class Pago(models.Model):
    """Una parte del pago de una venta (las ventas admiten pagos mixtos).

    `monto` es lo aplicado a la venta; `recibido` es lo que entrego el cliente
    (solo difiere en efectivo). El vuelto es recibido - monto.
    """

    venta = models.ForeignKey("sales.Venta", on_delete=models.PROTECT, related_name="pagos")
    metodo = models.CharField(max_length=10, choices=Metodo.choices)
    monto = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    recibido = models.DecimalField(max_digits=12, decimal_places=2)
    referencia = models.CharField(max_length=80, blank=True, help_text="Referencia de la transaccion QR.")
    comprobante = models.ImageField(upload_to="comprobantes/", null=True, blank=True)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="pago_monto_positivo"),
            models.CheckConstraint(condition=Q(recibido__gte=F("monto")), name="pago_recibido_cubre_monto"),
        ]

    @property
    def vuelto(self) -> Decimal:
        return self.recibido - self.monto
