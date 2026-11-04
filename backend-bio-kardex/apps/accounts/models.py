from django.contrib.auth.models import AbstractUser
from django.db import models


class Rol(models.TextChoices):
    ADMIN = "admin", "Administrador"
    REGENTE = "regente", "Regente farmaceutico"
    CAJERO = "cajero", "Cajero"
    ALMACENERO = "almacenero", "Almacenero"


class Usuario(AbstractUser):
    """Usuario del sistema. El rol define permisos; las sucursales, el alcance de datos."""

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CAJERO)
    sucursales = models.ManyToManyField(
        "branches.Sucursal", related_name="usuarios", blank=True
    )
    ci = models.CharField("CI", max_length=20, blank=True)
    telefono = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name_plural = "usuarios"

    @property
    def es_admin(self) -> bool:
        return self.rol == Rol.ADMIN or self.is_superuser

    def puede_operar_en(self, sucursal_id: int) -> bool:
        """Un usuario opera solo en sus sucursales; el admin en todas."""
        if self.es_admin:
            return True
        return self.sucursales.filter(pk=sucursal_id).exists()
