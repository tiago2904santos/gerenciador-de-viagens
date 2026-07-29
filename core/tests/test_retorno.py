"""O contrato de "volta para onde eu estava" (`NOVO-15`).

Cinco cópias byte a byte iguais de `_safe_next_url` viraram uma. Estes testes
fixam o comportamento que as cinco tinham, para que a consolidação não mude nada,
e cobrem o que nenhuma delas tinha teste: a recusa de *open redirect*.
"""

from __future__ import annotations

from django.test import RequestFactory
from django.test import SimpleTestCase

from core.retorno import com_next
from core.retorno import daqui
from core.retorno import next_valido
from core.retorno import url_de_cadastro
from core.retorno import voltar_para


class VoltarParaTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_next_do_get_e_respeitado(self):
        request = self.factory.get("/cadastros/servidores/novo/?next=/oficios/7/editar/")

        self.assertEqual(voltar_para(request, "/fallback/"), "/oficios/7/editar/")

    def test_next_do_post_tem_prioridade_sobre_o_do_get(self):
        """O formulário reenvia o `next` num campo oculto; ele é o mais atual."""
        request = self.factory.post(
            "/cadastros/servidores/novo/?next=/do-get/", {"next": "/do-post/"}
        )

        self.assertEqual(voltar_para(request, "/fallback/"), "/do-post/")

    def test_sem_next_cai_no_fallback(self):
        request = self.factory.get("/cadastros/servidores/novo/")

        self.assertEqual(voltar_para(request, "/fallback/"), "/fallback/")

    def test_next_vazio_cai_no_fallback(self):
        request = self.factory.get("/cadastros/servidores/novo/?next=")

        self.assertEqual(voltar_para(request, "/fallback/"), "/fallback/")

    def test_a_querystring_do_destino_sobrevive(self):
        """Voltar para uma lista filtrada tem que devolver o filtro."""
        request = self.factory.get("/x/", {"next": "/oficios/?q=silva&aba=atuais"})

        self.assertEqual(
            voltar_para(request, "/fallback/"), "/oficios/?q=silva&aba=atuais"
        )


class OpenRedirectTests(SimpleTestCase):
    """`?next=` vira `Location:` — host de fora tem que ser recusado.

    Nenhuma das cinco cópias tinha teste para isto, embora todas validassem.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_host_externo_e_recusado(self):
        for hostil in (
            "https://sitemalicioso.example/",
            "//sitemalicioso.example/",
            "http://sitemalicioso.example/oficios/",
        ):
            with self.subTest(hostil=hostil):
                request = self.factory.get("/x/", {"next": hostil})

                self.assertEqual(voltar_para(request, "/seguro/"), "/seguro/")

    def test_next_valido_devolve_vazio_para_host_externo(self):
        request = self.factory.get("/x/", {"next": "https://sitemalicioso.example/"})

        self.assertEqual(next_valido(request), "")


class NextValidoTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_sem_next_devolve_vazio_em_vez_de_fallback(self):
        """A diferença que justifica existir: distinguir "sem retorno"."""
        request = self.factory.get("/cadastros/cargos/")

        self.assertEqual(next_valido(request), "")

    def test_com_next_devolve_o_next(self):
        request = self.factory.get("/cadastros/cargos/?next=/cadastros/servidores/novo/")

        self.assertEqual(next_valido(request), "/cadastros/servidores/novo/")


class ComNextTests(SimpleTestCase):
    def test_anexa_com_interrogacao_quando_a_url_e_limpa(self):
        self.assertEqual(
            com_next("/cadastros/servidores/novo/", "/oficios/7/"),
            "/cadastros/servidores/novo/?next=%2Foficios%2F7%2F",
        )

    def test_anexa_com_e_comercial_quando_a_url_ja_tem_querystring(self):
        """Sem isto o `next` sobrescreveria o parâmetro anterior."""
        self.assertEqual(
            com_next("/cadastros/cargos/?q=inv", "/x/"),
            "/cadastros/cargos/?q=inv&next=%2Fx%2F",
        )

    def test_sem_next_devolve_a_url_intacta(self):
        self.assertEqual(com_next("/cadastros/cargos/", ""), "/cadastros/cargos/")


class UrlDeCadastroTests(SimpleTestCase):
    def test_monta_a_url_do_formulario_com_o_retorno(self):
        url = url_de_cadastro("cadastros:servidor_create", "/oficios/7/editar/")

        self.assertIn("/cadastros/servidores/novo/", url)
        self.assertIn("next=%2Foficios%2F7%2Feditar%2F", url)

    def test_sem_retorno_monta_a_url_nua(self):
        url = url_de_cadastro("cadastros:servidor_create", "")

        self.assertNotIn("next=", url)


class DaquiTests(SimpleTestCase):
    def test_preserva_a_querystring_da_tela_atual(self):
        request = RequestFactory().get("/oficios/", {"q": "silva", "aba": "atuais"})

        resultado = daqui(request)

        self.assertIn("/oficios/", resultado)
        self.assertIn("q=silva", resultado)
        self.assertIn("aba=atuais", resultado)
