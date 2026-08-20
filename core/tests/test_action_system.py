from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class GlobalActionSystemTests(SimpleTestCase):
    def setUp(self):
        self.css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "actions"
            / "action-system.css"
        )
        self.css = self.css_path.read_text(encoding="utf-8")

    def test_a_camada_de_botao_nao_voltou(self):
        """`.cv-btn`, `.btn`, `.app-btn` e `.icon-btn` saíram em 2026-08-20.

        Eram a geometria dos botões do sistema ANTIGO, e nenhum template ou
        script os emitia mais: o botão é `c-v2.button` e o de ícone é
        `c-v2.icon_button`, cada um com folha própria. Enquanto as regras
        ficaram aqui, `action-system.css` parecia grande e viva por causa de 250
        linhas que não vestiam nada.
        """
        self.assertIn(":root {", self.css)
        self.assertIn('html[data-theme="dark"] {', self.css)
        for morta in (".cv-btn", ".btn,", ".app-btn", ".icon-btn"):
            with self.subTest(classe=morta):
                self.assertNotIn(morta, self.css)

    def test_o_dialogo_do_sistema_antigo_nao_voltou(self):
        """O diálogo é `<dialog class="modal">` — de template ou montado em JS.

        `delete-confirm-modal*` e `attach-signed-modal*` eram o desenho anterior
        dos dois diálogos globais. Os dois viraram `c-v2.modal` (o de anexar em
        2026-08-16, o de confirmação em 2026-08-20, dentro de `core/app.js`), e
        as regras aqui deixaram de alcançar qualquer marcação.
        """
        for morta in (".delete-confirm-modal", ".attach-signed-modal", "#attach-signed-modal"):
            with self.subTest(seletor=morta):
                self.assertNotIn(morta, self.css)

    def test_rich_menu_primitives_exist(self):
        self.assertIn(".action-menu--rich {", self.css)
        self.assertIn(".action-menu__heading {", self.css)
        self.assertIn(".action-menu__item--rich {", self.css)

        item = render_to_string(
            "cotton/v2/menu_item.html",
            {
                "href": "/documento.pdf",
                "title": "Baixar PDF",
                "description": "Documento pronto para impressão",
                "icon": "pdf",
                "tone": "pdf",
                "download": True,
            },
        )
        self.assertIn("menu__item", item)
        self.assertIn("Documento pronto para impressão", item)
        self.assertIn("download", item)

    def test_document_action_tones_are_distinct_and_motion_can_be_reduced(self):
        """Quem pinta o tom de cada item de menu agora é o v2, por `data-tone`.

        `.action-menu__item-icon--docx/--preview/--edit` saíram na poda de
        2026-08-20: nenhum template as emitia desde que o menu de ações virou
        `c-v2.menu_item`, que marca o tom num atributo em vez de uma classe por
        formato. Os quatro tons continuam SENDO QUATRO — é isso que este teste
        guarda —, só que medidos onde eles vivem agora.
        """
        menu = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "menu.css"
        ).read_text(encoding="utf-8")
        tons = [
            linha
            for linha in menu.splitlines()
            if ".menu__icon[data-tone=" in linha
        ]
        for tone in ("pdf", "docx", "success", "warning"):
            with self.subTest(tone=tone):
                self.assertTrue(
                    any(f'data-tone="{tone}"' in linha for linha in tons),
                    f"o menu do v2 não pinta o tom {tone}",
                )
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)

    def test_menu_item_does_not_require_a_model_pk(self):
        html = render_to_string(
            "cotton/v2/menu_item.html",
            {
                "href": "/termos/7/pdf/",
                "title": "Destino não informado",
                "description": "PDF do termo",
                "icon": "pdf",
            },
        )
        self.assertIn('href="/termos/7/pdf/"', html)
        self.assertIn("Destino não informado", html)

    def test_base_carrega_o_bundle_antes_do_css_de_tela(self):
        """A ordem da cascata mora no bundle; `extra_css` vem depois dele.

        O teste guardava também a ordem entre `actions/buttons.css` e
        `actions/action-system.css`. A primeira foi APAGADA em 2026-08-20: das
        54 classes dela, 48 não eram emitidas por ninguém (o botão legado
        inteiro) e o que restava vivo era o tooltip global, que `v2/tooltip.css`
        já desenhava — duas folhas para a mesma caixinha.
        """
        root = Path(settings.BASE_DIR)
        base = (root / "templates" / "base.html").read_text(encoding="utf-8")

        self.assertIn("css/shell.bundle.css", base)
        self.assertLess(
            base.index("css/shell.bundle.css"),
            base.index("{% block extra_css %}"),
        )
        self.assertFalse(
            (root / "static" / "css" / "actions" / "buttons.css").exists(),
            "a folha de botão legada voltou",
        )
