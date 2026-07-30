from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


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
        self.assertIn('window.CV.registerEnhancer("picker", init)', self.engine)
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
        self.assertFalse((components / "cv-search-picker.js").exists())
        self.assertFalse((components / "cv-custom-select.js").exists())

        paths = list((self.root / "static" / "js").rglob("*.js"))
        paths += list((self.root / "templates").rglob("*.html"))
        paths += list(self.root.glob("*/forms.py"))
        sources = "\n".join(path.read_text(encoding="utf-8-sig") for path in paths)
        self.assertNotIn("data-cv-search-picker", sources)
        self.assertNotIn("data-cv-select", sources)
        self.assertNotIn("data-picker-mode", sources)

    def test_live_contract_declares_renderer_and_selection_mode(self):
        templates = self.root / "templates"
        sources = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in templates.rglob("*.html")
        )
        self.assertIn("data-entity-picker", sources)
        self.assertIn('data-entity-picker-renderer="select"', sources)
        self.assertIn('data-entity-picker-mode="single"', sources)
        self.assertIn('data-entity-picker-mode="multi"', sources)

        base = (templates / "base.html").read_text(encoding="utf-8")
        self.assertIn("js/components/picker.js", base)
        self.assertIn("js/components/picker-select.js", base)
        self.assertNotIn("cv-search-picker.js", base)
        self.assertNotIn("cv-custom-select.js", base)
