from django.contrib import admin

from assinaturas.models import AssinaturaDigital
from assinaturas.models import ConfiguracaoChaveAssinatura
from assinaturas.models import EventoAssinatura
from assinaturas.models import PedidoAssinaturaDocumento


@admin.register(ConfiguracaoChaveAssinatura)
class ConfiguracaoChaveAssinaturaAdmin(admin.ModelAdmin):
    list_display = ("nome", "storage_kind", "ativo", "pkcs12_path")
    list_filter = ("ativo", "storage_kind")


class EventoAssinaturaInline(admin.TabularInline):
    model = EventoAssinatura
    extra = 0
    readonly_fields = ("tipo", "payload", "criado_em")


@admin.register(AssinaturaDigital)
class AssinaturaDigitalAdmin(admin.ModelAdmin):
    list_display = ("id", "artefato", "status", "codigo_verificacao", "criado_em", "validado_em")
    list_filter = ("status",)
    readonly_fields = ("criado_em", "hash_documento", "hash_documento_assinado")
    inlines = [EventoAssinaturaInline]


@admin.register(PedidoAssinaturaDocumento)
class PedidoAssinaturaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("id", "artefato", "status", "nome_assinante_snapshot", "criado_em", "expira_em", "assinado_em")
    list_filter = ("status", "tipo_documento")
    readonly_fields = ("id", "token", "criado_em", "assinado_em", "hash_documento_original", "hash_documento_assinado")
