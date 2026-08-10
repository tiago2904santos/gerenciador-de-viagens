import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
CONDITIONAL_DOT = re.compile(r"\{% if .*and.* %\} ·")


class ConditionalSeparatorContractTests(SimpleTestCase):
    def test_templates_nao_montam_separador_condicional(self):
        findings = []
        for path in (ROOT / "templates").rglob("*.html"):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                if CONDITIONAL_DOT.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}")

        self.assertEqual(findings, [])
