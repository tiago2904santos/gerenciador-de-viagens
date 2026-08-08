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
            # `DB-12`: o eixo que faltava — área cruzada com período. O único
            # leitor da trilha é o admin do Django (`core/admin.py`), que filtra
            # por `area` e herda o `ordering` acima.
            #
            # **A medição não justifica este índice na escala de hoje, e isso
            # está dito de propósito.** Com 60.000 eventos, o planner só passa a
            # escolhê-lo quando a área fica seletiva o bastante:
            #
            #       3 áreas   0,30 → 0,26 ms   1,1x   não usa o índice
            #      20 áreas   0,49 → 0,47 ms   1,0x   não usa o índice
            #     100 áreas   1,51 → 0,08 ms  18,4x   usa (buffers 1720 → 103)
            #
            # Entrou por decisão do usuário em 08/08/2026, como folga de
            # crescimento: o número de áreas em produção não é observável daqui.
            # Se a trilha ficar cara de escrever antes de as áreas crescerem, a
            # remoção é uma migração de uma linha.
            models.Index(
                fields=["area", "-created_at", "-id"],
                name="core_audit_area_periodo_idx",
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
