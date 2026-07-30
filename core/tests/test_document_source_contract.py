from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DocumentSourceContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.engine = (
            cls.root / "static" / "js" / "components" / "document-source.js"
        ).read_text(encoding="utf-8")

    def test_one_engine_owns_document_prefill_operations(self):
        self.assertIn("window.CV.documentSource = {", self.engine)
        for operation in (
            "apply: apply",
            "read: read",
            "selected: selected",
            "setDateRange: setDateRange",
            "setMulti: setMulti",
            "setRadio: setRadio",
            "setValue: setValue",
        ):
            self.assertIn(operation, self.engine)

        consumers = (
            "static/js/pages/termos-form.js",
            "static/js/pages/ordens-servico-form.js",
            "static/js/pages/diario-motorista.js",
        )
        for relative_path in consumers:
            with self.subTest(consumer=relative_path):
                source = (self.root / relative_path).read_text(encoding="utf-8")
                self.assertIn("window.CV.documentSource.apply(", source)

    def test_consumers_no_longer_parse_or_apply_private_document_sources(self):
        termo = (
            self.root / "static" / "js" / "pages" / "termos-form.js"
        ).read_text(encoding="utf-8")
        ordem = (
            self.root / "static" / "js" / "pages" / "ordens-servico-form.js"
        ).read_text(encoding="utf-8")
        diario = (
            self.root / "static" / "js" / "pages" / "diario-motorista.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn("JSON.parse(", diario)
        self.assertIn(
            'return window.CV.documentSource.read("termos-oficios-summary");',
            termo,
        )
        self.assertNotIn("function autoFillFromOficio", termo)
        self.assertNotIn("function setValor", diario)
        self.assertNotIn("function marcarRadio", diario)
        self.assertNotIn("var allServidorIds", ordem)
        self.assertNotIn("var startDates", ordem)

    def test_sources_use_safe_json_script_contract(self):
        templates = {
            "templates/termos/form.html": "termos-oficios-summary",
            "templates/ordens_servico/form.html": "os-oficios-summary",
            "templates/prestacoes_contas/diario_motorista_form.html": "dmv-oficios-source",
        }
        for relative_path, script_id in templates.items():
            with self.subTest(template=relative_path):
                source = (self.root / relative_path).read_text(encoding="utf-8")
                self.assertIn("|json_script:", source)
                self.assertIn(script_id, source)
                self.assertNotIn("data-oficios=", source)

        live_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                self.root / "termos" / "forms.py",
                self.root / "ordens_servico" / "forms.py",
                self.root / "templates" / "prestacoes_contas" / "partials" / "_dmv_motorista_body.html",
            )
        )
        self.assertEqual(live_sources.count("data-source-document"), 3)
