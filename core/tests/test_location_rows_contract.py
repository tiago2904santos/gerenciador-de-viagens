from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class LocationRowsContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.engine = (
            cls.root / "static" / "js" / "components" / "location-rows.js"
        ).read_text(encoding="utf-8")

    def test_engine_owns_the_only_state_city_cascade(self):
        self.assertIn("window.CV.locationRows = {", self.engine)
        self.assertIn("function loadCities(params)", self.engine)
        self.assertIn('registerEnhancer("locationRows"', self.engine)

        page_sources = (
            "static/js/pages/eventos-detalhe.js",
            "static/js/pages/ordens-servico-form.js",
            "static/js/pages/planos-trabalho-wizard.js",
            "static/js/pages/roteiros/editor/index.js",
            "static/js/pages/termos-form.js",
        )
        for relative_path in page_sources:
            with self.subTest(page=relative_path):
                source = (self.root / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("window.CV.destinations", source)
                self.assertNotIn("Falha ao carregar cidades", source)
                self.assertNotIn("fetchJson(cidadesUrl", source)

    def test_live_templates_only_emit_the_canonical_hooks(self):
        templates = self.root / "templates"
        live_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in templates.rglob("*.html")
        )
        for hook in (
            "data-location-rows",
            "data-location-list",
            "data-location-row",
            "data-location-state",
            "data-location-city",
            "data-location-add",
            "data-location-remove",
            "data-location-template",
        ):
            self.assertIn(hook, live_sources)

        for legacy_hook in (
            "data-destination-section",
            "data-destination-row",
            "data-destination-add",
            "data-os-destino-",
            "data-termo-destino-",
            "data-pt-destino-",
            "data-destino-uf-extra",
            "data-destino-cidade-extra",
        ):
            self.assertNotIn(legacy_hook, live_sources)

    def test_event_state_controls_use_primary_keys(self):
        source = (
            self.root
            / "templates"
            / "cotton"
            / "v2"
            / "destination_row.html"
        ).read_text(encoding="utf-8")
        self.assertIn("{% destinos_opcoes_estado estados estado_selecionado %}", source)
        self.assertIn("data-location-state", source)

        options = (
            self.root / "templates" / "includes" / "destinos" / "opcoes_de_estado.html"
        ).read_text(encoding="utf-8")
        self.assertIn('value="{{ estado.pk }}"', options)
        self.assertIn("data-location-state-code", options)
        self.assertNotIn('value="{{ estado.sigla }}"', options)

        event_partials = self.root / "templates" / "eventos" / "partials"
        self.assertFalse(list(event_partials.glob("_destino_*_state*.html")))
        self.assertFalse(list(event_partials.glob("_destino_*_city*.html")))
