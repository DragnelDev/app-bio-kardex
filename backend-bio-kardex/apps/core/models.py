from django.db import models


class ModeloBase(models.Model):
    """Base abstracta con marcas de tiempo."""

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
