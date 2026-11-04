from django.contrib import admin

from .models import Lote, MovimientoKardex, StockLote, Traspaso


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("numero", "producto", "fecha_vencimiento")
    search_fields = ("numero", "producto__nombre_comercial")


@admin.register(StockLote)
class StockLoteAdmin(admin.ModelAdmin):
    list_display = ("lote", "sucursal", "cantidad", "bloqueado")
    list_filter = ("sucursal", "bloqueado")


@admin.register(MovimientoKardex)
class MovimientoKardexAdmin(admin.ModelAdmin):
    """Solo lectura: el Kardex es inalterable."""

    list_display = ("creado_en", "sucursal", "lote", "tipo", "cantidad", "saldo", "usuario")
    list_filter = ("tipo", "sucursal")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Traspaso)
