from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from core.middleware import CurrentRequestMiddleware
from core.tenancy import filter_queryset_by_area
from core.tenancy import resolve_area_for_request
from eventos.models import Evento
from oficios.models import Oficio
from oficios.services import criar_oficio_rascunho
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class FilterQuerysetByAreaLegacyTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="DPC", sigla="DPC")
        self.user = get_user_model().objects.create_user(username="area_user", password="x")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.factory = RequestFactory()
        # `area=None` de propósito: `Cargo` é catálogo (grupo 2 do `DB-02`),
        # continua anulável, e o legado sem área é o objeto deste arquivo.
        self.cargo = Cargo.objects.create(area=None, nome="Cargo Legado")

    def _activate_area(self):
        request = self.factory.get("/")
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        resolve_area_for_request(request)
        CurrentRequestMiddleware(lambda req: None)
        from core import middleware as mw

        mw._local.request = request
        return request

    def tearDown(self):
        from core import middleware as mw

        mw._local.request = None

    def test_filtro_nao_compartilha_registros_legados_sem_area(self):
        self._activate_area()
        legado = Servidor.objects.create(area=None, nome="Servidor Legado", cargo=self.cargo)
        da_area = Servidor.objects.create(nome="Servidor Area", cargo=self.cargo, area=self.area)
        outra = AreaTrabalho.objects.create(nome="Outra", sigla="OUT")
        Servidor.objects.create(nome="Servidor Outra", cargo=self.cargo, area=outra)

        qs = filter_queryset_by_area(Servidor.objects)
        ids = set(qs.values_list("pk", flat=True))
        self.assertNotIn(legado.pk, ids)
        self.assertIn(da_area.pk, ids)
        self.assertEqual(qs.filter(area=outra).count(), 0)


class NovoOficioEventoAreaTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="DPC", sigla="DPC")
        self.user = get_user_model().objects.create_user(username="oficio_area", password="x")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.factory = RequestFactory()

    def _activate_area(self):
        request = self.factory.get("/")
        request.user = self.user
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        resolve_area_for_request(request)
        from core import middleware as mw

        mw._local.request = request
        return request

    def tearDown(self):
        from core import middleware as mw

        mw._local.request = None

    def test_criar_oficio_herda_a_area_do_evento_e_nao_a_ativa(self):
        # DB-02: "evento sem área" deixou de existir — Evento é operacional e a
        # coluna é NOT NULL. O que resta da derivação em Oficio.save() é a parte
        # que importa: o ofício herda a área DO EVENTO, mesmo quando a área
        # ativa do request é outra.
        self._activate_area()
        outra = AreaTrabalho.objects.create(nome="Outra", sigla="OUT-OF")
        evento = Evento.all_objects.create(area=outra, titulo="Evento de outra área")

        oficio = criar_oficio_rascunho(evento=evento)

        self.assertEqual(oficio.area_id, outra.pk)
        self.assertTrue(Oficio.all_objects.filter(pk=oficio.pk, area=outra).exists())

    def test_evento_criado_dentro_de_request_nao_nasce_mais_sem_area(self):
        """`DB-02`, grupo operacional — o teste que falharia antes.

        `Evento` era o único dos oito modelos do `core.E001` sem derivação de
        área no `save()`: criado dentro de request por código que esquecesse
        `area`, nascia no balde `area IS NULL`. Fora de request o comportamento
        segue o do `BE-09`: nada é derivado, worker grava o que recebe.
        """
        self._activate_area()

        evento = Evento.objects.create(titulo="Evento novo em request")

        self.assertEqual(evento.area_id, self.area.pk)

    def test_view_novo_oficio_com_evento_redireciona_para_wizard(self):
        self.client.force_login(self.user)
        evento = Evento.objects.create(titulo="Evento com area", area=self.area)

        response = self.client.post(reverse("oficios:novo"), {"evento": evento.pk})

        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.latest("pk")
        self.assertEqual(oficio.area_id, self.area.pk)
        self.assertEqual(oficio.evento_id, evento.pk)
        self.assertIn(reverse("oficios:dados_viajantes", args=[oficio.pk]), response["Location"])
