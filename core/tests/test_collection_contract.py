from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class CollectionContractTests(SimpleTestCase):
    def test_one_engine_owns_client_and_server_collection_modes(self):
        source = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "collection.js"
        ).read_text(encoding="utf-8")
        self.assertIn('mode === "client"', source)
        self.assertIn('mode === "server"', source)
        self.assertIn('window.CV.registerEnhancer("collection", init)', source)
        self.assertIn("window.CV.http.fetchText", source)

    def test_legacy_filter_engines_and_hooks_are_absent_from_live_sources(self):
        base = Path(settings.BASE_DIR)
        self.assertFalse(
            (base / "static" / "js" / "components" / "realtime-filters.js").exists()
        )
        self.assertFalse(
            (base / "static" / "js" / "components" / "live-search-submit.js").exists()
        )

        legacy_hooks = (
            "data-cv-realtime-filter-scope",
            "data-cv-live-submit-form",
            "data-cv-filter-item",
        )
        paths = list((base / "templates" / "components").rglob("*.html"))
        paths += list((base / "templates" / "cotton").rglob("*.html"))
        paths += list((base / "static" / "js").rglob("*.js"))
        for path in paths:
            source = path.read_text(encoding="utf-8-sig")
            for hook in legacy_hooks:
                with self.subTest(path=path.relative_to(base), hook=hook):
                    self.assertNotIn(hook, source)

    def test_list_components_declare_exactly_one_mode(self):
        components = Path(settings.BASE_DIR) / "templates" / "cotton" / "lists"
        for filename in (
            "list_page_cards.html",
            "list_page_quick_add.html",
            "list_page_standard.html",
        ):
            with self.subTest(component=filename):
                source = (components / filename).read_text(encoding="utf-8")
                self.assertEqual(source.count("data-collection-mode="), 1)
                self.assertIn('data-collection-mode="server"', source)
