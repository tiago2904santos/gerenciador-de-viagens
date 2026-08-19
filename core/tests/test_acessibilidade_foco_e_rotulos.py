"""`HT-01`, `HT-09` e `HT-11` — foco visível e nome acessível.

O que estes testes cobrem é o **contrato**: que o piso de foco exista nos dois
lugares onde ele precisa existir, que o login tenha o skip link e associe o erro
ao campo, e que o seletor de busca nomeie o input que ele cria.

O que eles **não** cobrem, e por isso a etapa também foi conferida no navegador
com Playwright: se o anel de fato aparece na tela. CSS que existe no arquivo
pode ser sobrescrito por outro arquivo, e foi exatamente o que aconteceu na
primeira versão — o piso estava em `base.css`, correto, e mesmo assim o login
continuava sem anel, porque aquela tela não carrega `base.css`. Contrato em
arquivo não prova pixel na tela.
"""

from __future__ import annotations

import re

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse
from django.utils.crypto import get_random_string

from core.forms import LoginForm

RAIZ = Path(settings.BASE_DIR)


def ler(rel: str) -> str:
    return (RAIZ / rel).read_text(encoding="utf-8")


class FocoVisivelTests(SimpleTestCase):
    """`HT-01` — o anel de foco de teclado."""

    def test_o_token_do_anel_existe_nos_dois_temas(self):
        for arquivo in ("static/css/base/tokens.css", "static/css/base/03-theme-dark.css"):
            with self.subTest(arquivo=arquivo):
                self.assertIn("--color-focus-visible-ring:", ler(arquivo))

    def test_o_piso_existe_em_base_e_tambem_no_login(self):
        """São dois porque são dois carregamentos diferentes.

        `templates/core/login.html` não estende `base.html` e `base.css` não é
        uma das folhas que ele carrega. Um piso só em `base.css` deixa de fora
        justamente a tela que o defeito citava.

        O token muda com o arquivo, e é o ponto: `base.css` é do sistema legado
        e lê `--color-focus-visible-ring`; a folha do login foi reconstruída no
        v2 (`NOVO-20260819-220313-df2a5685481a`) e lê `--focus-ring`, que é o
        anel único do sistema novo. Exigir o token legado na folha nova traria
        de volta a camada que a migração acabou de tirar.
        """
        for arquivo, token in (
            ("static/css/base/base.css", "var(--color-focus-visible-ring)"),
            ("static/css/v2/auth.css", "var(--focus-ring)"),
        ):
            with self.subTest(arquivo=arquivo):
                css = ler(arquivo)
                self.assertIn(":focus-visible", css)
                self.assertIn(token, css)

    def test_o_login_nao_depende_de_base_css(self):
        """Se um dia passar a depender, o piso duplicado em `v2/auth.css` sai.

        A busca é pelo `<link>`, não pelo nome solto: a asserção antiga casava
        com a palavra dentro de um comentário do template — inclusive um que
        dizia justamente que a folha está de fora.
        """
        html = ler("templates/core/login.html")

        folhas = re.findall(r'{%\s*static\s+[\'"]([^\'"]+\.css)[\'"]', html)

        self.assertNotIn("css/base/base.css", folhas)
        self.assertIn("css/v2/auth.css", folhas)

    def test_o_anel_leva_offset(self):
        """No tema escuro o âmbar dá 2,07:1 contra a borda do campo.

        Colado nela reprovaria; o afastamento põe o fundo ao lado do anel, onde
        a medida é 7,76:1. O offset é requisito de contraste, não enfeite.
        """
        for arquivo in ("static/css/base/base.css", "static/css/v2/auth.css"):
            with self.subTest(arquivo=arquivo):
                self.assertIn("outline-offset", ler(arquivo))


class SkipLinkDoLoginTests(SimpleTestCase):
    """`HT-09` — a única das 25 telas sem skip link."""

    def test_o_login_tem_skip_link_apontando_para_alvo_que_existe(self):
        html = ler("templates/core/login.html")

        self.assertIn('class="skip-link" href="#auth-form"', html)
        self.assertIn('id="auth-form"', html)

    def test_o_estilo_do_skip_link_acompanha_a_tela_que_o_usa(self):
        """`app-shell.css` não entra nesta tela; sem isto o link ficaria visível."""
        self.assertIn(".skip-link", ler("static/css/v2/auth.css"))


class ErroDeLoginAssociadoTests(TestCase):
    """`HT-09` — os `id` de erro existiam e ninguém os referenciava."""

    def setUp(self):
        self.senha = get_random_string(24)
        get_user_model().objects.create_user(username="quem", password=self.senha)

    def test_sem_erro_o_campo_nao_ganha_atributo_nenhum(self):
        """Apontar para um `id` ausente é pior que não apontar."""
        form = LoginForm(data={"username": "quem", "password": self.senha})
        form.is_valid()

        self.assertNotIn("aria-describedby", form.fields["username"].widget.attrs)

    def test_com_erro_de_campo_o_input_aponta_para_a_mensagem(self):
        form = LoginForm(data={"username": "", "password": ""})
        form.is_valid()

        for nome in ("username", "password"):
            with self.subTest(campo=nome):
                attrs = form.fields[nome].widget.attrs
                self.assertEqual(attrs.get("aria-describedby"), f"id_{nome}-error")
                self.assertEqual(attrs.get("aria-invalid"), "true")

    def test_o_id_referenciado_e_o_que_o_template_renderiza(self):
        """A referência e o alvo nascem em arquivos diferentes; se um mudar sozinho, quebra calado."""
        resposta = self.client.post(reverse("core:login"), {"username": "", "password": ""})

        self.assertContains(resposta, 'id="id_username-error"')
        self.assertContains(resposta, 'aria-describedby="id_username-error"')


class NomeAcessivelDoSeletorTests(SimpleTestCase):
    """`HT-11` — o input que o `picker.js` cria não tinha nome."""

    def test_o_rotulo_sobrevive_como_sr_only_no_campo_de_busca(self):
        """Era omitido de vez; agora sai da tela mas fica na árvore de acessibilidade."""
        html = ler("templates/cotton/v2/form_field.html")

        self.assertIn(':label_for="field.id_for_label"', html)
        self.assertIn(':label="rotulo"', html)

    def test_o_picker_associa_o_rotulo_ao_input(self):
        js = ler("static/js/components/picker.js")

        self.assertIn('input.setAttribute("aria-labelledby"', js)
        self.assertIn('label[for="${CSS.escape(select.id)}"]', js)

    def test_o_picker_cai_para_o_placeholder_quando_nao_ha_rotulo(self):
        """Nome fraco é melhor que nenhum, e nunca falta placeholder."""
        js = ler("static/js/components/picker.js")

        self.assertIn('input.setAttribute("aria-label", placeholder)', js)
