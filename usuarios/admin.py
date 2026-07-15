from django.contrib import admin

from .models import AreaTrabalho
from .models import VinculoUsuarioArea


class VinculoUsuarioAreaInline(admin.TabularInline):
    model = VinculoUsuarioArea
    extra = 0
    autocomplete_fields = ["usuario"]
    fields = ["usuario", "papel", "area_padrao", "ativo"]


@admin.register(AreaTrabalho)
class AreaTrabalhoAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "ativa", "atualizado_em"]
    list_filter = ["ativa"]
    search_fields = ["nome", "sigla"]
    inlines = [VinculoUsuarioAreaInline]


@admin.register(VinculoUsuarioArea)
class VinculoUsuarioAreaAdmin(admin.ModelAdmin):
    list_display = ["usuario", "area", "papel", "area_padrao", "ativo"]
    list_filter = ["papel", "area_padrao", "ativo", "area"]
    search_fields = ["usuario__username", "usuario__first_name", "usuario__last_name", "area__nome", "area__sigla"]
    autocomplete_fields = ["usuario", "area"]
