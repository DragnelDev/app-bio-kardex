from django.contrib import admin

from .models import Cliente, Devolucion, Venta


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("numero", "sucursal", "cajero", "total", "estado", "creado_en")
    list_filter = ("estado", "sucursal")
    readonly_fields = [f.name for f in Venta._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Cliente)
admin.site.register(Devolucion)
