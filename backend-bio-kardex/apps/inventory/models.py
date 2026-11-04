from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import KardexInalterable
from apps.core.models import ModeloBase


class Lote(ModeloBase):
    """Lote de un producto (global). El stock por sucursal vive en StockLote."""

    producto = models.ForeignKey(
        "catalog.Producto", on_delete=models.PROTECT, related_name="lotes"
    )
    numero = models.CharField(max_length=60)
    fecha_vencimiento = models.DateField(db_index=True)
    costo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Costo por unidad base.",
    )

    class Meta:
        ordering = ["fecha_vencimiento", "id"]
        constraints = [
            models.UniqueConstraint(fields=["producto", "numero"], name="lote_unico_por_producto")
        ]

    @property
    def vencido(self) -> bool:
        return self.fecha_vencimiento < timezone.localdate()

    def __str__(self):
        return f"{self.producto} / lote {self.numero}"


class StockLote(ModeloBase):
    """Existencias de un lote en una sucursal, en unidades base."""

    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="stocks")
    sucursal = models.ForeignKey(
        "branches.Sucursal", on_delete=models.PROTECT, related_name="stocks"
    )
    cantidad = models.BigIntegerField(default=0)
    bloqueado = models.BooleanField(
        default=False, help_text="Bloqueo manual (cuarentena, retiro sanitario)."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lote", "sucursal"], name="stock_unico_por_lote_sucursal"),
            models.CheckConstraint(condition=Q(cantidad__gte=0), name="stock_no_negativo"),
        ]
        indexes = [models.Index(fields=["sucursal", "cantidad"])]

    @property
    def vendible(self) -> bool:
        return self.cantidad > 0 and not self.bloqueado and not self.lote.vencido


class TipoMovimiento(models.TextChoices):
    INGRESO = "ingreso", "Ingreso"
    VENTA = "venta", "Venta"
    DEVOLUCION_VENTA = "devolucion_venta", "Devolucion de venta"
    ANULACION_VENTA = "anulacion_venta", "Anulacion de venta"
    BAJA = "baja", "Baja"
    AJUSTE = "ajuste", "Ajuste de inventario"
    TRASPASO_SALIDA = "traspaso_salida", "Traspaso (salida)"
    TRASPASO_ENTRADA = "traspaso_entrada", "Traspaso (entrada)"
    TRASPASO_RECHAZO = "traspaso_rechazo", "Traspaso rechazado (retorno)"


class KardexQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise KardexInalterable("El Kardex es inalterable.")

    def delete(self):
        raise KardexInalterable("El Kardex es inalterable.")

    def bulk_update(self, *args, **kwargs):
        raise KardexInalterable("El Kardex es inalterable.")


class MovimientoKardex(models.Model):
    """Registro inalterable de cada entrada o salida de stock.

    Proteccion en dos capas: Django (save/delete/update bloqueados) y un trigger de
    PostgreSQL (ver signals.py). Las correcciones se hacen con movimientos compensatorios.
    """

    sucursal = models.ForeignKey(
        "branches.Sucursal", on_delete=models.PROTECT, related_name="movimientos"
    )
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    cantidad = models.BigIntegerField(help_text="Con signo: positivo entra, negativo sale.")
    saldo = models.BigIntegerField(help_text="Saldo del lote en la sucursal tras el movimiento.")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos_kardex"
    )
    referencia_tipo = models.CharField(max_length=30, blank=True)
    referencia_id = models.PositiveBigIntegerField(null=True, blank=True)
    motivo = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(default=timezone.now, db_index=True)

    objects = KardexQuerySet.as_manager()

    class Meta:
        ordering = ["-creado_en", "-id"]
        constraints = [
            models.CheckConstraint(condition=~Q(cantidad=0), name="kardex_cantidad_distinta_de_cero")
        ]
        indexes = [
            models.Index(fields=["sucursal", "lote", "creado_en"]),
            models.Index(fields=["referencia_tipo", "referencia_id"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise KardexInalterable("El Kardex es inalterable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise KardexInalterable("El Kardex es inalterable.")


class EstadoTraspaso(models.TextChoices):
    ENVIADO = "enviado", "Enviado"
    RECIBIDO = "recibido", "Recibido"
    RECHAZADO = "rechazado", "Rechazado"


class Traspaso(ModeloBase):
    """Transferencia de stock entre sucursales. El stock sale del origen al enviar."""

    origen = models.ForeignKey(
        "branches.Sucursal", on_delete=models.PROTECT, related_name="traspasos_salientes"
    )
    destino = models.ForeignKey(
        "branches.Sucursal", on_delete=models.PROTECT, related_name="traspasos_entrantes"
    )
    estado = models.CharField(
        max_length=12, choices=EstadoTraspaso.choices, default=EstadoTraspaso.ENVIADO
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="traspasos_creados"
    )
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="traspasos_resueltos",
    )
    resuelto_en = models.DateTimeField(null=True, blank=True)
    observacion = models.CharField(max_length=255, blank=True)
    observacion_recepcion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        constraints = [
            models.CheckConstraint(condition=~Q(origen=models.F("destino")), name="traspaso_origen_distinto_destino")
        ]


class TraspasoItem(models.Model):
    traspaso = models.ForeignKey(Traspaso, on_delete=models.CASCADE, related_name="items")
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="+")
    cantidad_enviada = models.PositiveIntegerField()
    cantidad_recibida = models.PositiveIntegerField(null=True, blank=True)

    @property
    def diferencia(self):
        if self.cantidad_recibida is None:
            return None
        return self.cantidad_enviada - self.cantidad_recibida
