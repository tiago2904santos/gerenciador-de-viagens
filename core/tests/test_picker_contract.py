import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_BLOCO = re.compile(r"/\*.*?\*/", re.S)
_LINHA = re.compile(r"//[^\n]*")


def sem_comentarios(fonte: str) -> str:
    """Apaga comentários preservando o número de linhas.

    O contrato do JS-06 é sobre código: citar a classe antiga num comentário
    que explica por que ela saiu não pode reprovar o teste.
    """
    fonte = _BLOCO.sub(lambda m: "\n" * m.group(0).count("\n"), fonte)
    return _LINHA.sub("", fonte)


class PickerContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.engine = (
            cls.root / "static" / "js" / "components" / "picker.js"
        ).read_text(encoding="utf-8")
        cls.select_renderer = (
            cls.root / "static" / "js" / "components" / "picker-select.js"
        ).read_text(encoding="utf-8")

    def test_one_namespace_and_enhancer_own_all_picker_renderers(self):
        self.assertIn("window.CV.picker = {", self.engine)
        self.assertIn('window.CV.registerEnhancer("picker", init, destroy)', self.engine)
        self.assertIn("registerRenderer(renderer)", self.engine)
        self.assertIn(
            "window.CV.picker.registerRenderer(initAll)",
            self.select_renderer,
        )

        combined = self.engine + self.select_renderer
        for legacy_namespace in (
            "window.CvSearchPicker",
            "window.CvCustomSelect",
            "window.CV.searchPicker",
            "window.CV.customSelect",
        ):
            self.assertNotIn(legacy_namespace, combined)

    def test_legacy_picker_engines_and_hooks_are_absent(self):
        components = self.root / "static" / "js" / "components"
        self.assertFalse((components / "search-picker.js").exists())
        self.assertFalse((components / "custom-select.js").exists())

        paths = list((self.root / "static" / "js").rglob("*.js"))
        paths += list((self.root / "templates").rglob("*.html"))
        paths += list(self.root.glob("*/forms.py"))
        sources = "\n".join(path.read_text(encoding="utf-8-sig") for path in paths)
        self.assertNotIn("data-cv-search-picker", sources)
        self.assertNotIn("data-cv-select", sources)
        self.assertNotIn("data-picker-mode", sources)

    def test_rendered_root_and_parts_are_found_by_attribute_not_by_css_class(self):
        """JS-06 — o nome da classe CSS não é mais condição de lógica.

        Antes deste contrato, 10 arquivos achavam o picker renderizado com
        `classList.contains("search-picker")` e suas partes por seletor de
        classe BEM. Renomear a classe na reconstrução do CSS quebraria o
        roteamento de foco em 6 telas em silêncio: não há runtime de teste de
        JS que execute esse caminho.
        """
        self.assertIn("dataset.entityPickerRoot", self.engine)
        self.assertIn("data-entity-picker-part", self.engine)
        self.assertIn("data-entity-picker-root", self.select_renderer)
        for exported in ("rootFor,", "part: partOf,", "parts: partsOf,", "closestPart,"):
            self.assertIn(exported, self.engine)

        js_dir = self.root / "static" / "js"
        infratores = []
        for path in sorted(js_dir.rglob("*.js")):
            if path.name.endswith(".bundle.js"):
                continue
            codigo = sem_comentarios(path.read_text(encoding="utf-8"))
            for numero, linha in enumerate(codigo.splitlines(), start=1):
                if 'classList.contains("search-picker' in linha or ".search-picker" in linha:
                    infratores.append(f"{path.relative_to(self.root)}:{numero}")
        self.assertEqual(
            infratores,
            [],
            "O picker deve ser localizado por data-entity-picker-root/-part, "
            "nunca pela classe CSS: " + ", ".join(infratores),
        )

    def test_live_contract_declares_renderer_and_selection_mode(self):
        templates = self.root / "templates"
        sources = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in templates.rglob("*.html")
        )
        self.assertIn("data-entity-picker", sources)
        self.assertIn('data-entity-picker-renderer="select"', sources)
        self.assertIn('data-entity-picker-mode="single"', sources)
        self.assertIn('data-entity-picker-mode="{{ mode|default:\'single\' }}"', sources)
        self.assertIn('mode="multi"', sources)

        base = (templates / "base.html").read_text(encoding="utf-8")
        form_bundle = (
            self.root / "static" / "js" / "form-components.bundle.js"
        ).read_text(encoding="utf-8")
        self.assertIn("js/shell.bundle.js", base)
        self.assertIn("js/form-components.bundle.js", base)
        self.assertIn(">>> js/components/picker.js >>>", form_bundle)
        self.assertIn(">>> js/components/picker-select.js >>>", form_bundle)
        self.assertNotIn("search-picker.js", base)
        self.assertNotIn("custom-select.js", base)
