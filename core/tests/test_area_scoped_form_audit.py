from django.test import SimpleTestCase

from scripts.audit_area_scoped_managers import model_form_fields_sem_recorte


class AreaScopedModelFormAuditTests(SimpleTestCase):
    def test_nenhum_model_form_oferece_relacao_global_sem_declarar_recorte(self):
        self.assertEqual(model_form_fields_sem_recorte(), [])
