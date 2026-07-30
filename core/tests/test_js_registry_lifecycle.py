from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class JavascriptRegistryLifecycleTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        cls.registry_source = (static_js / "core" / "app.js").read_text(encoding="utf-8")
        cls.live_search_source = (
            static_js / "components" / "live-search-submit.js"
        ).read_text(encoding="utf-8")
        cls.action_menu_source = (
            static_js / "components" / "action-menu.js"
        ).read_text(encoding="utf-8")

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
        self.assertIn(destroy_call, self.live_search_source)
        self.assertLess(
            self.live_search_source.index(destroy_call),
            self.live_search_source.index(replace_call),
        )

    def test_action_menu_registers_cleanup_that_restores_portaled_menu(self):
        self.assertIn("function restoreOwner(menu)", self.action_menu_source)
        self.assertIn("owner.parent.insertBefore(menu", self.action_menu_source)
        self.assertIn(
            'window.CV.registerEnhancer("actionMenu", init, destroy)',
            self.action_menu_source,
        )
