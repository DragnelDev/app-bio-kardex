from django.db import models

from apps.core.models import ModeloBase


class Sucursal(ModeloBase):
    """Sucursal de la farmacia. Cada sucursal tiene stock, cajas y ventas propias."""

    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=120)
    direccion = models.CharField(max_length=255, blank=True)
    ciudad = models.CharField(max_length=80, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    es_casa_matriz = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "sucursales"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
