"""`BE-13` fatia 1 — rede para `_setup_roteiro_querysets` antes de mexer na assinatura.

Ela é a única das sete funções de parsing do `editor_state_builder.py` que lê `request.method`
além de `request.POST` — o único `request.method` do módulo inteiro, aliás. Tirar o
`request` de lá significa passar `method` como parâmetro, e é exatamente o `if/elif/else`
que ramifica nele que estava descoberto: `coverage` apontava os ramos "instância
existente" e "cadastro novo com initial" de `_setup_roteiro_querysets`.

Os três ramos escolhem de qual estado virá o queryset de cidades da sede. Errar isso não
dá erro: dá um `<select>` de cidades do estado errado, ou vazio.

Escritos e provados verdes contra o código de hoje, pela fachada pública
(`roteiros.services.preparar_querysets_formulario_roteiro`), que é quem monta o falso
request que esta fatia vai apagar.
"""

from django.test import TestCase
from django.http import QueryDict
from urllib.parse import urlencode

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import area_de_teste
from roteiros.forms import RoteiroForm
from roteiros.models import Roteiro
from roteiros.services import preparar_querysets_formulario_roteiro


class QuerysetsDoEditorTests(TestCase):
    """De qual estado vêm as cidades da sede, nos três ramos."""

    def setUp(self):
        self.estado_a = Estado.objects.create(nome="Estado A BE13", sigla="A1")
        self.estado_b = Estado.objects.create(nome="Estado B BE13", sigla="B1")
        self.cidade_a = Cidade.objects.create(nome="Cidade A BE13", estado=self.estado_a)
        self.cidade_b = Cidade.objects.create(nome="Cidade B BE13", estado=self.estado_b)

    def _cidades_oferecidas(self, form):
        return set(form.fields["origem_cidade"].queryset.values_list("pk", flat=True))

    def test_post_manda_no_queryset_mesmo_com_instancia_de_outro_estado(self):
        """Ramo POST: o estado vem do que foi submetido, não da instância gravada."""
        roteiro = Roteiro.objects.create(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado_b,
            origem_cidade=self.cidade_b,
        )
        post = QueryDict(urlencode({"origem_estado": str(self.estado_a.pk)}))
        form = RoteiroForm(post, instance=roteiro)

        preparar_querysets_formulario_roteiro(
            form, method="POST", post=post, instance=roteiro
        )

        oferecidas = self._cidades_oferecidas(form)
        self.assertIn(self.cidade_a.pk, oferecidas)
        self.assertNotIn(self.cidade_b.pk, oferecidas)

    def test_post_com_estado_invalido_nao_derruba_e_nao_oferece_nada(self):
        """`int()` falhando vira `estado_id = None`, não exceção."""
        post = QueryDict(urlencode({"origem_estado": "nao-e-numero"}))
        form = RoteiroForm(post)

        preparar_querysets_formulario_roteiro(form, method="POST", post=post)

        self.assertEqual(self._cidades_oferecidas(form), set())

    def test_get_de_instancia_usa_o_estado_gravado(self):
        """Ramo `elif instance`, descoberto: edição carrega o estado do registro."""
        roteiro = Roteiro.objects.create(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado_b,
            origem_cidade=self.cidade_b,
        )
        form = RoteiroForm(instance=roteiro)

        preparar_querysets_formulario_roteiro(
            form, method="GET", post=QueryDict(), instance=roteiro
        )

        oferecidas = self._cidades_oferecidas(form)
        self.assertIn(self.cidade_b.pk, oferecidas)
        self.assertNotIn(self.cidade_a.pk, oferecidas)

    def test_instancia_tem_precedencia_sobre_o_initial_discordante(self):
        """O que separa o ramo `elif instance` do `else`, e só isto separa.

        Um `ModelForm` construído com `instance=` já preenche `form.initial` a partir do
        registro, então nos casos comuns os dois ramos dão o mesmo resultado — desligar o
        `elif` não muda nada e nenhum teste percebe. A diferença só aparece quando o
        chamador passa um `initial` **discordante** do que está gravado, que é o que
        `oficios/route_views.py` faz ao herdar a sede do estado do editor.
        """
        roteiro = Roteiro.objects.create(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado_b,
            origem_cidade=self.cidade_b,
        )
        form = RoteiroForm(instance=roteiro, initial={"origem_estado": self.estado_a.pk})

        preparar_querysets_formulario_roteiro(
            form, method="GET", post=QueryDict(), instance=roteiro
        )

        oferecidas = self._cidades_oferecidas(form)
        self.assertIn(self.cidade_b.pk, oferecidas, "o registro gravado ganha do initial")
        self.assertNotIn(self.cidade_a.pk, oferecidas)

    def test_get_de_cadastro_novo_usa_o_initial_da_configuracao(self):
        """Ramo `else`, descoberto: sem instância, o estado vem do `initial`.

        É o caminho que herda a sede padrão do singleton de configuração.
        """
        form = RoteiroForm(initial={"origem_estado": self.estado_a.pk})

        preparar_querysets_formulario_roteiro(form, method="GET", post=QueryDict())

        oferecidas = self._cidades_oferecidas(form)
        self.assertIn(self.cidade_a.pk, oferecidas)
        self.assertNotIn(self.cidade_b.pk, oferecidas)

    def test_get_de_cadastro_novo_aceita_instancia_de_estado_no_initial(self):
        """O `initial` pode trazer o objeto `Estado`, não só o pk — `getattr(est, "pk", est)`."""
        form = RoteiroForm(initial={"origem_estado": self.estado_a})

        preparar_querysets_formulario_roteiro(form, method="GET", post=QueryDict())

        self.assertIn(self.cidade_a.pk, self._cidades_oferecidas(form))

    def test_estados_oferecidos_nao_dependem_do_ramo(self):
        """O queryset de estados é o mesmo nos três ramos; só o de cidades ramifica."""
        esperado = {self.estado_a.pk, self.estado_b.pk}
        for rotulo, kwargs in (
            ("post", {"method": "POST", "post": QueryDict(urlencode({"origem_estado": str(self.estado_a.pk)}))}),
            ("get novo", {"method": "GET", "post": QueryDict()}),
        ):
            with self.subTest(rotulo):
                form = RoteiroForm()
                preparar_querysets_formulario_roteiro(form, **kwargs)
                oferecidos = set(form.fields["origem_estado"].queryset.values_list("pk", flat=True))
                self.assertTrue(esperado.issubset(oferecidos))


class ParserNaoMutaOPostDoChamadorTests(TestCase):
    """`BE-13` fatia 1: o parser recebe o POST direto, então não pode escrever nele.

    `_build_avulso_roteiro_state_from_post` copia o POST e **grava** no resultado
    (`sede_estado` a partir de `origem_estado`). Enquanto ele recebia um request, o
    `QueryDict` vinha imutável e o `.copy()` era obrigatório por construção. Recebendo o
    `post` do chamador, esquecer o `.copy()` passa despercebido — e o chamador que
    reutilizasse o mesmo POST veria campos que nunca submeteu.

    `roteiros/services/roteiro_editor.py::validar_submissao_editor_roteiro` passa o mesmo
    `post` para três funções em sequência, então é exatamente esse o cenário.
    """

    def setUp(self):
        self.estado = Estado.objects.create(nome="Estado M BE13", sigla="M1")
        self.cidade = Cidade.objects.create(nome="Cidade M BE13", estado=self.estado)

    def _post(self):
        return QueryDict(
            urlencode(
                {
                    "roteiro_modo": "ROTEIRO_PROPRIO",
                    "origem_estado": str(self.estado.pk),
                    "origem_cidade": str(self.cidade.pk),
                }
            ),
            mutable=True,
        )

    def test_o_post_do_chamador_sai_intacto(self):
        from roteiros.services import editor_state_builder

        post = self._post()
        antes = dict(post.lists())

        editor_state_builder._build_avulso_roteiro_state_from_post(post)

        self.assertEqual(
            dict(post.lists()),
            antes,
            "o parser tem de copiar antes de injetar os aliases `sede_*`",
        )
        self.assertNotIn("sede_estado", post)

    def test_duas_chamadas_com_o_mesmo_post_dao_o_mesmo_estado(self):
        from roteiros.services import editor_state_builder

        post = self._post()

        primeiro = editor_state_builder._build_avulso_roteiro_state_from_post(post)
        segundo = editor_state_builder._build_avulso_roteiro_state_from_post(post)

        self.assertEqual(primeiro["sede_estado_id"], segundo["sede_estado_id"])
        self.assertEqual(primeiro["sede_cidade_id"], segundo["sede_cidade_id"])
