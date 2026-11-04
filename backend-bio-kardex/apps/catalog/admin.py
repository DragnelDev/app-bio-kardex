from django.contrib import admin

from .models import (
    FormaFarmaceutica,
    PrecioSucursal,
    Presentacion,
    PrincipioActivo,
    Producto,
)


class PresentacionInline(admin.TabularInline):
    model = Presentacion
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre_comercial", "concentracion", "principio_activo", "es_controlado", "activo")
    list_filter = ("activo", "es_controlado", "forma")
    search_fields = ("nombre_comercial", "principio_activo__nombre", "codigo_barras")
    inlines = [PresentacionInline]


admin.site.register(PrincipioActivo)
admin.site.register(FormaFarmaceutica)
admin.site.register(PrecioSucursal)
