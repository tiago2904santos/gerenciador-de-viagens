from django.contrib import admin

from .models import ModeloMotivoOficio
from .models import Oficio


@admin.register(Oficio)
class OficioAdmin(admin.ModelAdmin):
    list_display = ("id", "numero_do_oficio", "protocolo", "status", "data_criacao", "roteiro")
    search_fields = ("protocolo", "assunto", "motivo", "numero", "ano")
    list_filter = ("status", "custeio", "data_criacao")
    filter_horizontal = ("servidores",)

    @admin.display(description="N° do Ofício")
    def numero_do_oficio(self, obj):
        return obj.numero_formatado


@admin.register(ModeloMotivoOficio)
class ModeloMotivoOficioAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "is_padrao", "ordem", "updated_at")
    list_filter = ("ativo", "is_padrao")
    search_fields = ("nome", "texto")
    ordering = ("ordem", "nome")
