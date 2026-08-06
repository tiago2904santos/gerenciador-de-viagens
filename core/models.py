from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import AreaScopedManager


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CancelavelModel(models.Model):
    cancelado = models.BooleanField("Cancelado", default=False)
    motivo_cancelamento = models.TextField("Motivo do cancelamento", blank=True, default="")
    cancelado_em = models.DateTimeField("Cancelado em", null=True, blank=True)

    class Meta:
        abstract = True

    def cancelar(self, motivo: str) -> None:
        self.cancelado = True
        self.motivo_cancelamento = (motivo or "").strip()
        self.cancelado_em = timezone.now()
        self.save(update_fields=["cancelado", "motivo_cancelamento", "cancelado_em"])

    def reativar(self) -> None:
        self.cancelado = False
        self.motivo_cancelamento = ""
        self.cancelado_em = None
        self.save(update_fields=["cancelado", "motivo_cancelamento", "cancelado_em"])


class AuditEvent(models.Model):
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="domain_audit_events",
    )
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=12)
    model_label = models.CharField(max_length=120, db_index=True)
    object_id = models.CharField(max_length=120, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True, default="")
    changes = models.JSONField(default=dict)
    request_path = models.CharField(max_length=500, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["model_label", "object_id", "-created_at"],
                name="core_audit_object_idx",
            ),
        ]

    def __str__(self) -> str:
        identificador = f"{self.action} {self.model_label} #{self.object_id}"
        return (
            f"{identificador} — {self.object_repr}"
            if self.object_repr
            else identificador
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise TypeError("Eventos de auditoria são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Eventos de auditoria são imutáveis.")
