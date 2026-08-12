import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class JavascriptNamespaceContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_js = Path(settings.BASE_DIR) / "static" / "js"
        cls.sources = {
            path.relative_to(cls.static_js).as_posix(): path.read_text(
                encoding="utf-8-sig"
            )
            for path in cls.static_js.rglob("*.js")
            if "vendor" not in path.parts and not path.name.endswith(".test.js")
        }

    def test_application_does_not_publish_namespaces_outside_cv(self):
        assignments = []
        pattern = re.compile(r"\bwindow\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=(?!=)")
        allowed = {"CV"}
        for relative_path, source in self.sources.items():
            for match in pattern.finditer(source):
                name = match.group(1)
                if name not in allowed:
                    assignments.append(f"{relative_path}: window.{name}")
        self.assertEqual(assignments, [])

    def test_removed_aliases_and_orphan_fallbacks_do_not_return(self):
        combined = "\n".join(self.sources.values())
        for legacy_name in (
            "AppAutosave",
            "AppAutosaveSnapshots",
            "AppAutosaveValidators",
            "AppMultiselect",
            "CvDatePicker",
            "CvSelect",
            "CVThemeShared",
            "MaskEngine",
            "OficioSelectPicker",
            "OficioWizard",
            "OSFocusDestino",
            "ROTEIRO_MAP_CONFIG",
            "RoteirosEditor",
            "RoteirosEditorModules",
            "RoteirosMap",
            "RoteirosMapBoot",
        ):
            with self.subTest(namespace=legacy_name):
                self.assertNotIn(f"window.{legacy_name}", combined)

    def test_roteiro_engines_share_one_cv_subtree_without_facade_stubs(self):
        editor = self.sources["pages/roteiros/editor/index.js"]
        map_engine = self.sources["pages/roteiros-map.js"]
        wizard = self.sources["pages/roteiros-wizard.js"]
        self.assertIn("window.CV.roteiros.editor", editor)
        self.assertIn("window.CV.roteiros.modules", editor)
        self.assertIn("window.CV.roteiros.map", map_engine)
        self.assertIn("window.CV.roteiros.wizard", wizard)
        for stub in ("state.js", "retorno.js", "diarias.js"):
            with self.subTest(stub=stub):
                self.assertNotIn(f"pages/roteiros/editor/{stub}", self.sources)
                self.assertNotIn(f"'./{stub}'", editor)
