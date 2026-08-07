from django.core import checks
from django.test import SimpleTestCase
from django.test import TestCase
from django.test import override_settings

from core.checks import check_document_generation_sla_configuration
from core.checks import check_operational_records_have_area
from eventos.models import Evento


class OperationalAreaDeployCheckTests(TestCase):
    def test_bloqueia_deploy_com_registro_operacional_sem_area(self):
        Evento.objects.create(titulo="Legado sem área")

        errors = check_operational_records_have_area(None)

        self.assertEqual(errors[0].id, "core.E001")
        self.assertIn("eventos.Evento=1", errors[0].msg)


class DocumentSLADeployCheckTests(SimpleTestCase):
    @override_settings(
        DOCUMENTOS_DEFAULT_PDF_ENGINE="unoserver",
        DOCUMENTOS_UNOSERVER_URL="http://127.0.0.1:2003",
    )
    def test_aprova_conversor_residente_configurado(self):
        self.assertEqual(check_document_generation_sla_configuration(None), [])

    @override_settings(
        DOCUMENTOS_DEFAULT_PDF_ENGINE="auto",
        DOCUMENTOS_UNOSERVER_URL=None,
    )
    def test_relata_fallback_lento_sem_travar_o_deploy(self):
        # NOVO-12: Warning, nao Error. O gate do deploy.yml roda com
        # --fail-level ERROR; se isto voltar a ser Error sem producao ter o
        # unoserver, todo deploy trava — foi exatamente o que impediu o gate
        # de existir ate agora.
        achados = check_document_generation_sla_configuration(None)

        self.assertEqual(achados[0].id, "core.W002")
        self.assertTrue(achados[0].is_serious(level=checks.WARNING))
        self.assertFalse(achados[0].is_serious(level=checks.ERROR))
