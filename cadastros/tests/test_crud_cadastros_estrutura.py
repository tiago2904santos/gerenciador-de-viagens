import re

from django.contrib.auth import get_user_model
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.testing import area_de_teste
from core.testing import vincular_area


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CargoCrudTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="teste-cargo")
        self.client.force_login(self.user)
        vincular_area(self.user)

    def test_crud_cargo_e_normalizacao(self):
        self.assertEqual(self.client.get(reverse("cadastros:cargos_index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:cargo_create")).status_code, 200)

        response = self.client.post(reverse("cadastros:cargo_create"), {"nome": " analista "})
        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        cargo = Cargo.objects.get(nome="ANALISTA")

        response = self.client.post(reverse("cadastros:cargo_update", args=[cargo.pk]), {"nome": " gerente "})
        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        cargo.refresh_from_db()
        self.assertEqual(cargo.nome, "GERENTE")

        self.client.post(reverse("cadastros:cargo_create"), {"nome": "gerente"})
        self.assertEqual(Cargo.objects.filter(nome="GERENTE").count(), 1)

        response = self.client.post(reverse("cadastros:cargo_delete", args=[cargo.pk]))
        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        self.assertFalse(Cargo.objects.filter(pk=cargo.pk).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CombustivelCrudTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="teste-combustivel")
        self.client.force_login(self.user)
        vincular_area(self.user)

    def test_crud_combustivel_e_normalizacao(self):
        self.assertEqual(self.client.get(reverse("cadastros:combustiveis_index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:combustivel_create")).status_code, 200)

        response = self.client.post(reverse("cadastros:combustivel_create"), {"nome": " gasolina "})
        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        combustivel = Combustivel.objects.get(nome="GASOLINA")

        response = self.client.post(
            reverse("cadastros:combustivel_update", args=[combustivel.pk]),
            {"nome": " etanol "},
        )
        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        combustivel.refresh_from_db()
        self.assertEqual(combustivel.nome, "ETANOL")

        self.client.post(reverse("cadastros:combustivel_create"), {"nome": "etanol"})
        self.assertEqual(Combustivel.objects.filter(nome="ETANOL").count(), 1)

        response = self.client.post(reverse("cadastros:combustivel_delete", args=[combustivel.pk]))
        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        self.assertFalse(Combustivel.objects.filter(pk=combustivel.pk).exists())

    def test_lista_usa_ct_como_marcador_do_catalogo(self):
        Combustivel.objects.create(area=area_de_teste(), nome="GASOLINA")

        response = self.client.get(reverse("cadastros:combustiveis_index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["rows"][0]["avatar"], "CT")
        self.assertContains(response, "CT")


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class SimpleListCsrfTests(TestCase):
    def test_acao_inline_de_cargo_renderiza_csrf_e_aceita_post(self):
        Cargo.objects.create(area=area_de_teste(), nome="ANALISTA", is_padrao=True)
        cargo = Cargo.objects.create(area=area_de_teste(), nome="GERENTE")
        user_model = get_user_model()
        user = user_model.objects.create_user(username="teste-csrf")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        vincular_area(user)

        response = client.get(reverse("cadastros:cargos_index"))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode()
        self.assertIn('name="csrfmiddlewaretoken"', html)
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        self.assertIsNotNone(match)

        response = client.post(
            reverse("cadastros:cargo_set_default", args=[cargo.pk]),
            {"csrfmiddlewaretoken": match.group(1)},
        )
        self.assertRedirects(response, reverse("cadastros:cargos_index"))


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ServidorCrudTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="teste-servidor")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.unidade = Unidade.objects.create(area=area_de_teste(), nome="Secretaria", sigla="SEC")
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="ANALISTA")

    def test_servidor_fluxo_busca_e_regras(self):
        create_page = self.client.get(reverse("cadastros:servidor_create"))
        self.assertEqual(create_page.status_code, 200)
        self.assertNotContains(create_page, 'name="matricula"')
        self.assertNotContains(create_page, "cv-field-row")

        response = self.client.post(
            reverse("cadastros:servidor_create"),
            {
                "nome": " joao silva ",
                "cargo": str(self.cargo.pk),
                "cpf": "111.444.777-35",
                "rg": "12.345.678-9",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor = Servidor.objects.get(nome="JOAO SILVA")
        self.assertEqual(servidor.cpf, "11144477735")
        self.assertEqual(servidor.rg, "123456789")

        response = self.client.post(
            reverse("cadastros:servidor_update", args=[servidor.pk]),
            {
                "nome": "joao silva",
                "cargo": str(self.cargo.pk),
                "cpf": "11144477735",
                "rg": "",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))

        self.client.post(
            reverse("cadastros:servidor_create"),
            {
                "nome": "JOAO SILVA",
                "cargo": str(self.cargo.pk),
                "cpf": "",
                "rg": "",
                "unidade": "",
            },
        )
        self.assertEqual(Servidor.objects.filter(nome="JOAO SILVA").count(), 1)

        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "JOAO"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "11144477735"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "123456789"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "ANALISTA"}).status_code, 200)

        response = self.client.post(reverse("cadastros:servidor_delete", args=[servidor.pk]))
        self.assertRedirects(response, reverse("cadastros:servidores_index"))

    def test_servidores_index_limita_25_por_pagina(self):
        for index in range(30):
            Servidor.objects.create(area=area_de_teste(), nome=f"SERVIDOR PAGINADO {index:02d}", cargo=self.cargo)

        response = self.client.get(reverse("cadastros:servidores_index"), {"q": "PAGINADO"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)
        self.assertEqual(len(response.context["rows"]), 25)
        # A contagem "Mostrando X–Y de Z" vive em `list_page_quick_add`; o
        # `list_page_standard`, que esta lista usa, inclui a paginacao com
        # `pagination_part="controls"` e nao emite o bloco de informacao.
        # O que continua sendo contrato aqui e a navegacao entre paginas.
        self.assertContains(response, 'aria-label="Paginação"')
        self.assertContains(response, "?q=PAGINADO&page=2")
        self.assertNotContains(response, "data-cv-results-count")
        self.assertNotContains(response, "data-cv-realtime-filter-scope")
        self.assertContains(response, "data-delete-confirm-modal")
        self.assertContains(response, 'data-overlay-target="delete-confirm-modal"')
        # A exclusão sai como gatilho de modal, nunca como link direto. O pk vem
        # do registro, não fixo: em PostgreSQL a sequência não recomeça em 1 a
        # cada teste, e o literal fazia a asserção depender do banco.
        primeiro = Servidor.objects.get(nome="SERVIDOR PAGINADO 00")
        url_exclusao = reverse("cadastros:servidor_delete", args=[primeiro.pk])
        self.assertContains(response, f'data-delete-url="{url_exclusao}"')
        self.assertNotContains(response, f'href="{url_exclusao}"')

        response = self.client.get(reverse("cadastros:servidores_index"), {"q": "PAGINADO", "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 5)
        # Mesmo motivo da pagina 1: sem bloco de contagem no list_page_standard.
        # A ultima pagina se prova pelos `rows` e pelo link de volta a primeira.
        self.assertContains(response, "?q=PAGINADO&page=1")

    def test_servidores_index_filtra_pelos_tres_cargos_mais_usados(self):
        cargo_a = Cargo.objects.create(area=area_de_teste(), nome="DELEGADO")
        cargo_b = Cargo.objects.create(area=area_de_teste(), nome="ESCRIVAO")
        cargo_c = Cargo.objects.create(area=area_de_teste(), nome="MOTORISTA")
        cargo_d = Cargo.objects.create(area=area_de_teste(), nome="RARO")
        for i in range(5):
            Servidor.objects.create(area=area_de_teste(), nome=f"SRV A {i}", cargo=cargo_a)
        for i in range(3):
            Servidor.objects.create(area=area_de_teste(), nome=f"SRV B {i}", cargo=cargo_b)
        for i in range(2):
            Servidor.objects.create(area=area_de_teste(), nome=f"SRV C {i}", cargo=cargo_c)
        Servidor.objects.create(area=area_de_teste(), nome="SRV D", cargo=cargo_d)

        response = self.client.get(reverse("cadastros:servidores_index"))
        self.assertEqual(response.status_code, 200)
        abas = response.context["abas"]
        self.assertEqual([aba["label"] for aba in abas], ["Todos", "DELEGADO", "ESCRIVAO", "MOTORISTA"])
        self.assertEqual(abas[0]["count"], 11)
        self.assertNotIn("RARO", [aba["label"] for aba in abas])
        self.assertContains(response, 'class="list-tabs"')
        self.assertContains(response, f"cargo={cargo_a.pk}")

        filtrado = self.client.get(reverse("cadastros:servidores_index"), {"cargo": cargo_a.pk})
        self.assertEqual(filtrado.status_code, 200)
        self.assertEqual(len(filtrado.context["rows"]), 5)
        self.assertTrue(
            any(aba["is_active"] and aba["key"] == str(cargo_a.pk) for aba in filtrado.context["abas"])
        )
        self.assertContains(filtrado, f'name="cargo" value="{cargo_a.pk}"')

    def test_servidor_delete_get_redireciona_para_lista(self):
        servidor = Servidor.objects.create(area=area_de_teste(), nome="SERVIDOR SEM PAGINA DE DELETE", cargo=self.cargo)

        response = self.client.get(reverse("cadastros:servidor_delete", args=[servidor.pk]))

        self.assertRedirects(response, reverse("cadastros:servidores_index"))

    def test_servidor_create_respeita_next_interno_seguro(self):
        next_url = reverse("cadastros:cargos_index")
        create_url = f"{reverse('cadastros:servidor_create')}?next={next_url}"

        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], next_url)

        response = self.client.post(
            create_url,
            {
                "nome": " servidor com retorno ",
                "cargo": str(self.cargo.pk),
                "cpf": "111.444.777-35",
                "rg": "",
                "unidade": "",
            },
        )

        self.assertRedirects(response, next_url)

    def test_servidor_create_ignora_next_externo(self):
        create_url = f"{reverse('cadastros:servidor_create')}?next=https://example.com/fora"

        response = self.client.post(
            create_url,
            {
                "nome": " servidor retorno externo ",
                "cargo": str(self.cargo.pk),
                "cpf": "111.444.777-35",
                "rg": "",
                "unidade": "",
            },
        )

        self.assertRedirects(response, reverse("cadastros:servidores_index"))

    def test_servidor_create_apenas_com_nome_fica_rascunho(self):
        response = self.client.post(
            reverse("cadastros:servidor_create"),
            {
                "nome": "servidor incompleto",
                "cargo": "",
                "cpf": "",
                "rg": "",
                "unidade": "",
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor = Servidor.objects.get(nome="SERVIDOR INCOMPLETO")
        self.assertEqual(servidor.status, Servidor.STATUS_RASCUNHO)

        response = self.client.get(reverse("cadastros:servidores_index"))
        self.assertContains(response, "Rascunho")

        response = self.client.post(
            reverse("cadastros:servidor_update", args=[servidor.pk]),
            {
                "nome": "servidor incompleto",
                "cargo": str(self.cargo.pk),
                "cpf": "111.444.777-35",
                "rg": "",
                "unidade": "",
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor.refresh_from_db()
        self.assertEqual(servidor.status, Servidor.STATUS_COMPLETO)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ViaturaCrudTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="teste-viatura")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.combustivel = Combustivel.objects.create(area=area_de_teste(), nome="GASOLINA")

    def test_viatura_fluxo_busca_e_validacoes(self):
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viatura_create")).status_code, 200)

        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "aaa1234",
                "modelo": "Onix",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura = Viatura.objects.get(placa="AAA1234")

        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "aaa1a23",
                "modelo": "Tracker",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_DESCARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        self.assertTrue(Viatura.objects.filter(placa="AAA1A23").exists())

        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "12ABC34",
                "modelo": "Invalida",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Placa deve estar no formato")

        self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "AAA1234",
                "modelo": "Duplicada",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertEqual(Viatura.objects.filter(placa="AAA1234").count(), 1)

        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "AAA"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "Onix"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "GASOLINA"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "CARACTERIZADA"}).status_code, 200)

        response = self.client.post(
            reverse("cadastros:viatura_update", args=[viatura.pk]),
            {
                "placa": "aaa1234",
                "modelo": "Onix Plus",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))

        response = self.client.post(reverse("cadastros:viatura_delete", args=[viatura.pk]))
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))

    def test_viatura_create_respeita_next_interno_seguro(self):
        next_url = reverse("cadastros:combustiveis_index")
        create_url = f"{reverse('cadastros:viatura_create')}?next={next_url}"

        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], next_url)

        response = self.client.post(
            create_url,
            {
                "placa": "bbb1234",
                "modelo": "Duster",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )

        self.assertRedirects(response, next_url)

    def test_viatura_create_apenas_com_placa_fica_rascunho(self):
        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "ccc1234",
                "modelo": "",
                "combustivel": "",
                "tipo": "",
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura = Viatura.objects.get(placa="CCC1234")
        self.assertEqual(viatura.status, Viatura.STATUS_RASCUNHO)

        response = self.client.get(reverse("cadastros:viaturas_index"))
        self.assertContains(response, "Rascunho")

        response = self.client.post(
            reverse("cadastros:viatura_update", args=[viatura.pk]),
            {
                "placa": "ccc1234",
                "modelo": "Onix",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura.refresh_from_db()
        self.assertEqual(viatura.status, Viatura.STATUS_COMPLETO)

    def test_viaturas_index_filtra_unidade_config_e_top_combustiveis(self):
        unidade = Unidade.objects.create(area=area_de_teste(), nome="Assessoria", sigla="ASCOM")
        outra = Unidade.objects.create(area=area_de_teste(), nome="Outra", sigla="OUT")
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.unidade = unidade
        cfg.save(update_fields=["unidade"])

        flex = Combustivel.objects.create(area=area_de_teste(), nome="FLEX")
        diesel = Combustivel.objects.create(area=area_de_teste(), nome="DIESEL")
        etanol = Combustivel.objects.create(area=area_de_teste(), nome="ETANOL")
        Combustivel.objects.create(area=area_de_teste(), nome="GNV")

        for i in range(5):
            Viatura.objects.create(area=area_de_teste(), 
                placa=f"FLX{i:04d}",
                modelo="Duster",
                combustivel=flex,
                tipo=Viatura.TIPO_DESCARACTERIZADA,
                unidade=unidade,
            )
        for i in range(3):
            Viatura.objects.create(area=area_de_teste(), 
                placa=f"DSL{i:04d}",
                modelo="S10",
                combustivel=diesel,
                tipo=Viatura.TIPO_DESCARACTERIZADA,
                unidade=unidade,
            )
        for i in range(2):
            Viatura.objects.create(area=area_de_teste(), 
                placa=f"ETA{i:04d}",
                modelo="Onix",
                combustivel=etanol,
                tipo=Viatura.TIPO_CARACTERIZADA,
                unidade=outra,
            )
        Viatura.objects.create(area=area_de_teste(), 
            placa="GNV0000",
            modelo="Uno",
            combustivel=Combustivel.objects.get(nome="GNV"),
            tipo=Viatura.TIPO_CARACTERIZADA,
            unidade=outra,
        )

        response = self.client.get(reverse("cadastros:viaturas_index"))
        self.assertEqual(response.status_code, 200)
        abas = response.context["abas"]
        self.assertEqual(
            [aba["label"] for aba in abas],
            ["Todos", "ASCOM", "FLEX", "DIESEL", "ETANOL"],
        )
        self.assertEqual(abas[0]["count"], 11)
        self.assertNotIn("GNV", [aba["label"] for aba in abas])
        self.assertContains(response, 'class="list-tabs"')

        por_unidade = self.client.get(reverse("cadastros:viaturas_index"), {"unidade": unidade.pk})
        self.assertEqual(len(por_unidade.context["rows"]), 8)
        self.assertTrue(
            any(aba["is_active"] and aba["key"] == f"unidade-{unidade.pk}" for aba in por_unidade.context["abas"])
        )
        self.assertContains(por_unidade, f'name="unidade" value="{unidade.pk}"')

        por_combustivel = self.client.get(
            reverse("cadastros:viaturas_index"), {"combustivel": flex.pk}
        )
        self.assertEqual(len(por_combustivel.context["rows"]), 5)
        self.assertTrue(
            any(
                aba["is_active"] and aba["key"] == f"combustivel-{flex.pk}"
                for aba in por_combustivel.context["abas"]
            )
        )
        self.assertContains(por_combustivel, f'name="combustivel" value="{flex.pk}"')


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class MotoristaRemovidoTests(TestCase):
    def test_rota_motoristas_nao_existe(self):
        response = self.client.get("/cadastros/motoristas/")
        self.assertEqual(response.status_code, 404)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class AutenticacaoCadastrosTests(TestCase):
    def test_cadastros_exige_login_para_usuario_anonimo(self):
        response = self.client.get(reverse("cadastros:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
        self.assertIn("next=/cadastros/", response["Location"])
