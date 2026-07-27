from django.contrib import admin

from core.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action",
        "model_label",
        "object_id",
        "actor",
        "area",
    )
    list_filter = ("action", "model_label", "area")
    search_fields = ("object_id", "object_repr", "request_id")
    readonly_fields = (
        "actor",
        "area",
        "action",
        "model_label",
        "object_id",
        "object_repr",
        "changes",
        "request_path",
        "request_id",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
