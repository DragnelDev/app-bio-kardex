from django.contrib import admin

from .models import Caja, TurnoCaja

admin.site.register(Caja)


@admin.register(TurnoCaja)
class TurnoCajaAdmin(admin.ModelAdmin):
    list_display = ("id", "caja", "cajero", "abierto_en", "cerrado_en", "fondo_inicial")
    list_filter = ("caja__sucursal",)
