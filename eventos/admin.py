from django.contrib import admin

from .models import Evento
from .models import EventoAnexo
from .models import TipoEvento


class EventoAnexoInline(admin.TabularInline):
    model = EventoAnexo
    extra = 0


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "status", "destino_display", "data_inicio", "data_fim", "responsavel")
    list_filter = ("status", "destino_uf")
    search_fields = ("titulo", "descricao", "destino_cidade")
    autocomplete_fields = ("unidade_responsavel", "responsavel")
    inlines = (EventoAnexoInline,)

    @admin.display(description="Destino")
    def destino_display(self, obj):
        return obj.destino_display


@admin.register(TipoEvento)
class TipoEventoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "ordem")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(EventoAnexo)
class EventoAnexoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "evento", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("titulo", "observacoes")
