from django.contrib import admin

from .models import AssinaturaDocumento


@admin.register(AssinaturaDocumento)
class AssinaturaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("prestacao", "tipo", "signer", "status", "assinado_em", "codigo_verificacao")
    list_filter = ("tipo", "status")
    search_fields = ("prestacao__id", "signer__nome", "codigo_verificacao")
    exclude = ("link_token", "link_token_hash")
    readonly_fields = ("criado_em", "atualizado_em", "assinado_em", "codigo_verificacao")
