from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "rol", "is_active")
    list_filter = ("rol", "is_active")
    filter_horizontal = ("sucursales", "groups", "user_permissions")
    fieldsets = UserAdmin.fieldsets + (
        ("BioKardex", {"fields": ("rol", "sucursales", "ci", "telefono")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("BioKardex", {"fields": ("rol", "sucursales", "ci", "telefono")}),
    )
