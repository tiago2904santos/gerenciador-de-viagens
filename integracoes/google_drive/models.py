from django.conf import settings
from django.db import models


class GoogleDriveToken(models.Model):
    """Armazena o token OAuth 2.0 do Google Drive por usuário."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_drive_token",
        verbose_name="Usuário",
    )
    token = models.TextField(verbose_name="Access token")
    refresh_token = models.TextField(blank=True, verbose_name="Refresh token")
    token_uri = models.CharField(max_length=512, verbose_name="Token URI")
    client_id = models.CharField(max_length=512)
    client_secret = models.CharField(max_length=512)
    scopes = models.TextField(verbose_name="Escopos (JSON)")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Token Google Drive"
        verbose_name_plural = "Tokens Google Drive"

    def __str__(self):
        return f"Token Drive — {self.usuario}"
