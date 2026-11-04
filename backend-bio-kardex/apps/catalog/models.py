from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import ModeloBase


class PrincipioActivo(ModeloBase):
    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "principios activos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class FormaFarmaceutica(ModeloBase):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        verbose_name_plural = "formas farmaceuticas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(ModeloBase):
    nombre_comercial = models.CharField(max_length=200, db_index=True)
    principio_activo = models.ForeignKey(
        PrincipioActivo, on_delete=models.PROTECT, related_name="productos"
    )
    concentracion = models.CharField(max_length=80, blank=True)
    forma = models.ForeignKey(
        FormaFarmaceutica, on_delete=models.PROTECT, related_name="productos"
    )
    laboratorio = models.CharField(max_length=120, blank=True)
    codigo_barras = models.CharField(max_length=60, unique=True, null=True, blank=True)
    registro_sanitario = models.CharField(max_length=60, blank=True)
    es_controlado = models.BooleanField(
        default=False, help_text="Psicotropico o estupefaciente: exige receta."
    )
    requiere_receta = models.BooleanField(default=False)
    unidad_base = models.CharField(
        max_length=30,
        default="unidad",
        help_text="Unidad minima de venta y de stock (tableta, ml, sobre...).",
    )
    stock_minimo = models.PositiveIntegerField(
        default=0, help_text="En unidades base. 0 desactiva la alerta."
    )
    imagen = models.ImageField(upload_to="productos/", null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre_comercial"]

    def __str__(self):
        return f"{self.nombre_comercial} {self.concentracion}".strip()


class Nivel(models.TextChoices):
    CAJA = "caja", "Caja"
    BLISTER = "blister", "Blister"
    UNIDAD = "unidad", "Unidad"


class Presentacion(ModeloBase):
    """Nivel de empaque de un producto con su factor de conversion y precio de venta.

    El stock siempre se guarda en unidades base; `factor` es cuantas unidades base
    contiene este nivel (caja x30 -> 30, blister x10 -> 10, unidad -> 1).
    El precio incluye IVA.
    """

    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="presentaciones"
    )
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    nombre = models.CharField(max_length=80, blank=True)
    factor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    codigo_barras = models.CharField(max_length=60, unique=True, null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "presentaciones"
        ordering = ["producto_id", "-factor"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "nivel"], name="presentacion_unica_por_nivel"
            ),
            models.CheckConstraint(
                condition=Q(factor__gte=1), name="presentacion_factor_positivo"
            ),
            models.CheckConstraint(
                condition=~Q(nivel="unidad") | Q(factor=1),
                name="presentacion_unidad_factor_1",
            ),
        ]

    def clean(self):
        if self.nivel == Nivel.UNIDAD and self.factor != 1:
            raise ValidationError({"factor": "El nivel unidad debe tener factor 1."})

    def __str__(self):
        return f"{self.producto} - {self.nombre or self.get_nivel_display()}"


class PrecioSucursal(ModeloBase):
    """Precio especifico de una presentacion en una sucursal (reemplaza al precio base)."""

    presentacion = models.ForeignKey(
        Presentacion, on_delete=models.CASCADE, related_name="precios_sucursal"
    )
    sucursal = models.ForeignKey(
        "branches.Sucursal", on_delete=models.CASCADE, related_name="precios"
    )
    precio = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["presentacion", "sucursal"], name="precio_unico_por_sucursal"
            )
        ]


def precio_vigente(presentacion: Presentacion, sucursal_id: int) -> Decimal:
    especifico = PrecioSucursal.objects.filter(
        presentacion=presentacion, sucursal_id=sucursal_id
    ).first()
    return especifico.precio if especifico else presentacion.precio
