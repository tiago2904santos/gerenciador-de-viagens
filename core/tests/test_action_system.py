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

    def test_global_layer_covers_new_and_legacy_buttons_in_both_themes(self):
        self.assertIn(":root {", self.css)
        self.assertIn('html[data-theme="dark"] {', self.css)
        self.assertIn(".cv-btn,", self.css)
        self.assertIn(".btn,", self.css)
        self.assertIn(".app-btn {", self.css)
        self.assertIn(".icon-btn {", self.css)

    def test_icon_groups_do_not_receive_an_outer_box(self):
        group_rule = self.css.split(".icon-btn-group {", 1)[1].split("}", 1)[0]
        self.assertIn("background: transparent;", group_rule)
        self.assertIn("border: 0;", group_rule)
        self.assertIn("box-shadow: none;", group_rule)

    def test_rich_menu_and_shared_modal_primitives_exist(self):
        self.assertIn(".action-menu--rich {", self.css)
        self.assertIn(".action-menu__heading {", self.css)
        self.assertIn(".action-menu__item--rich {", self.css)
        self.assertIn(".delete-confirm-modal__dialog {", self.css)
        self.assertIn(".attach-signed-modal__dialog {", self.css)

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
        for tone in ("pdf", "docx", "preview", "edit"):
            self.assertIn(f"--action-{tone}-bg:", self.css)
            self.assertIn(f".action-menu__item-icon--{tone} {{", self.css)
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

    def test_base_loads_action_system_after_the_legacy_button_styles(self):
        root = Path(settings.BASE_DIR)
        base = (root / "templates" / "base.html").read_text(encoding="utf-8")
        bundle = (root / "static" / "css" / "shell.bundle.css").read_text(
            encoding="utf-8"
        )
        # NOVO-12: ordem de cascata mora no bundle; extra_css vem depois do shell.
        self.assertIn("css/shell.bundle.css", base)
        self.assertLess(
            base.index("css/shell.bundle.css"),
            base.index("{% block extra_css %}"),
        )
        self.assertLess(
            bundle.index(">>> css/actions/buttons.css >>>"),
            bundle.index(">>> css/actions/action-system.css >>>"),
        )
