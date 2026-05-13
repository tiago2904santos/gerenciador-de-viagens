from django.contrib import admin

from .models import Justificativa
from .models import ModeloJustificativa


@admin.register(ModeloJustificativa)
class ModeloJustificativaAdmin(admin.ModelAdmin):
    list_display = ("nome", "ordem", "ativo", "is_padrao", "updated_at")
    list_filter = ("ativo", "is_padrao")
    search_fields = ("nome",)


@admin.register(Justificativa)
class JustificativaAdmin(admin.ModelAdmin):
    list_display = ("oficio", "status", "obrigatoria", "modelo", "updated_at")
    list_filter = ("status", "obrigatoria")
    raw_id_fields = ("oficio", "modelo")
