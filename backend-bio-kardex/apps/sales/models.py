import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TipoDocumento(models.TextChoices):
    CI = "ci", "Cedula de identidad"
    NIT = "nit", "NIT"
    PASAPORTE = "pasaporte", "Pasaporte"
    OTRO = "otro", "Otro"


class Cliente(models.Model):
    tipo_documento = models.CharField(max_length=12, choices=TipoDocumento.choices, default=TipoDocumento.CI)
    numero_documento = models.CharField(max_length=30)
    razon_social = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "numero_documento"], name="cliente_documento_unico"
            )
        ]

    def __str__(self):
        return f"{self.razon_social} ({self.numero_documento})"


class EstadoVenta(models.TextChoices):
    COMPLETADA = "completada", "Completada"
    ANULADA = "anulada", "Anulada"


class Venta(models.Model):
    """Venta del POS. Los precios incluyen IVA; `iva` es el monto contenido en el total."""

    sucursal = models.ForeignKey("branches.Sucursal", on_delete=models.PROTECT, related_name="ventas")
    numero = models.PositiveIntegerField(help_text="Correlativo por sucursal.")
    turno = models.ForeignKey("cash.TurnoCaja", on_delete=models.PROTECT, related_name="ventas")
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="ventas")
    nombre_cliente = models.CharField(max_length=150, default="S/N")
    documento_cliente = models.CharField(max_length=30, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    vuelto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    estado = models.CharField(max_length=12, choices=EstadoVenta.choices, default=EstadoVenta.COMPLETADA)
    creado_en = models.DateTimeField(default=timezone.now, db_index=True)

    receta_numero = models.CharField(max_length=60, blank=True)
    medico = models.CharField(max_length=120, blank=True)
    receta = models.ImageField(upload_to="recetas/", null=True, blank=True)

    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="ventas_anuladas"
    )
    anulada_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=255, blank=True)

    # Idempotencia: el POS genera un UUID por venta para que un reintento no duplique.
    referencia_cliente = models.UUIDField(null=True, blank=True, unique=True, default=None)

    # Preparado para la facturacion del SIN (fase posterior)
    tipo_documento_fiscal = models.CharField(max_length=20, blank=True)
    numero_factura = models.PositiveBigIntegerField(null=True, blank=True)
    cuf = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["sucursal", "numero"], name="venta_numero_unico_por_sucursal"),
            models.CheckConstraint(condition=Q(total__gt=0), name="venta_total_positivo"),
        ]


class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    presentacion = models.ForeignKey("catalog.Presentacion", on_delete=models.PROTECT, related_name="+")
    producto = models.ForeignKey("catalog.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField(help_text="En unidades de la presentacion.")
    factor = models.PositiveIntegerField(help_text="Factor de la presentacion al momento de la venta.")
    cantidad_base = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)


class VentaItemLote(models.Model):
    """De que lotes salio cada linea (para trazabilidad y devoluciones)."""

    item = models.ForeignKey(VentaItem, on_delete=models.CASCADE, related_name="lotes")
    lote = models.ForeignKey("inventory.Lote", on_delete=models.PROTECT, related_name="+")
    cantidad_base = models.PositiveIntegerField()


class MetodoReembolso(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    QR = "qr", "QR / Transferencia"


class Devolucion(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name="devoluciones")
    turno = models.ForeignKey("cash.TurnoCaja", on_delete=models.PROTECT, related_name="devoluciones")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="devoluciones")
    motivo = models.CharField(max_length=255)
    metodo_reembolso = models.CharField(max_length=10, choices=MetodoReembolso.choices)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-creado_en"]


class DevolucionItem(models.Model):
    devolucion = models.ForeignKey(Devolucion, on_delete=models.CASCADE, related_name="items")
    venta_item_lote = models.ForeignKey(VentaItemLote, on_delete=models.PROTECT, related_name="devoluciones")
    cantidad_base = models.PositiveIntegerField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)


def nuevo_uuid():
    return uuid.uuid4()
