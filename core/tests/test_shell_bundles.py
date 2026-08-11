"""Gate NOVO-12 — bundles de entrega do shell atualizados e base.html enxuto."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
BASE_HTML = ROOT / "templates" / "base.html"

FORM_COMPONENT_TEMPLATES = (
    "templates/cadastros/configuracao/form.html",
    "templates/cadastros/servidores/form.html",
    "templates/cadastros/viaturas/form.html",
    "templates/eventos/detalhe.html",
    "templates/justificativas/index.html",
    "templates/oficios/wizard_base.html",
    "templates/ordens_servico/form.html",
    "templates/planos_trabalho/wizard_base.html",
    "templates/prestacoes_contas/diario_motorista_form.html",
    "templates/roteiros/roteiro_form_page.html",
    "templates/termos/form.html",
)

FORM_COMPONENT_STYLE_TEMPLATES = FORM_COMPONENT_TEMPLATES + (
    "templates/eventos/index.html",
    "templates/oficios/index.html",
    "templates/ordens_servico/index.html",
    "templates/planos_trabalho/index.html",
    "templates/prestacoes_contas/index.html",
    "templates/roteiros/index.html",
    "templates/termos/index.html",
)

DIRECT_FORM_API_CONSUMERS = (
    "static/js/pages/configuracoes.js",
    "static/js/pages/diario-motorista.js",
    "static/js/pages/eventos-detalhe.js",
    "static/js/pages/justificativas-index.js",
    "static/js/pages/oficios-transporte.js",
    "static/js/pages/ordens-servico-form.js",
    "static/js/pages/planos-trabalho-wizard.js",
    "static/js/pages/roteiros/editor/index.js",
    "static/js/pages/roteiros-wizard.js",
    "static/js/pages/servidores-form.js",
    "static/js/pages/termos-form.js",
    "static/js/pages/viaturas-form.js",
)

# Limites do shell após o bundle (extra_css/extra_js por página ficam de fora).
MAX_SHELL_CSS_LINKS = 1
MAX_SHELL_HEAD_SCRIPTS = 2  # theme-shared + theme-init
MAX_SHELL_BODY_SCRIPTS = 1  # shell.bundle.js


class ShellBundleGateTests(SimpleTestCase):
    def test_build_shell_bundles_check_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_shell_bundles.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"bundles desatualizados:\n{result.stdout}\n{result.stderr}",
        )

    def test_base_html_shell_asset_budget(self):
        text = BASE_HTML.read_text(encoding="utf-8")
        css_links = re.findall(r"static '([^']+\.css)'", text)
        scripts = re.findall(
            r'<script\b[^>]*?\ssrc="{% static \'([^\']+\.js)\' %}"',
            text,
            flags=re.S,
        )

        self.assertEqual(css_links, ["css/shell.bundle.css"])
        self.assertEqual(
            scripts,
            [
                "js/core/theme-shared.js",
                "js/core/theme-init.js",
                "js/shell.bundle.js",
            ],
        )
        self.assertLessEqual(len(css_links), MAX_SHELL_CSS_LINKS)
        self.assertEqual(len(scripts[:2]), MAX_SHELL_HEAD_SCRIPTS)
        self.assertEqual(len(scripts[2:]), MAX_SHELL_BODY_SCRIPTS)

    def test_ht04_form_css_leaves_the_default_shell_without_changing_order(self):
        base = BASE_HTML.read_text(encoding="utf-8")
        shell = (ROOT / "static/css/shell.bundle.css").read_text(encoding="utf-8")
        form_shell = (
            ROOT / "static/css/shell.form-components.bundle.css"
        ).read_text(encoding="utf-8")
        sources = (
            "css/fields/date-picker.css",
            "css/fields/file-picker.css",
        )

        self.assertIn("{% block shell_css %}", base)
        for source in sources:
            with self.subTest(source=source):
                self.assertNotIn(f">>> {source} >>>", shell)
                self.assertIn(f">>> {source} >>>", form_shell)

        self.assertLess(
            form_shell.index(">>> css/fields/field.css >>>"),
            form_shell.index(">>> css/fields/date-picker.css >>>"),
        )
        self.assertLess(
            form_shell.index(">>> css/fields/file-picker.css >>>"),
            form_shell.index(">>> css/actions/action-system.css >>>"),
        )

    def test_ht04_form_css_consumers_choose_the_form_shell(self):
        marker = "{% include 'includes/form_components_css.html' only %}"
        for relative in FORM_COMPONENT_STYLE_TEMPLATES:
            with self.subTest(template=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("{% block shell_css %}", text)
                self.assertIn(marker, text)

    def test_base_html_keeps_extra_blocks(self):
        text = BASE_HTML.read_text(encoding="utf-8")
        self.assertIn("{% block extra_css %}", text)
        self.assertIn("{% block extra_css_after_theme %}", text)
        self.assertIn("{% block component_js %}", text)
        self.assertIn("{% block extra_js %}", text)
        self.assertLess(
            text.index("src=\"{% static 'js/shell.bundle.js' %}\""),
            text.index("{% block component_js %}"),
        )
        self.assertLess(
            text.index("{% block component_js %}"),
            text.index("{% block extra_js %}"),
        )

    def test_bundle_markers_cover_canonical_sources(self):
        css = (ROOT / "static" / "css" / "shell.bundle.css").read_text(encoding="utf-8")
        js = (ROOT / "static" / "js" / "shell.bundle.js").read_text(encoding="utf-8")
        self.assertIn("AUTO-GENERATED by scripts/build_shell_bundles.py", css)
        self.assertIn("AUTO-GENERATED by scripts/build_shell_bundles.py", js)
        self.assertIn(">>> css/layout/page-shell.css >>>", css)
        self.assertIn(">>> js/core/http.js >>>", js)
        self.assertNotIn(">>> js/core/theme-init.js >>>", js)

    def test_js08_components_are_lazy_and_have_static_urls(self):
        base = BASE_HTML.read_text(encoding="utf-8")
        bundle = (ROOT / "static" / "js" / "shell.bundle.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(">>> js/core/component-loader.js >>>", bundle)
        for name in (
            "card-toggle",
            "segment-nav",
            "file-picker",
            "signature-actions",
            "extra-download",
        ):
            with self.subTest(component=name):
                source = f"js/components/{name}.js"
                self.assertNotIn(f">>> {source} >>>", bundle)
                self.assertIn(f"{{% static '{source}' %}}", base)

    def test_ht04_form_components_leave_the_global_shell(self):
        base = BASE_HTML.read_text(encoding="utf-8")
        shell = (ROOT / "static" / "js" / "shell.bundle.js").read_text(
            encoding="utf-8"
        )
        forms = (ROOT / "static" / "js" / "form-components.bundle.js").read_text(
            encoding="utf-8"
        )
        sources = (
            "js/components/picker-parts.js",
            "js/components/picker.js",
            "js/components/picker-select.js",
            "js/components/location-rows.js",
            "js/components/document-source.js",
            "js/components/document-search.js",
            "js/components/date-picker.js",
        )

        self.assertIn("{% block component_js %}", base)
        self.assertIn("{% static 'js/form-components.bundle.js' %}", base)
        for source in sources:
            with self.subTest(source=source):
                self.assertNotIn(f">>> {source} >>>", shell)
                self.assertIn(f">>> {source} >>>", forms)

        self.assertLess(
            forms.index(">>> js/components/picker-parts.js >>>"),
            forms.index(">>> js/components/picker.js >>>"),
        )

    def test_ht04_direct_api_consumers_declare_the_form_bundle(self):
        marker = "{% include 'includes/form_components_js.html' only %}"
        for relative in FORM_COMPONENT_TEMPLATES:
            with self.subTest(template=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("{% block component_js %}", text)
                self.assertIn(marker, text)

    def test_ht04_direct_api_consumer_inventory_is_complete(self):
        api = re.compile(
            r"(?:window\.)?CV\.(?:pickerParts|picker|locationRows|"
            r"documentSource|documentSearch|datePicker)"
        )
        discovered = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "static" / "js" / "pages").rglob("*.js")
            if api.search(path.read_text(encoding="utf-8"))
        }
        self.assertEqual(discovered, set(DIRECT_FORM_API_CONSUMERS))

    def test_ht04_remaining_large_components_are_lazy(self):
        base = BASE_HTML.read_text(encoding="utf-8")
        shell = (ROOT / "static" / "js" / "shell.bundle.js").read_text(
            encoding="utf-8"
        )
        for name in ("attach-signed-modal", "wizard-sticky-header"):
            with self.subTest(component=name):
                source = f"js/components/{name}.js"
                self.assertNotIn(f">>> {source} >>>", shell)
                self.assertIn(f"{{% static '{source}' %}}", base)
