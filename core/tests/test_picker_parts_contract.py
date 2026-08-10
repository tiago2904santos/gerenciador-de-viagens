from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
CONSUMERS = (
    "static/js/pages/eventos-detalhe.js",
    "static/js/pages/justificativas-index.js",
    "static/js/pages/oficios-transporte.js",
    "static/js/pages/ordens-servico-form.js",
    "static/js/pages/roteiros/editor/index.js",
    "static/js/pages/termos-form.js",
)


class PickerPartsContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = (
            ROOT / "static" / "js" / "components" / "picker-parts.js"
        ).read_text(encoding="utf-8")

    def test_fabrica_unica_possui_cards_opcoes_e_apresentacao_compacta(self):
        for contract in (
            "createCompactRouteCard",
            "createOption",
            "createRelatedCard",
            "createRouteCard",
            "createSelectedCard",
            "routeMeta",
            "routeTitle",
        ):
            self.assertIn(contract, self.factory)
        self.assertIn("search-picker__selected-card related-route-item", self.factory)
        self.assertIn("search-picker__option", self.factory)
        self.assertNotIn("innerHTML", self.factory)

    def test_seis_consumidores_nao_reimplementam_markup_bem(self):
        forbidden = (
            "ROUTE_AVATAR_ICON",
            "DOC_AVATAR_ICON",
            'className = "search-picker__option"',
            "search-picker__selected-card related-route-item",
            "search-picker__selected-avatar",
            "search-picker__selected-main",
        )
        for relative in CONSUMERS:
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("window.CV.pickerParts", source, relative)
            for fragment in forbidden:
                self.assertNotIn(fragment, source, relative)

    def test_editor_escolhe_apresentacao_por_dado_semântico(self):
        editor = (ROOT / "static/js/pages/roteiros/editor/index.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-related-picker-root", editor)
        self.assertIn("dataset.relatedPickerPresentation", editor)
        self.assertNotIn("closest('.related-route-picker')", editor)

    def test_consumidores_nao_localizam_raiz_por_classe_visual(self):
        for relative in CONSUMERS:
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn(".termo-oficio-picker", source, relative)
            self.assertNotIn("closest('.related-route-picker')", source, relative)

    def test_fabrica_esta_no_bundle_antes_dos_scripts_de_pagina(self):
        bundle = (ROOT / "static/js/shell.bundle.js").read_text(encoding="utf-8")
        self.assertIn(">>> js/components/picker-parts.js >>>", bundle)
        self.assertLess(
            bundle.index(">>> js/components/picker.js >>>"),
            bundle.index(">>> js/components/picker-parts.js >>>"),
        )
        self.assertLess(
            bundle.index(">>> js/components/picker-parts.js >>>"),
            bundle.index(">>> js/components/picker-select.js >>>"),
        )
