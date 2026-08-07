import string

from django.test import SimpleTestCase
from django.test import TestCase
from django.test import override_settings

from core.checks import check_document_generation_sla_configuration
from core.checks import check_operational_records_have_area
from core.checks import check_secret_key_strength
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
    def test_fallback_lento_avisa_sem_bloquear_o_deploy(self):
        """`NOVO-12` rebaixou `core.E002` para `core.W002`: produção roda `auto`
        e um `Error` insatisfazível travaria todo deploy com o gate
        `--fail-level ERROR` ligado. O SLA real segue medido no CI, com unoserver
        de verdade."""
        problemas = check_document_generation_sla_configuration(None)

        self.assertEqual(problemas[0].id, "core.W002")
        self.assertEqual(problemas[0].level, 30)  # WARNING: relata, não trava


class SecretKeyDeployCheckTests(SimpleTestCase):
    """`core.E003` (`NOVO-12`) — a chave de 9 caracteres tem de reprovar o gate.

    `security.W009` do Django já vê chave fraca, mas é Warning e o gate do deploy
    roda com `--fail-level ERROR`; sem a promoção a Error, o gate não pegaria o
    próprio defeito que o motivou.
    """

    @override_settings(SECRET_KEY="curta-9ch")
    def test_chave_de_nove_caracteres_bloqueia(self):
        errors = check_secret_key_strength(None)

        self.assertEqual(errors[0].id, "core.E003")

    @override_settings(SECRET_KEY="a" * 60)
    def test_chave_longa_de_um_caractere_so_bloqueia(self):
        self.assertEqual(check_secret_key_strength(None)[0].id, "core.E003")

    # Longa e variada de propósito: só o prefixo reprova aqui. Sequência
    # repetida, e não um literal aleatório — para o scanner de segredos e para
    # quem lê, isto é obviamente um valor de teste (mesma razão do tests.yml,
    # que gera a chave do CI em vez de commitá-la).
    @override_settings(SECRET_KEY="django-insecure-" + "abcd1234" * 5)
    def test_prefixo_de_chave_gerada_pelo_startproject_bloqueia(self):
        self.assertEqual(check_secret_key_strength(None)[0].id, "core.E003")

    # `string.ascii_letters`: 52 caracteres, 52 distintos, sem o prefixo — passa
    # pelos três critérios sem parecer segredo, porque não é um.
    @override_settings(SECRET_KEY=string.ascii_letters)
    def test_chave_forte_passa(self):
        self.assertEqual(check_secret_key_strength(None), [])
