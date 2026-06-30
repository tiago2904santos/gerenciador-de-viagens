from django.contrib import admin

from integracoes.google_drive.models import (
    DriveArquivo,
    DriveArquivoExterno,
    DriveCredenciais,
    DriveReorganizacaoJob,
)


@admin.register(DriveCredenciais)
class DriveCredenciaisAdmin(admin.ModelAdmin):
    list_display = ("__str__", "scope", "token_expiry", "atualizado_em")
    readonly_fields = ("access_token", "refresh_token", "token_expiry", "scope", "criado_em", "atualizado_em")

    def has_add_permission(self, request):
        return False


@admin.register(DriveArquivo)
class DriveArquivoAdmin(admin.ModelAdmin):
    list_display = ("nome", "artefato", "mock", "enviado_em")
    list_filter = ("mock",)
    search_fields = ("nome", "file_id")
    readonly_fields = ("artefato", "file_id", "url", "nome", "mime_type", "mock", "enviado_em")

    def has_add_permission(self, request):
        return False


@admin.register(DriveReorganizacaoJob)
class DriveReorganizacaoJobAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "eventos_processados", "total_eventos", "avulsos", "erros", "iniciado_em", "finalizado_em")
    list_filter = ("status",)
    readonly_fields = (
        "status", "total_eventos", "eventos_processados", "avulsos", "erros",
        "mensagem", "iniciado_em", "finalizado_em",
    )

    def has_add_permission(self, request):
        return False


@admin.register(DriveArquivoExterno)
class DriveArquivoExternoAdmin(admin.ModelAdmin):
    list_display = ("nome", "content_type", "object_id", "campo", "mock", "enviado_em")
    list_filter = ("mock", "content_type")
    search_fields = ("nome", "file_id")
    readonly_fields = (
        "content_type",
        "object_id",
        "campo",
        "file_id",
        "url",
        "nome",
        "pasta_id",
        "mime_type",
        "mock",
        "enviado_em",
        "atualizado_em",
    )

    def has_add_permission(self, request):
        return False
