from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from eventos.models import Evento
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class AreaRoleMiddlewareTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Auditoria", sigla="AUD")
        self.evento = Evento.objects.create(titulo="Evento protegido", area=self.area)
        self.user = get_user_model().objects.create_user(username="papel", password="123456789012")
        self.vinculo = VinculoUsuarioArea.objects.create(
            usuario=self.user,
            area=self.area,
            papel=VinculoUsuarioArea.PAPEL_LEITOR,
            area_padrao=True,
        )
        self.client.force_login(self.user)

    def test_leitor_nao_pode_excluir_registro(self):
        response = self.client.post(reverse("eventos:excluir", args=[self.evento.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Evento.objects.filter(pk=self.evento.pk).exists())

    def test_editor_pode_executar_operacao_de_escrita(self):
        self.vinculo.papel = VinculoUsuarioArea.PAPEL_EDITOR
        self.vinculo.save(update_fields=["papel"])

        response = self.client.post(reverse("eventos:excluir", args=[self.evento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Evento.objects.filter(pk=self.evento.pk).exists())

    @override_settings(AREA_RBAC_REQUIRE_MEMBERSHIP=True)
    def test_usuario_sem_vinculo_nao_pode_escrever(self):
        self.vinculo.delete()

        response = self.client.post(reverse("eventos:novo"))

        self.assertEqual(response.status_code, 403)

    def test_usuario_sem_area_nao_cria_evento_sem_escopo(self):
        self.vinculo.delete()

        response = self.client.post(reverse("eventos:novo"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Evento.objects.count(), 1)
        self.assertFalse(Evento.objects.filter(area__isnull=True).exists())
