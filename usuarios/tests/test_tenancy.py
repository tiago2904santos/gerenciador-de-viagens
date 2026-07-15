from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase

from core.tenancy import AREA_SESSION_KEY
from core.tenancy import resolve_area_for_request
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class ResolveAreaForRequestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ascom1", password="x")
        self.factory = RequestFactory()
        self.ascom = AreaTrabalho.objects.create(nome="Assessoria de Comunicacao Social", sigla="ascom")
        self.dpcap = AreaTrabalho.objects.create(nome="DPCAP", sigla="dpcap")

    def _request(self, user=None):
        request = self.factory.get("/")
        request.user = user or self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def test_resolve_area_padrao_do_usuario(self):
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.ascom, area_padrao=True)
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.dpcap)

        request = self._request()

        area = resolve_area_for_request(request)

        self.assertEqual(area, self.ascom)
        self.assertEqual(request.area, self.ascom)
        self.assertEqual(request.session[AREA_SESSION_KEY], self.ascom.pk)

    def test_resolve_area_da_sessao_quando_usuario_tem_acesso(self):
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.ascom, area_padrao=True)
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.dpcap)
        request = self._request()
        request.session[AREA_SESSION_KEY] = self.dpcap.pk

        area = resolve_area_for_request(request)

        self.assertEqual(area, self.dpcap)
        self.assertEqual(request.area, self.dpcap)

    def test_ignora_area_da_sessao_sem_vinculo(self):
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.ascom)
        request = self._request()
        request.session[AREA_SESSION_KEY] = self.dpcap.pk

        area = resolve_area_for_request(request)

        self.assertEqual(area, self.ascom)
        self.assertEqual(request.area, self.ascom)
        self.assertEqual(request.session[AREA_SESSION_KEY], self.ascom.pk)
