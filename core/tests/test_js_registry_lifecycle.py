from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class JavascriptRegistryLifecycleTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        cls.registry_source = (static_js / "core" / "app.js").read_text(encoding="utf-8")
        cls.collection_source = (
            static_js / "components" / "collection.js"
        ).read_text(encoding="utf-8")
        cls.overlay_source = (
            static_js / "components" / "overlay.js"
        ).read_text(encoding="utf-8")
        cls.autosave_source = (static_js / "autosave.js").read_text(
            encoding="utf-8"
        )

    def test_registry_exposes_destroy_and_runs_cleanup_for_removed_nodes(self):
        self.assertIn("function destroy(root)", self.registry_source)
        self.assertIn("window.CV.registry = {", self.registry_source)
        self.assertIn("destroy: destroy", self.registry_source)
        self.assertIn(
            "Array.prototype.forEach.call(mutation.removedNodes, destroy)",
            self.registry_source,
        )

    def test_live_search_destroys_old_panel_before_replacing_it(self):
        destroy_call = "window.CV.registry.destroy(currentPanel)"
        replace_call = "currentPanel.replaceWith(nextPanel)"
        self.assertIn(destroy_call, self.collection_source)
        self.assertLess(
            self.collection_source.index(destroy_call),
            self.collection_source.index(replace_call),
        )

    def test_action_menu_registers_cleanup_that_restores_portaled_menu(self):
        self.assertIn("function restoreOwner(overlay)", self.overlay_source)
        self.assertIn("owner.parent.insertBefore(overlay", self.overlay_source)
        self.assertIn(
            'window.CV.registerEnhancer("overlay", init, destroy)',
            self.overlay_source,
        )

    def test_ajax_sensitive_components_register_as_enhancers(self):
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        contracts = {
            "autosave.js": "registerEnhancer('autosave'",
            "cv-select.js": "registerEnhancer('dropdowns'",
            "components/card-toggle.js": 'registerEnhancer("cardToggle"',
            "components/location-rows.js": 'registerEnhancer("locationRows"',
            "components/document-number-field.js": 'registerEnhancer("documentNumberField"',
            "components/fields-init.js": "registerEnhancer('fields'",
            "components/masks.js": "registerEnhancer('masks'",
            "components/state-toggle.js": "registerEnhancer('stateToggle'",
        }
        for relative_path, registration in contracts.items():
            with self.subTest(component=relative_path):
                source = (static_js / relative_path).read_text(encoding="utf-8")
                self.assertIn(registration, source)

    def test_inline_create_is_idempotent_enhancer(self):
        self.assertIn('window.CV.registerEnhancer("inlineCreate"', self.registry_source)
        self.assertIn('dataset.inlineCreateBound === "true"', self.registry_source)
        self.assertIn("if (quickEditBound) return", self.registry_source)

    def test_registry_loads_before_autosave(self):
        base = (
            Path(settings.BASE_DIR) / "templates" / "base.html"
        ).read_text(encoding="utf-8")
        self.assertLess(
            base.index("js/core/app.js"),
            base.index("js/autosave.js"),
        )

    def test_autosave_unregisters_global_and_form_listeners_on_destroy(self):
        self.assertIn(
            "registerEnhancer('autosave', window.CV.autosave.init, destroy)",
            self.autosave_source,
        )
        for contract in (
            "form.removeEventListener('input', onInput, true)",
            "form.removeEventListener('change', onChange, true)",
            "form.removeEventListener('blur', onBlur, true)",
            "form.removeEventListener('submit', onSubmit, true)",
            "activeInstances.delete(instance)",
            "forms.delete(form)",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.autosave_source)

        self.assertEqual(
            self.autosave_source.count("document.addEventListener('click'"),
            1,
        )
        self.assertEqual(
            self.autosave_source.count("window.addEventListener('beforeunload'"),
            1,
        )
