"""Contratos dos quatro catálogos de ``cadastros`` antes da migração P-02.

O objetivo é congelar as diferenças observáveis que ``core.catalog`` precisa
preservar: paginação, mensagens literais, ``?next=`` opcional, URLs de linha,
confirmação por GET e bloqueio de exclusão por vínculo.
"""

from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade


class _CatalogosCadastrosMixin:
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(username=self.__class__.__name__)
        )

    @staticmethod
    def _mensagens(response):
        return [str(message) for message in get_messages(response.wsgi_request)]

    @staticmethod
    def _com_query(url_name, *, args=None, **params):
        return f"{reverse(url_name, args=args)}?{urlencode(params)}"


class EstadosCatalogoCaracterizacaoTests(_CatalogosCadastrosMixin, TestCase):
    def test_lista_busca_e_paginacao_preservam_contexto(self):
        for index in range(16):
            Estado.objects.create(
                nome=f"Estado {index:02d}",
                sigla=f"{chr(65 + index // 26)}{chr(65 + index % 26)}",
                codigo_ibge=index + 1,
            )

        response = self.client.get(reverse("cadastros:estados_index"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["pagination_pages"], [1, 2])
        self.assertEqual(response.context["page_title"], "Estados")
        self.assertEqual(response.context["page_eyebrow"], "Cadastros internos")

        filtrada = self.client.get(reverse("cadastros:estados_index"), {"q": "Estado 15"})
        self.assertEqual(
            [row["title"] for row in filtrada.context["rows"]],
            ["ESTADO 15"],
        )
        self.assertEqual(filtrada.context["page_querystring"], "q=Estado+15")

    def test_criacao_edicao_e_mensagens_literais(self):
        response = self.client.post(
            reverse("cadastros:estados_index"),
            {"nome": "Paraná", "sigla": "pr", "codigo_ibge": "41"},
        )
        self.assertRedirects(response, reverse("cadastros:estados_index"))
        self.assertIn("Estado criado com sucesso.", self._mensagens(response))

        estado = Estado.objects.get(sigla="PR")
        response = self.client.post(
            reverse("cadastros:estado_update", args=[estado.pk]),
            {"nome": "Paraná", "sigla": "P", "codigo_ibge": "41"},
        )
        self.assertRedirects(response, reverse("cadastros:estados_index"))
        self.assertIn(
            "Não foi possível salvar o estado. Verifique os dados informados.",
            self._mensagens(response),
        )

        response = self.client.post(
            reverse("cadastros:estado_update", args=[estado.pk]),
            {"nome": "Paraná atualizado", "sigla": "PR", "codigo_ibge": "41"},
        )
        estado.refresh_from_db()
        self.assertEqual(estado.nome, "PARANÁ ATUALIZADO")
        self.assertIn("Estado atualizado com sucesso.", self._mensagens(response))

    def test_get_exclusao_renderiza_confirmacao_e_post_exclui(self):
        estado = Estado.objects.create(nome="Paraná", sigla="PR", codigo_ibge=41)
        url = reverse("cadastros:estado_delete", args=[estado.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cadastros/estados/confirm_delete.html")
        self.assertEqual(response.context["page_title"], "Excluir estado")
        self.assertEqual(
            response.context["page_description"],
            "Não é possível excluir se existirem cidades vinculadas.",
        )
        self.assertEqual(response.context["back_url"], reverse("cadastros:estados_index"))

        response = self.client.post(url)
        self.assertFalse(Estado.objects.filter(pk=estado.pk).exists())
        self.assertIn("Estado excluído com sucesso.", self._mensagens(response))

    def test_exclusao_vinculada_e_bloqueada_com_mensagem_global(self):
        estado = Estado.objects.create(nome="Paraná", sigla="PR", codigo_ibge=41)
        Cidade.objects.create(nome="Curitiba", estado=estado)

        response = self.client.post(
            reverse("cadastros:estado_delete", args=[estado.pk])
        )

        self.assertTrue(Estado.objects.filter(pk=estado.pk).exists())
        self.assertIn(
            "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            self._mensagens(response),
        )


class UnidadesCatalogoCaracterizacaoTests(_CatalogosCadastrosMixin, TestCase):
    destino = "/cadastros/servidores/novo/"

    def test_lista_preserva_next_somente_nas_urls_que_ja_o_usam(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")

        response = self.client.get(
            reverse("cadastros:unidades_index"),
            {"q": "Unidade", "next": self.destino},
        )

        row = response.context["rows"][0]
        self.assertEqual(
            row["edit_url"],
            reverse("cadastros:unidade_update", args=[unidade.pk]),
        )
        self.assertEqual(
            row["delete_url"],
            self._com_query(
                "cadastros:unidade_delete",
                args=[unidade.pk],
                next=self.destino,
            ),
        )
        self.assertEqual(response.context["back_url"], self.destino)
        self.assertEqual(response.context["back_label"], "Voltar ao servidor")
        self.assertEqual(response.context["next_url"], self.destino)
        self.assertEqual(
            response.context["page_querystring"],
            urlencode({"q": "Unidade", "next": self.destino}),
        )

    def test_criacao_com_next_e_edicao_invalida_preservam_contrato(self):
        response = self.client.post(
            reverse("cadastros:unidades_index"),
            {"nome": "Secretaria", "sigla": "SEC", "next": self.destino},
        )
        self.assertEqual(
            response["Location"],
            self._com_query("cadastros:unidades_index", next=self.destino),
        )
        self.assertIn("Unidade criada com sucesso.", self._mensagens(response))

        unidade = Unidade.objects.get(nome="SECRETARIA")
        response = self.client.post(
            reverse("cadastros:unidade_update", args=[unidade.pk]),
            {"nome": "", "sigla": "SEC"},
        )
        self.assertIn(
            "Não foi possível salvar a unidade. Verifique os dados informados.",
            self._mensagens(response),
        )

    def test_get_exclusao_redireciona_e_vinculo_bloqueia_post(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        Servidor.objects.create(nome="Servidor A", unidade=unidade)
        url = self._com_query(
            "cadastros:unidade_delete",
            args=[unidade.pk],
            next=self.destino,
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Unidade.objects.filter(pk=unidade.pk).exists())

        response = self.client.post(url)
        self.assertTrue(Unidade.objects.filter(pk=unidade.pk).exists())
        self.assertIn(
            "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            self._mensagens(response),
        )


class CargosCatalogoCaracterizacaoTests(_CatalogosCadastrosMixin, TestCase):
    destino = "/cadastros/servidores/novo/"

    def test_urls_de_linha_next_e_definir_padrao_por_get_e_post(self):
        cargo = Cargo.objects.create(nome="Analista")
        response = self.client.get(
            reverse("cadastros:cargos_index"), {"next": self.destino}
        )
        row = response.context["rows"][0]

        self.assertEqual(
            row["edit_url"], reverse("cadastros:cargo_update", args=[cargo.pk])
        )
        self.assertIn(urlencode({"next": self.destino}), row["delete_url"])
        self.assertIn(urlencode({"next": self.destino}), row["set_default_url"])
        self.assertEqual(response.context["back_label"], "Voltar ao servidor")

        default_url = row["set_default_url"]
        response = self.client.get(default_url)
        cargo.refresh_from_db()
        self.assertFalse(cargo.is_padrao)
        self.assertEqual(response.status_code, 302)

        response = self.client.post(default_url)
        cargo.refresh_from_db()
        self.assertTrue(cargo.is_padrao)
        self.assertIn(
            "Cargo definido como padrão com sucesso.", self._mensagens(response)
        )

    def test_criacao_edicao_invalida_e_exclusao_avisam(self):
        response = self.client.post(
            reverse("cadastros:cargos_index"), {"nome": "Analista"}
        )
        self.assertIn("Cargo criado com sucesso.", self._mensagens(response))
        cargo = Cargo.objects.get(nome="ANALISTA")

        response = self.client.post(
            reverse("cadastros:cargo_update", args=[cargo.pk]), {"nome": ""}
        )
        self.assertIn(
            "Não foi possível salvar o cargo. Verifique os dados informados.",
            self._mensagens(response),
        )

        delete_url = reverse("cadastros:cargo_delete", args=[cargo.pk])
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(delete_url)
        self.assertFalse(Cargo.objects.filter(pk=cargo.pk).exists())
        self.assertIn("Cargo excluído com sucesso.", self._mensagens(response))


class CombustiveisCatalogoCaracterizacaoTests(
    _CatalogosCadastrosMixin, TestCase
):
    destino = "/cadastros/viaturas/nova/"

    def test_urls_de_linha_next_e_definir_padrao_por_get_e_post(self):
        combustivel = Combustivel.objects.create(nome="Gasolina")
        response = self.client.get(
            reverse("cadastros:combustiveis_index"), {"next": self.destino}
        )
        row = response.context["rows"][0]

        self.assertEqual(
            row["edit_url"],
            reverse("cadastros:combustivel_update", args=[combustivel.pk]),
        )
        self.assertIn(urlencode({"next": self.destino}), row["delete_url"])
        self.assertIn(urlencode({"next": self.destino}), row["set_default_url"])
        self.assertEqual(response.context["back_label"], "Voltar à viatura")

        response = self.client.get(row["set_default_url"])
        combustivel.refresh_from_db()
        self.assertFalse(combustivel.is_padrao)
        self.assertEqual(response.status_code, 302)

        response = self.client.post(row["set_default_url"])
        combustivel.refresh_from_db()
        self.assertTrue(combustivel.is_padrao)
        self.assertIn(
            "Combustível definido como padrão com sucesso.",
            self._mensagens(response),
        )

    def test_criacao_edicao_invalida_e_exclusao_avisam(self):
        response = self.client.post(
            reverse("cadastros:combustiveis_index"), {"nome": "Gasolina"}
        )
        self.assertIn("Combustível criado com sucesso.", self._mensagens(response))
        combustivel = Combustivel.objects.get(nome="GASOLINA")

        response = self.client.post(
            reverse("cadastros:combustivel_update", args=[combustivel.pk]),
            {"nome": ""},
        )
        self.assertIn(
            "Não foi possível salvar o combustível. Verifique os dados informados.",
            self._mensagens(response),
        )

        delete_url = reverse(
            "cadastros:combustivel_delete", args=[combustivel.pk]
        )
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(delete_url)
        self.assertFalse(Combustivel.objects.filter(pk=combustivel.pk).exists())
        self.assertIn(
            "Combustível excluído com sucesso.", self._mensagens(response)
        )
