from django.contrib import admin

from .models import TermoAutorizacao


@admin.register(TermoAutorizacao)
class TermoAutorizacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "destino_display", "periodo_display", "oficio", "viatura", "created_at")
    list_filter = ("created_at", "destino_estado")
    search_fields = (
        "destino_cidade__nome",
        "destino_estado__sigla",
        "oficio__protocolo",
        "oficio__assunto",
        "servidores__nome",
    )
    autocomplete_fields = ("oficio", "destino_estado", "destino_cidade", "servidores", "viatura")
