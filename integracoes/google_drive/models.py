from django.db import models


class DriveCredenciais(models.Model):
    """Tokens OAuth 2.0 da conta Google autorizada. Registro único (singleton)."""

    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True)
    pasta_raiz_id = models.CharField(max_length=200, blank=True, default="")
    pasta_raiz_nome = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Credencial Google Drive"
        verbose_name_plural = "Credenciais Google Drive"

    def __str__(self) -> str:
        return f"OAuth Drive (atualizado {self.atualizado_em:%d/%m/%Y %H:%M})"


class DriveArquivo(models.Model):
    """Registro de um DocumentoArtefato enviado ao Google Drive."""

    artefato = models.OneToOneField(
        "documentos.DocumentoArtefato",
        on_delete=models.CASCADE,
        related_name="drive_arquivo",
    )
    file_id = models.CharField(max_length=200)
    url = models.URLField(max_length=500, blank=True)
    nome = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=64, blank=True)
    mock = models.BooleanField(default=False)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arquivo no Drive"
        verbose_name_plural = "Arquivos no Drive"
        ordering = ["-enviado_em"]

    def __str__(self) -> str:
        return f"Drive: {self.nome or self.file_id}"
