from django.contrib import admin

from .models import (
    Protocolo,
    ProtocoloAssinatura,
    ProtocoloDocumento,
    ProtocoloLog,
    ProtocoloMovimentacao,
    ProtocoloPendencia,
    ProtocoloTramitacao,
)


class ProtocoloDocumentoInline(admin.TabularInline):
    model = ProtocoloDocumento
    extra = 0
    fields = ("tipo_documento", "nome_arquivo", "codigo_documento_eprotocolo",
              "esta_no_volume", "assinado", "enviado_em")
    readonly_fields = ("enviado_em",)
    show_change_link = True


class ProtocoloTramitacaoInline(admin.TabularInline):
    model = ProtocoloTramitacao
    extra = 0
    fields = ("nome_local_de", "nome_local_para", "nome_destinatario", "data_tramitacao")
    show_change_link = True


@admin.register(Protocolo)
class ProtocoloAdmin(admin.ModelAdmin):
    list_display = ("numero_display", "status_local", "situacao_eprotocolo",
                    "nome_local_atual", "nome_responsavel_atual", "modo_mock",
                    "ativo", "criado_no_sistema_em")
    list_filter = ("status_local", "origem_tipo", "modo_mock", "ativo")
    search_fields = ("numero", "assunto_resumo", "nome_local_atual",
                     "nome_responsavel_atual", "cpf_responsavel_atual", "nome_orgao")
    date_hierarchy = "criado_no_sistema_em"
    readonly_fields = ("criado_no_sistema_em", "ultima_sincronizacao_em",
                       "ultima_movimentacao_em", "payload_atual_json")
    inlines = [ProtocoloDocumentoInline, ProtocoloTramitacaoInline]

    @admin.display(description="Número")
    def numero_display(self, obj):
        return obj.numero_display


@admin.register(ProtocoloDocumento)
class ProtocoloDocumentoAdmin(admin.ModelAdmin):
    list_display = ("nome_arquivo", "tipo_documento", "protocolo",
                    "codigo_documento_eprotocolo", "esta_no_volume", "assinado", "enviado_em")
    list_filter = ("tipo_documento", "esta_no_volume", "assinado")
    search_fields = ("nome_arquivo", "codigo_documento_eprotocolo", "protocolo__numero", "md5")
    raw_id_fields = ("protocolo",)


@admin.register(ProtocoloAssinatura)
class ProtocoloAssinaturaAdmin(admin.ModelAdmin):
    list_display = ("nome_assinante", "cpf_assinante_mascarado", "status",
                    "protocolo", "solicitado_em", "assinado_em")
    list_filter = ("status",)
    search_fields = ("nome_assinante", "cpf_assinante", "protocolo__numero")
    raw_id_fields = ("protocolo", "documento")

    @admin.display(description="CPF")
    def cpf_assinante_mascarado(self, obj):
        return obj.cpf_assinante_mascarado


@admin.register(ProtocoloPendencia)
class ProtocoloPendenciaAdmin(admin.ModelAdmin):
    list_display = ("tipo", "status", "nome_destinatario", "protocolo",
                    "criado_em", "concluido_em")
    list_filter = ("status", "tipo")
    search_fields = ("tipo", "codigo_pendencia", "nome_destinatario", "protocolo__numero")
    raw_id_fields = ("protocolo", "documento")


@admin.register(ProtocoloTramitacao)
class ProtocoloTramitacaoAdmin(admin.ModelAdmin):
    list_display = ("protocolo", "nome_local_de", "nome_local_para",
                    "nome_destinatario", "data_tramitacao")
    search_fields = ("nome_local_de", "nome_local_para", "nome_destinatario", "protocolo__numero")
    raw_id_fields = ("protocolo",)
    date_hierarchy = "data_tramitacao"


@admin.register(ProtocoloMovimentacao)
class ProtocoloMovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("protocolo", "tipo", "local", "usuario", "data_movimentacao")
    list_filter = ("tipo",)
    search_fields = ("tipo", "descricao", "local", "protocolo__numero")
    raw_id_fields = ("protocolo",)
    date_hierarchy = "data_movimentacao"


@admin.register(ProtocoloLog)
class ProtocoloLogAdmin(admin.ModelAdmin):
    list_display = ("acao", "metodo", "status_code", "sucesso", "modo_mock",
                    "protocolo", "criado_em")
    list_filter = ("sucesso", "modo_mock", "acao", "metodo")
    search_fields = ("acao", "endpoint", "protocolo__numero", "erro")
    date_hierarchy = "criado_em"
    raw_id_fields = ("protocolo",)
    readonly_fields = ("acao", "endpoint", "metodo", "status_code", "sucesso",
                       "modo_mock", "erro", "request_payload", "response_payload", "criado_em")

    def has_add_permission(self, request):
        return False
