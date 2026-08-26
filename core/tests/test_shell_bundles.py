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
    # O CASCO, e não a etapa: as cinco telas de prestação passaram a estender
    # `prestacoes_contas/flow_base.html` em 2026-08-19, e é ele quem declara os
    # dois blocos — como já fazem os cascos de ofício e de plano de trabalho.
    "templates/prestacoes_contas/flow_base.html",
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
# NOVO-120: 2 = shell + a camada de componentes globais. O teto existe para
# impedir o retorno dos 24 <link> que o NOVO-12 eliminou; dois arquivos fixos
# preservam esse ganho.
MAX_SHELL_CSS_LINKS = 2
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

        # NOVO-120: a camada de componentes globais entra como um <link> próprio,
        # depois do shell. O orçamento continua fechado: dois arquivos, não N.
        #
        # NOVO-70: os dois <link> passaram a ser perfis por família de rota; o que
        # este teste lê são os FALLBACKS, que é o que sobra quando a rota não tem
        # perfil (`{% static 'css/...bundle.css' %}` literal — o caminho do perfil
        # é variável e o regex acima não o vê). A ressalva antiga continua valendo
        # e agora vale para os dois: o perfil descarta regra cujo `rule_id` mudou,
        # então editar uma folha do v2 exige recapturar o manifesto
        # (`build_css_profiles.py --capture`). O gate contra esquecer é o
        # `test_build_shell_bundles_check_passes` logo acima, que reprova quando o
        # perfil no disco não bate com o que o podador geraria hoje.
        self.assertEqual(css_links, ["css/shell.bundle.css", "css/ui.bundle.css"])
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
        """O pacote de formulário carrega o que só ele precisa, e nada mais.

        Em 2026-08-20 as BASES do picker, do calendário e do select saíram de
        `fields/` e foram fundidas nas folhas do v2 (`v2/picker.css`,
        `v2/date-picker.css`, `v2/select.css`). Elas não eram legado: eram as
        declarações do próprio componente, e o arquivo v2 carregava só o delta —
        duas folhas para uma peça, em dois bundles diferentes.

        Com a fusão, o mecanismo de `@import` injetado no `style.css` também
        deixou de existir. O que este teste guarda agora é o que sobrou de
        verdade: as duas folhas exclusivas do formulário estão no pacote de
        formulário e FORA do shell padrão, na ordem em que a cascata precisa
        delas.
        """
        base = BASE_HTML.read_text(encoding="utf-8")
        shell = (ROOT / "static/css/shell.bundle.css").read_text(encoding="utf-8")
        form_shell = (
            ROOT / "static/css/shell.form-components.bundle.css"
        ).read_text(encoding="utf-8")
        sources = ("css/fields/related-route-picker.css",)

        self.assertIn("{% block shell_css %}", base)
        for source in sources:
            with self.subTest(source=source):
                self.assertNotIn(f">>> {source} >>>", shell)
                self.assertIn(f">>> {source} >>>", form_shell)

        # A folha da barra de lista vinha antes desta no pacote; foi apagada em
        # 2026-08-20 e a de escopo de wizard ficou sozinha, no fim.
        self.assertNotIn(">>> css/lists/list-header.css >>>", form_shell)

        # As bases fundidas não voltaram a ser folha própria.
        for extinta in ("fields/search-picker.css", "fields/date-picker.css",
                        "fields/custom-select.css", "fields/select.css",
                        "fields/field.css", "fields/file-picker.css"):
            with self.subTest(extinta=extinta):
                self.assertFalse((ROOT / "static/css" / extinta).exists())

        # E o que elas declaravam continua chegando à tela, pelo pacote do v2.
        ui = (ROOT / "static/css/ui.bundle.css").read_text(encoding="utf-8")
        for marca in (".search-picker__control", ".date-picker__panel",
                      ".custom-select__menu", ".file-picker"):
            with self.subTest(marca=marca):
                self.assertIn(marca, ui)

    def test_ht04_form_css_consumers_choose_the_form_shell(self):
        include_marker = (
            "{% include 'includes/form_components_css.html' "
            "with shell_css_profile_path=shell_css_profile_path only %}"
        )
        for relative in FORM_COMPONENT_STYLE_TEMPLATES:
            with self.subTest(template=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("{% block shell_css %}", text)
                self.assertIn(include_marker, text)

    def test_ui04_justificativas_uses_shared_related_route_picker_css(self):
        template = (ROOT / "templates/justificativas/index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("css/pages/justificativas.css", template)
        for obsolete in (
            "css/pages/oficios.css",
            "css/pages/roteiros.css",
            "css/pages/termos.css",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, template)

        # O `UI-04` tirou três famílias das folhas de página e as juntou numa
        # folha compartilhada. Em 2026-08-20 elas se mudaram de novo — desta vez
        # para o DONO de cada uma, que é o que a folha compartilhada nunca teve:
        #
        #   - o picker de documento vinculado → `v2/picker.css`, com o resto do
        #     picker (as classes `related-route-*`/`termo-oficio-*` ficaram: são
        #     contrato dos três motores de tela que as procuram);
        #   - o painel que se revela → `pages/justificativas.css`, a tela que o
        #     emite.
        #
        # O que o `UI-04` proibia continua proibido: nenhuma das três volta a
        # ser desenhada na folha de página de outro módulo.
        picker = (ROOT / "static/css/v2/picker.css").read_text(encoding="utf-8")
        self.assertIn(".related-route-item {", picker)
        self.assertIn(".termo-oficio-picker {", picker)
        justificativas = (
            ROOT / "static/css/pages/justificativas.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".oficio-reveal-panel {", justificativas)

        # `pages/oficios.css` foi APAGADA em 2026-08-20: nenhuma página a
        # carregava — sem `<link>`, sem bundle e sem `@import` — desde que as
        # telas de Ofícios migraram para o v2. O que ela ainda vestia de vivo
        # mudou para o dono: a família `oficio-documentos-*` para
        # `v2/document-summary.css`, o alternador de documentos do evento e as
        # três regras do picker de viatura para `v2/picker.css`.
        self.assertFalse((ROOT / "static/css/pages/oficios.css").exists())

        # `pages/termos.css` foi APAGADA em 2026-08-20: sobraram duas regras de
        # um cartão de lista que virou `c-v2.record`, e nenhuma tela a carregava.
        self.assertFalse((ROOT / "static/css/pages/termos.css").exists())

        # `pages/roteiros.css` foi APAGADA em 2026-08-20: o editor migrou para o
        # v2 em 17/08 e nenhuma página a carregava desde então.
        self.assertFalse((ROOT / "static/css/pages/roteiros.css").exists())

    def test_ui04_terms_list_nao_carrega_folha_de_pagina(self):
        """UI-04 proibia a lista de termos puxar a folha das prestações.

        Migrada para o v2 (2026-08-15), ela não carrega folha de PÁGINA alguma:
        tudo o que desenha vem do `ui.bundle.css`. A regra ficou mais forte que
        a original — e o `<link>` que voltasse seria pego aqui, qualquer que
        fosse a folha.
        """
        template = (ROOT / "templates/termos/index.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("css/pages/", template)
        self.assertNotIn("css/lists/", template)

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

    def test_ui_bundle_rebases_relative_font_urls(self):
        source = (ROOT / "static" / "css" / "v2" / "signature-fonts.css").read_text(
            encoding="utf-8"
        )
        bundle = (ROOT / "static" / "css" / "ui.bundle.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('url("../../vendor/fonts/GreatVibes-Regular.ttf")', source)
        self.assertIn('url("../vendor/fonts/GreatVibes-Regular.ttf")', bundle)

    def test_js08_components_are_lazy_and_have_static_urls(self):
        base = BASE_HTML.read_text(encoding="utf-8")
        bundle = (ROOT / "static" / "js" / "shell.bundle.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(">>> js/core/component-loader.js >>>", bundle)
        for name in (
            "card-toggle",
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
