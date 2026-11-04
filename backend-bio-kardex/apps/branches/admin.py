from django.contrib import admin

from .models import Sucursal


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "ciudad", "es_casa_matriz", "activa")
    list_filter = ("activa", "es_casa_matriz")
    search_fields = ("codigo", "nombre")
