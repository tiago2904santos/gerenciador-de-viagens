from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AreaTrabalho(models.Model):
    """Isola dados e configuracoes por setor/area de trabalho."""

    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=30, unique=True)
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sigla"]
        verbose_name = "Area de trabalho"
        verbose_name_plural = "Areas de trabalho"

    def __str__(self):
        return self.sigla or self.nome

    def save(self, *args, **kwargs):
        self.nome = (self.nome or "").strip()
        self.sigla = (self.sigla or "").strip().upper()
        super().save(*args, **kwargs)


class VinculoUsuarioArea(models.Model):
    """Define quais usuarios podem acessar cada area."""

    PAPEL_ADMIN = "ADMIN"
    PAPEL_EDITOR = "EDITOR"
    PAPEL_LEITOR = "LEITOR"
    PAPEL_CHOICES = [
        (PAPEL_ADMIN, "Administrador"),
        (PAPEL_EDITOR, "Editor"),
        (PAPEL_LEITOR, "Leitor"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculos_area",
    )
    area = models.ForeignKey(
        AreaTrabalho,
        on_delete=models.CASCADE,
        related_name="vinculos_usuario",
    )
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_EDITOR)
    area_padrao = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["usuario__username", "area__sigla"]
        verbose_name = "Vinculo usuario-area"
        verbose_name_plural = "Vinculos usuario-area"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "area"],
                name="usuarios_vinculo_usuario_area_unique",
            ),
            models.UniqueConstraint(
                fields=["usuario"],
                condition=Q(area_padrao=True, ativo=True),
                name="usuarios_vinculo_usuario_area_padrao_unica",
            ),
        ]

    def __str__(self):
        return f"{self.usuario} - {self.area}"
