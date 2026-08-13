from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from scripts.audit_frontend_standards import js_file_findings
from scripts.audit_frontend_standards import strip_js_comments


class InnerHtmlContractTests(SimpleTestCase):
    """NOVO-15: produção não injeta expressão dinâmica via innerHTML."""

    def test_no_dynamic_innerhtml_in_production_javascript(self):
        root = Path(settings.BASE_DIR)
        offenders = []
        for path in sorted((root / "static" / "js").rglob("*.js")):
            if path.name.endswith((".bundle.js", ".test.js")):
                continue
            raw = path.read_text(encoding="utf-8")
            for rule, line, _snippet in js_file_findings(
                strip_js_comments(raw), raw
            ):
                if rule == "innerhtml_dynamic_without_escape":
                    offenders.append(f"{path.relative_to(root)}:{line}")
        self.assertEqual(offenders, [])
