from unittest import mock

from django.core import checks
from django.db import IntegrityError
from django.db import transaction
from django.test import SimpleTestCase
from django.test import TestCase
from django.test import override_settings

from core import checks as core_checks
from core.checks import check_document_generation_sla_configuration
from core.checks import check_operational_records_have_area
from eventos.models import Evento
from eventos.models import TipoEvento


class OperationalAreaDeployCheckTests(TestCase):
    def test_banco_recusa_registro_operacional_sem_area(self):
        # DB-02, grupo 1: o proprio fixture antigo deste arquivo — um Evento
        # orfao — virou impossivel. Este teste falharia antes da migracao
        # `eventos.0015_area_obrigatoria`, que e a evidencia que o ID exige.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Evento.objects.create(area=None, titulo="Legado sem área")

    def test_bloqueia_deploy_com_registro_operacional_sem_area(self):
        # Com o NOT NULL do DB-02 nao ha como semear um orfao operacional de
        # verdade: o teste promove um modelo ainda anulavel (TipoEvento) a
        # "operacional" para provar que a contagem vira core.E001 — a janela
        # real em que o check dispara e o deploy que ainda nao migrou, rodando
        # com o codigo antigo contra um banco com orfaos.
        TipoEvento.objects.create(area=None, nome="Legado sem área")

        with mock.patch.object(
            core_checks,
            "_OPERATIONAL_MODELS",
            ("eventos.TipoEvento",),
        ):
            errors = check_operational_records_have_area(None)

        self.assertEqual(errors[0].id, "core.E001")
        # =\d+ e nao =1: as migracoes de seed ja criam TipoEvento sem area
        # (NOVO-34), entao a contagem inclui os seeds alem do criado acima.
        self.assertRegex(errors[0].msg, r"eventos\.TipoEvento=\d+")


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
