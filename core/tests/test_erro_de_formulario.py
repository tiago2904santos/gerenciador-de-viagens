"""`HT-03` — um padrão único para erro de formulário inteiro.

O componente certo, `form_errors.html`, existia e tinha **zero chamadores de
produção**. No lugar dele coexistiam quatro padrões: 18 templates reaproveitavam
`field_error.html` para `non_field_errors`, o editor de roteiros escrevia
`<div class="alert alert-danger py-2">` à mão, e o login usa um quarto
(`auth-error`, que fica de fora — ver o teste do fim deste arquivo).

Duas coisas que este arquivo trava e que não estavam no enunciado:

1. **O componente jogava a mensagem fora.** Ele sempre imprimia "Revise os campos
   destacados"; adotá-lo como estava teria apagado os `non_field_errors` de 18
   telas — "As duas senhas não conferem" viraria uma frase genérica.
2. **`formset.errors` é verdadeiro sem erro nenhum.** É uma lista com um dict por
   formulário, e lista de dicts vazios é `True`. Usá-la como guarda faria o
   resumo aparecer em toda página com formset.
"""

from __future__ import annotations

import re
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.forms import formset_factory
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

RESUMO = "components/ui/feedback/form_errors.html"
RAIZ = Path(settings.BASE_DIR)

GENERICA = "Revise os campos destacados antes de continuar."


class FormComErroGeral(forms.Form):
    senha = forms.CharField()
    confirmacao = forms.CharField()

    def clean(self):
        dados = super().clean()
        if dados.get("senha") != dados.get("confirmacao"):
            raise forms.ValidationError("As duas senhas não conferem.")
        return dados


class SoDeCampo(forms.Form):
    nome = forms.CharField()


class ResumoDeErroTests(SimpleTestCase):
    def renderiza(self, **contexto) -> str:
        return render_to_string(RESUMO, contexto)

    def test_a_mensagem_de_verdade_aparece(self):
        """A metade que impede a padronização de virar perda de informação."""
        form = FormComErroGeral(data={"senha": "a", "confirmacao": "b"})
        form.is_valid()

        html = self.renderiza(form=form)

        self.assertIn("As duas senhas não conferem.", html)
        self.assertNotIn(GENERICA, html)

    def test_duas_mensagens_gerais_nao_se_colam(self):
        class Duas(forms.Form):
            x = forms.CharField(required=False)

            def clean(self):
                raise forms.ValidationError(["Primeira falha.", "Segunda falha."])

        form = Duas(data={})
        form.is_valid()

        html = self.renderiza(form=form)

        self.assertIn("Primeira falha. Segunda falha.", html)

    def test_so_erro_de_campo_cai_na_frase_generica(self):
        """Sem `non_field_errors` não há o que dizer além de "olhe os campos"."""
        form = SoDeCampo(data={})
        form.is_valid()
        self.assertEqual(list(form.non_field_errors()), [])
        self.assertTrue(form.errors)

        html = self.renderiza(form=form)

        self.assertIn(GENERICA, html)

    def test_formulario_valido_nao_renderiza_nada(self):
        form = SoDeCampo(data={"nome": "ok"})
        self.assertTrue(form.is_valid())

        self.assertEqual(self.renderiza(form=form).strip(), "")

    def test_formulario_nao_submetido_nao_renderiza_nada(self):
        self.assertEqual(self.renderiza(form=SoDeCampo()).strip(), "")

    def test_o_resumo_e_anunciavel_e_focalizavel(self):
        """`role` sozinho não basta, e `focus()` num `<div>` sem `tabindex` não faz nada.

        O `data-form-errors` é o que `fields-init.js` procura — nome de classe não
        vira condição de lógica neste projeto desde o `JS-06`.
        """
        form = SoDeCampo(data={})
        form.is_valid()

        html = self.renderiza(form=form)

        self.assertIn('role="alert"', html)
        self.assertIn('tabindex="-1"', html)
        self.assertIn("data-form-errors", html)

    def test_a_mensagem_geral_e_escapada(self):
        """Quem escapa é o `join`, item a item — não o `{{ message }}` do alerta."""
        class ComMarcacao(forms.Form):
            x = forms.CharField(required=False)

            def clean(self):
                raise forms.ValidationError("<script>alert(1)</script>")

        form = ComMarcacao(data={})
        form.is_valid()

        html = self.renderiza(form=form)

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class AlertNaoInterpretaMarcacaoTests(SimpleTestCase):
    """A trava que faltava: `alert.html` escapa `message`, e isso é dos 12.

    A primeira versão do `HT-03` montava uma `<ul>` no resumo e pedia `|safe` aqui
    — 12 chamadores ganhando superfície de injeção para servir a um. Desisti do
    `|safe`, mas **a inversão não reprovava nada**: o teste do resumo passa dos dois
    jeitos, porque quem escapa lá é o `join`, e o `|safe` depois dele é inócuo.

    Décima terceira vez nesta etapa que uma edição minha não era atribuível. A
    propriedade é do `alert.html` e precisa ser exercida nele, com uma string crua.
    """

    def test_message_crua_com_marcacao_sai_escapada(self):
        html = render_to_string(
            "components/ui/feedback/alert.html",
            {"variant": "danger", "message": "<img src=x onerror=alert(1)>"},
        )

        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_title_cru_com_marcacao_sai_escapado(self):
        html = render_to_string(
            "components/ui/feedback/alert.html",
            {"variant": "danger", "title": "<b>x</b>", "message": "ok"},
        )

        self.assertNotIn("<b>x</b>", html)


class ResumoDeFormsetTests(SimpleTestCase):
    def formset(self, **kwargs):
        Conjunto = formset_factory(SoDeCampo, extra=2)
        return Conjunto(**kwargs)

    def test_formset_valido_nao_renderiza(self):
        """A armadilha: `formset.errors` é lista de dicts vazios, e isso é `True`.

        Se o componente usasse `formset.errors` de guarda, toda tela com formset
        **submetido e válido** abriria com uma faixa vermelha dizendo que não foi
        possível continuar.

        A primeira versão deste teste usava um formset **não vinculado** e afirmava
        o mesmo — e reprovou, porque ali `errors` é `[]`. O pressuposto estava
        errado, não o componente. A asserção sobre o pressuposto ficou: é ela que
        distingue "a armadilha não existe" de "a armadilha existe e está desviada".
        """
        Conjunto = formset_factory(SoDeCampo, extra=0)
        fs = Conjunto(data={
            "form-TOTAL_FORMS": "2", "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-nome": "a", "form-1-nome": "b",
        })
        self.assertTrue(fs.is_valid())
        self.assertEqual(fs.errors, [{}, {}])
        self.assertTrue(fs.errors, "o pressuposto caiu: lista de dicts vazios ficou falsy")
        self.assertEqual(list(fs.non_form_errors()), [])

        html = render_to_string(RESUMO, {"errors": fs.non_form_errors()})

        self.assertEqual(html.strip(), "")

    def test_erro_de_conjunto_aparece(self):
        Conjunto = formset_factory(SoDeCampo, extra=1, max_num=1, validate_max=True)
        fs = Conjunto(data={
            "form-TOTAL_FORMS": "2", "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1",
            "form-0-nome": "a", "form-1-nome": "b",
        })
        fs.is_valid()
        self.assertTrue(fs.non_form_errors())

        html = render_to_string(RESUMO, {"errors": fs.non_form_errors()})

        self.assertIn(str(fs.non_form_errors()[0]), html)


_INCLUDE = re.compile(r'\{%\s*include\s+"components/ui/feedback/(?P<qual>\w+)\.html"')


class UmPadraoSoTests(SimpleTestCase):
    """A varredura que impede o quinto padrão de nascer."""

    def templates(self):
        for caminho in sorted((RAIZ / "templates").rglob("*.html")):
            yield caminho, caminho.read_text(encoding="utf-8")

    #: Container de status preenchido por JS, não erro de formulário. O editor
    #: escreve `errEl.textContent` direto no elemento
    #: (`static/js/pages/roteiros/editor/index.js:1361,1376,1419,1451`), o que
    #: apagaria o `<span class="alert__message">` de dentro do `alert.html`.
    #: Converter exige mexer no JS do editor de roteiros — é o `BE-13`, não isto.
    FORA_DO_HT03 = {"templates/roteiros/partials/roteiro/_diarias_body.html"}

    def test_ninguem_escreve_alert_danger_a_mao(self):
        """`roteiros/includes/_roteiro_editor.html:40` era o único de formulário, e saiu.

        `alert alert-danger` é classe do Bootstrap legado; quem quer faixa de erro
        usa `alert.html`, que resolve variante, `role` e as classes do design
        system num lugar só.
        """
        mao = []
        for caminho, texto in self.templates():
            rel = caminho.relative_to(RAIZ).as_posix()
            if caminho.name == "alert.html" or rel in self.FORA_DO_HT03:
                continue
            # Fora de `{% comment %}`: os comentários desta etapa citam a classe
            # antiga para explicar por que ela saiu.
            sem_comentario = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}",
                                    "", texto, flags=re.S)
            for achado in re.finditer(r'class="[^"]*\balert-danger\b', sem_comentario):
                mao.append(f"{rel}:{sem_comentario.count(chr(10), 0, achado.start()) + 1}")

        self.assertEqual(mao, [], "use components/ui/feedback/alert.html")

    def test_a_excecao_do_diarias_body_ainda_e_de_JS(self):
        """Exceção que ninguém confere vira permissão. Esta é conferida.

        Se o container deixar de ser preenchido por JS, ele passa a ser marcação
        comum e a exceção some junto.
        """
        js = (RAIZ / "static/js/pages/roteiros/editor/index.js").read_text(encoding="utf-8")

        self.assertIn("$('diarias-error')", js)
        self.assertIn("errEl.textContent = ''", js)

    def test_o_resumo_saiu_de_zero_chamadores(self):
        """O enunciado do `HT-03` é justamente que ele tinha zero em produção."""
        producao = [
            caminho.relative_to(RAIZ).as_posix()
            for caminho, texto in self.templates()
            if "feedback/form_errors.html" in texto
           
        ]

        self.assertGreaterEqual(len(producao), 19, "esperava 18 formulários + o editor de roteiros")

    def test_o_login_fica_de_fora_e_o_motivo_esta_escrito(self):
        """`core/login.html` é HTML autônomo: não estende `base.html`.

        Não carrega `base.css` nem o bundle do shell — então não tem
        `fields-init.js` para mover o foco, e a faixa do design system entraria
        sem o CSS que a pinta. É o `HT-09`, que trata a tela inteira.
        """
        login = (RAIZ / "templates/core/login.html").read_text(encoding="utf-8")

        self.assertNotIn("base.html", login)
        self.assertNotIn("shell.bundle.js", login)
        self.assertIn("auth-error", login)


class FocoNoResumoTests(SimpleTestCase):
    """`HT-03` — a parte que a suíte não consegue provar, e o que dá para travar.

    Não existe teste de JavaScript neste projeto (`JS-03`), então **apagar o foco
    de `fields-init.js` não reprovava nada** — e eu só descobri porque inverti.
    O comportamento em si foi conferido no Chromium: com `/usuarios/` respondendo a
    um POST inválido, `document.activeElement` é o resumo.

    O que uma varredura estática consegue garantir é o contrato: que a chamada
    continue existindo, que ela seja pelo `data-*` (e não por classe, `JS-06`), e
    que a trava de uma vez por página continue lá. É pouco, e é honesto sobre ser
    pouco — mas é o que separa "alguém apagou sem querer" de "ninguém percebeu".
    """

    def js(self) -> str:
        return (RAIZ / "static/js/components/fields-init.js").read_text(encoding="utf-8")

    def test_o_orquestrador_chama_o_foco_do_resumo(self):
        fonte = self.js()

        self.assertIn("resumoDeErros: initResumoDeErros(scope)", fonte)
        self.assertIn("function initResumoDeErros", fonte)

    def test_o_foco_procura_pelo_data_attribute(self):
        """Nome de classe não vira condição de lógica desde o `JS-06`."""
        fonte = self.js()

        self.assertIn("[data-form-errors]", fonte)
        self.assertNotIn(".cv-notice--danger", fonte)

    def test_o_foco_acontece_uma_vez_por_pagina(self):
        """`init` roda de novo a cada re-render parcial.

        Sem a trava, um autosave que redesenha um bloco puxaria o foco de volta
        para o topo no meio da digitação — trocar um defeito de acessibilidade por
        outro pior.
        """
        fonte = self.js()

        self.assertIn("resumoDeErrosJaFocado", fonte)
        self.assertIn("if (resumoDeErrosJaFocado) return 0;", fonte)

    def test_o_bundle_do_shell_carrega_a_versao_nova(self):
        """`build_shell_bundles.py --check` já cobre, mas o CI é quem roda.

        Aqui a garantia é local: sem isto, uma edição no fonte sem rebuild passaria
        na suíte e chegaria no navegador sem o foco.
        """
        bundle = (RAIZ / "static/js/shell.bundle.js").read_text(encoding="utf-8")

        self.assertIn("initResumoDeErros", bundle)


class PainelAbertoNaoCortaTests(SimpleTestCase):
    """O resumo cresceu o painel de cadastro rápido além do teto de `max-height`.

    Medido em `/usuarios/` com Chromium, antes da correção: `scrollHeight` 696
    contra `clientHeight` 640 — **56 px cortados em silêncio**, e o que sumia era o
    bloco "Primeiro acesso" inteiro, com a área e o perfil do usuário novo.

    O par `max-height` + `overflow: hidden` existe para a animação de abertura;
    fechado, ele apaga o excedente sem aviso. `overflow-y: auto` mantém a animação
    e devolve o que passa do teto.

    **Duas folhas, e por quê:** `.list-header .cv-inline-create__panel` declara
    `overflow: hidden` com a mesma especificidade da regra genérica e vem **depois**
    no bundle — a correção só em `page-shell.css` não chegava a valer (medido:
    `overflowY` continuava `hidden`). É o `UI-04`; enquanto ele não sai, as duas
    precisam concordar, e é isso que este teste trava.
    """

    REGRAS = [
        ("static/css/page-shell.css", ".cv-inline-create__panel.is-open {"),
        ("static/css/components/list-header.css", ".list-header .cv-inline-create__panel.is-open {"),
    ]

    def test_o_painel_aberto_rola_em_vez_de_cortar(self):
        for arquivo, seletor in self.REGRAS:
            with self.subTest(arquivo=arquivo):
                css = (RAIZ / arquivo).read_text(encoding="utf-8")
                inicio = css.index(seletor)
                bloco = css[inicio : css.index("}", inicio)]

                self.assertIn("overflow-y: auto", bloco)


class TelaRealTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin_ht03", password="123456", email="a@b.c",
        )
        self.client.force_login(self.user)

    def test_o_resumo_aparece_no_post_invalido(self):
        resposta = self.client.post(reverse("usuarios:index"), data={})
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()

        self.assertIn("data-form-errors", html)
        self.assertIn("Não foi possível continuar", html)

    def test_a_lista_sem_post_nao_mostra_resumo(self):
        html = self.client.get(reverse("usuarios:index")).content.decode()

        self.assertNotIn("data-form-errors", html)
