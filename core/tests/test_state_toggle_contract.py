from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
LEGACY_ATTRIBUTES = ("data-rg-toggle", "data-motorista-fixo-toggle")


class StateToggleContractTests(SimpleTestCase):
    def test_motor_e_templates_vivos_nao_referenciam_gatilhos_legados(self):
        sources = [ROOT / "static/js/components/state-toggle.js"]
        sources.extend((ROOT / "templates").rglob("*.html"))

        for path in sources:
            source = path.read_text(encoding="utf-8", errors="replace")
            for attribute in LEGACY_ATTRIBUTES:
                with self.subTest(path=path.relative_to(ROOT), attribute=attribute):
                    self.assertNotIn(attribute, source)

    def test_motor_exige_o_contrato_canonico_binario(self):
        source = (ROOT / "static/js/components/state-toggle.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("[data-cv-state-trigger]", source)
        self.assertIn("data-cv-state-binary", source)
        self.assertIn("data-cv-state-input", source)
