from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AuditEvent
from eventos.models import Evento


class AuditEventTests(TestCase):
    def test_registra_criacao_e_alteracao_de_dominio(self):
        with self.captureOnCommitCallbacks(execute=True):
            evento = Evento.objects.create(titulo="Auditado")
        with self.captureOnCommitCallbacks(execute=True):
            evento.titulo = "Auditado alterado"
            evento.save(update_fields=["titulo", "atualizado_em"])

        events = AuditEvent.objects.filter(
            model_label="eventos.Evento",
            object_id=str(evento.pk),
        )
        self.assertEqual(events.count(), 2)
        update = events.get(action=AuditEvent.ACTION_UPDATE)
        self.assertEqual(update.changes["titulo"]["old"], "Auditado")
        self.assertEqual(update.changes["titulo"]["new"], "Auditado alterado")

    def test_evento_de_auditoria_nao_pode_ser_alterado_ou_excluido(self):
        actor = get_user_model().objects.create_user(username="auditor")
        event = AuditEvent.objects.create(
            actor=actor,
            action=AuditEvent.ACTION_CREATE,
            model_label="x.Model",
            object_id="1",
        )
        event.object_repr = "alterado"
        with self.assertRaises(TypeError):
            event.save()
        with self.assertRaises(TypeError):
            event.delete()
