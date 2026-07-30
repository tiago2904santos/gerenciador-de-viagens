from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class OverlayContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.components = cls.root / "static" / "js" / "components"
        cls.overlay = (cls.components / "overlay.js").read_text(encoding="utf-8")

    def test_one_namespace_and_enhancer_own_overlay_lifecycle(self):
        self.assertIn("window.CV.overlay = {", self.overlay)
        self.assertIn('window.CV.registerEnhancer("overlay", init, destroy)', self.overlay)
        for contract in (
            "openDialog: openDialog",
            "closeDialog: closeDialog",
            "attachDropdown: attachDropdown",
            "closeMenus: closeMenus",
        ):
            self.assertIn(contract, self.overlay)

    def test_legacy_overlay_engines_are_absent(self):
        for filename in (
            "action-menu.js",
            "cancel-reason-modal.js",
            "confirm-action-modal.js",
            "cv-floating-dropdown.js",
            "delete-confirm-modal.js",
        ):
            with self.subTest(component=filename):
                self.assertFalse((self.components / filename).exists())

        sources = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (self.root / "static" / "js").rglob("*.js")
        )
        self.assertNotIn("window.CV.dialogs", sources)
        self.assertNotIn("window.CV.actionMenu", sources)
        self.assertNotIn("window.CvFloatingDropdown", sources)

        templates = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (self.root / "templates").rglob("*.html")
        )
        self.assertNotIn("data-action-menu-trigger", templates)
        self.assertNotIn("data-action-menu-target", templates)
        self.assertNotIn("data-delete-modal-trigger", templates)
        self.assertNotIn("data-cancel-modal-trigger", templates)
        self.assertNotIn("data-confirm-action-trigger", templates)
        self.assertIn('data-overlay-kind="menu"', templates)
        self.assertIn('data-overlay-kind="dialog"', templates)
        self.assertIn("data-overlay-panel", templates)
        self.assertIn("data-overlay-close", templates)

    def test_consumers_use_overlay_api(self):
        app = (self.root / "static" / "js" / "core" / "app.js").read_text(
            encoding="utf-8"
        )
        attachment = (self.components / "attach-signed-modal.js").read_text(
            encoding="utf-8"
        )
        picker = (self.components / "picker.js").read_text(encoding="utf-8")
        picker_select = (self.components / "picker-select.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("window.CV.overlay.openDialog", app)
        self.assertIn("window.CV.overlay.openDialog", attachment)
        self.assertIn("window.CV.overlay.attachDropdown", picker)
        self.assertIn("window.CV.overlay.attachDropdown", picker_select)

    def test_base_loads_only_the_canonical_overlay_engine(self):
        base = (self.root / "templates" / "base.html").read_text(encoding="utf-8")
        bundle = (self.root / "static" / "js" / "shell.bundle.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("js/shell.bundle.js", base)
        self.assertIn(">>> js/components/overlay.js >>>", bundle)
        for filename in (
            "action-menu.js",
            "cancel-reason-modal.js",
            "confirm-action-modal.js",
            "cv-floating-dropdown.js",
            "delete-confirm-modal.js",
        ):
            self.assertNotIn(filename, base)
            self.assertNotIn(f">>> js/components/{filename} >>>", bundle)
