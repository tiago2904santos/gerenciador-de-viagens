import uuid

from django.core.exceptions import ValidationError
from django.db import models


class DocumentoArtefato(models.Model):
    """
    Registro de documento gerado (binário, hash, snapshot) e opção de versão assinada.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos_artefatos",
        verbose_name="Area de trabalho",
    )
    tipo = models.CharField(max_length=64, db_index=True)
    formato = models.CharField(max_length=16, db_index=True)
    oficio = models.ForeignKey(
        "oficios.Oficio",
        on_delete=models.SET_NULL,
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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_gerados",
        help_text="Evento de origem (usado por documentos que se ligam ao evento, ex.: plano de trabalho).",
    )
    termo = models.ForeignKey(
        "termos.TermoAutorizacao",
        on_delete=models.SET_NULL,
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

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.oficio_id and self.oficio and self.oficio.area_id:
                self.area = self.oficio.area
            elif self.evento_id and self.evento and self.evento.area_id:
                self.area = self.evento.area
            elif self.termo_id and self.termo and self.termo.area_id:
                self.area = self.termo.area
        super().save(*args, **kwargs)

    @property
    def esta_assinado(self) -> bool:
        if self.pk and self.versoes_assinadas.filter(revogada_em__isnull=True).exists():
            return True
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
        if self.pk:
            versao = self.versoes_assinadas.filter(
                revogada_em__isnull=True,
            ).order_by("-criado_em").first()
            if versao is not None:
                return versao.arquivo
        return self.arquivo_assinado if self.esta_assinado else self.arquivo


class DocumentoAssinaturaVersao(models.Model):
    """Versão assinada append-only; revogação é tombstone, nunca exclusão."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artefato = models.ForeignKey(
        DocumentoArtefato,
        on_delete=models.PROTECT,
        related_name="versoes_assinadas",
    )
    arquivo = models.FileField(upload_to="documentos/assinados/versoes/%Y/%m/")
    hash_sha256 = models.CharField(max_length=64, editable=False)
    nome_original = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    revogada_em = models.DateTimeField(null=True, blank=True)
    revogada_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Versão assinada"
        verbose_name_plural = "Versões assinadas"

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            anterior = type(self).objects.get(pk=self.pk)
            campos_imutaveis = (
                "artefato_id",
                "arquivo",
                "hash_sha256",
                "nome_original",
                "criado_por_id",
            )
            if any(
                getattr(anterior, campo) != getattr(self, campo)
                for campo in campos_imutaveis
            ):
                raise ValidationError("Versões documentais assinadas são imutáveis.")
            if anterior.revogada_em and self.revogada_em != anterior.revogada_em:
                raise ValidationError("A revogação documental é imutável.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Versões documentais não podem ser excluídas.")
