from django.contrib import admin

from integracoes.google_drive.models import (
    DriveArquivo,
    DriveArquivoExterno,
    DriveCredenciais,
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
