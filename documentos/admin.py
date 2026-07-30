from django.contrib import admin

from .models import DocumentoArtefato
from .models import DocumentoAssinaturaVersao
from .models import DocumentoGeracao


@admin.register(DocumentoArtefato)
class DocumentoArtefatoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "formato", "area", "hash_sha256", "criado_em")
    list_filter = ("tipo", "formato", "area")
    readonly_fields = (
        "hash_sha256",
        "payload_snapshot",
        "cache_key",
        "generator_version",
        "engine",
        "criado_em",
    )


@admin.register(DocumentoAssinaturaVersao)
class DocumentoAssinaturaVersaoAdmin(admin.ModelAdmin):
    list_display = (
        "artefato",
        "nome_original",
        "hash_sha256",
        "criado_em",
        "revogada_em",
    )
    readonly_fields = (
        "artefato",
        "arquivo",
        "hash_sha256",
        "nome_original",
        "criado_em",
        "criado_por",
        "revogada_em",
        "revogada_por",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentoGeracao)
class DocumentoGeracaoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "status", "area", "usuario", "criado_em", "concluido_em")
    list_filter = ("tipo", "status", "area")
    readonly_fields = (
        "tipo",
        "parametros",
        "status",
        "dedupe_key",
        "disposicao",
        "nome_arquivo",
        "content_type",
        "hash_sha256",
        "arquivo",
        "erro",
        "area",
        "usuario",
        "criado_em",
        "iniciado_em",
        "concluido_em",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
