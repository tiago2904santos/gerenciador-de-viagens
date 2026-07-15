import uuid

from django.db import models


class DocumentoArtefato(models.Model):
    """
    Registro de documento gerado (binário, hash, snapshot) e opção de versão assinada.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=64, db_index=True)
    formato = models.CharField(max_length=16, db_index=True)
    oficio = models.ForeignKey(
        "oficios.Oficio",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documentos_gerados",
    )
    servidor = models.ForeignKey(
        "cadastros.Servidor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_gerados",
    )
    evento = models.ForeignKey(
        "eventos.Evento",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documentos_gerados",
        help_text="Evento de origem (usado por documentos que se ligam ao evento, ex.: plano de trabalho).",
    )
    termo = models.ForeignKey(
        "termos.TermoAutorizacao",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documentos_gerados",
        help_text="Termo de autorização avulso de origem (cadastro em `termos`, pode não ter ofício).",
    )
    nome_drive = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Nome 'bonito' do arquivo no Drive, calculado na geração.",
    )
    payload_snapshot = models.JSONField(default=dict, blank=True)
    hash_sha256 = models.CharField(max_length=64)
    cache_key = models.CharField(max_length=128, db_index=True, blank=True, default="")
    generator_version = models.CharField(max_length=32, blank=True, default="")
    engine = models.CharField(max_length=32, blank=True, default="")
    arquivo = models.FileField(upload_to="documentos/gerados/%Y/%m/")
    arquivo_assinado = models.FileField(
        upload_to="documentos/assinados/%Y/%m/",
        blank=True,
        help_text="Versão assinada anexada manualmente (substitui a gerada na exibição/download/Drive).",
    )
    assinado_em = models.DateTimeField(null=True, blank=True)
    assinado_nome_original = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Nome do arquivo enviado pelo usuário, para exibição.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Artefato documental"
        verbose_name_plural = "Artefatos documentais"

    def __str__(self) -> str:
        return f"{self.tipo} ({self.formato}) {self.hash_sha256[:8]}"

    @property
    def esta_assinado(self) -> bool:
        arq = self.arquivo_assinado
        if not arq or not getattr(arq, "name", ""):
            return False
        try:
            return arq.storage.exists(arq.name)
        except OSError:
            return False

    @property
    def arquivo_efetivo(self):
        """Arquivo a considerar "oficial": assinado se existir no storage, senão o gerado."""
        return self.arquivo_assinado if self.esta_assinado else self.arquivo
