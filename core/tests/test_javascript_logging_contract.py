import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class JavascriptLoggingContractTests(SimpleTestCase):
    def test_application_logs_flow_through_cv_log(self):
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        violations = []
        pattern = re.compile(r"\bconsole\.(?:debug|error|warn)\b")
        for path in static_js.rglob("*.js"):
            if "vendor" in path.parts:
                continue
            if pattern.search(path.read_text(encoding="utf-8-sig")):
                violations.append(path.relative_to(static_js).as_posix())
        self.assertEqual(violations, [])

        app = (static_js / "core" / "app.js").read_text(encoding="utf-8-sig")
        self.assertIn("window.CV.log = {", app)
        self.assertIn('new CustomEvent("cv:log"', app)
