from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase

from core.dev_forms import MainPreviewFiltersForm


ROOT = Path(settings.BASE_DIR)


class MainPreviewContractTests(SimpleTestCase):
    def test_template_compila_e_carrega_as_tres_camadas_na_ordem(self):
        get_template("core/main_preview.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")

        shared = source.index("css/dev/main.css")
        light = source.index("css/dev/main-light.css")
        dark = source.index("css/dev/main-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        self.assertIn("main-preview-shell", source)

    def test_header_compila_e_carrega_as_tres_camadas_na_ordem(self):
        get_template("cotton/dev/header.html")
        get_template("cotton/dev/header_toggle.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        toggle_component = (ROOT / "templates/cotton/dev/header_toggle.html").read_text(encoding="utf-8")
        toggle_js = (ROOT / "static/js/dev/header-toggle.js").read_text(encoding="utf-8")

        shared = source.index("css/dev/header.css")
        light = source.index("css/dev/header-light.css")
        dark = source.index("css/dev/header-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        for variant in ("standard", "toggle", "button"):
            with self.subTest(variant=variant):
                self.assertIn(f'variant="{variant}"', source)
        self.assertIn("<c-dev.header_toggle ", source)
        self.assertEqual(source.count('aria-pressed="true"'), 1)
        self.assertEqual(source.count('aria-pressed="false"'), 2)
        self.assertIn("data-main-preview-header-toggle", toggle_component)
        self.assertIn("main-preview-header__title", toggle_js)
        self.assertIn('setAttribute("aria-pressed"', toggle_js)
        self.assertIn("header-toggle.js", source)

    def test_sub_header_compila_e_carrega_as_tres_camadas_na_ordem(self):
        get_template("cotton/dev/sub_header.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")

        shared = source.index("css/dev/sub-header.css")
        light = source.index("css/dev/sub-header-light.css")
        dark = source.index("css/dev/sub-header-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        for variant in ("filters", "quick-add", "stepper"):
            with self.subTest(variant=variant):
                self.assertIn(f'variant="{variant}"', source)

    def test_form_card_compila_e_carrega_as_tres_camadas_na_ordem(self):
        get_template("cotton/dev/form_card.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/dev/form_card.html").read_text(encoding="utf-8")
        shared_css = (ROOT / "static/css/dev/form-card.css").read_text(encoding="utf-8")
        light_css = (ROOT / "static/css/dev/form-card-light.css").read_text(encoding="utf-8")
        dark_css = (ROOT / "static/css/dev/form-card-dark.css").read_text(encoding="utf-8")

        shared = source.index("css/dev/form-card.css")
        light = source.index("css/dev/form-card-light.css")
        dark = source.index("css/dev/form-card-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        self.assertIn("<c-dev.form_card ", source)
        self.assertIn("main-preview-form-card__header", component)
        self.assertIn("Origem e destinos", source)
        self.assertIn("Bate-volta diário", source)
        self.assertIn("Distância (ida e volta)", source)
        self.assertNotIn("form-section-card", source)
        self.assertNotIn("route-section-block", source)
        self.assertGreaterEqual(
            shared_css.count("background: var(--color-primary);"),
            2,
        )
        self.assertIn(
            ".main-preview-form-card__value {\n  background: var(--color-secondary);",
            shared_css,
        )
        self.assertNotIn(
            "--color-form-card-tertiary",
            shared_css + light_css + dark_css,
        )
        self.assertIn("font-family: var(--font-sans);", shared_css)
        self.assertIn("font-size: var(--font-size-xl);", shared_css)
        self.assertIn("font-size: var(--font-size-sm);", shared_css)
        self.assertIn("font-size: var(--font-size-xs);", shared_css)
        self.assertIn("font-weight: 800;", shared_css)
        self.assertIn("font-weight: 900;", shared_css)
        self.assertIn(".main-preview-form-card {\n  background: var(--color-primary);\n  border: 0;", shared_css)
        self.assertIn(".main-preview-form-card__header {\n  border-bottom: 0;", shared_css)

    def test_entity_card_compila_e_carrega_as_tres_camadas_na_ordem(self):
        get_template("cotton/dev/entity_card.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/dev/entity_card.html").read_text(encoding="utf-8")

        shared = source.index("css/dev/entity-card.css")
        light = source.index("css/dev/entity-card-light.css")
        dark = source.index("css/dev/entity-card-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        self.assertIn("<c-dev.entity_card ", source)
        self.assertIn("main-preview-entity-card__header", component)
        self.assertIn("Nº 153/2026", source)
        self.assertIn("ADEMAR SCHONS", source)
        self.assertIn("AAA-1234", source)
        self.assertIn("R$<br>1.743,30", source)
        self.assertNotIn("record-card__", source)
        self.assertNotIn("entity-card__body", source)
        shared_css = (ROOT / "static/css/dev/entity-card.css").read_text(encoding="utf-8")
        self.assertIn("font-family: var(--font-sans);", shared_css)
        self.assertIn("font-size: var(--font-size-xl);", shared_css)
        self.assertIn("font-size: var(--font-size-sm);", shared_css)
        self.assertIn("font-size: var(--font-size-xs);", shared_css)
        self.assertIn("font-weight: 800;", shared_css)
        self.assertIn("font-weight: 900;", shared_css)

    def test_collection_panel_compila_e_carrega_as_tres_camadas_na_ordem(self):
        get_template("cotton/dev/collection_panel.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/dev/collection_panel.html").read_text(encoding="utf-8")

        shared = source.index("css/dev/collection-panel.css")
        light = source.index("css/dev/collection-panel-light.css")
        dark = source.index("css/dev/collection-panel-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        self.assertIn("<c-dev.collection_panel ", source)
        self.assertIn("main-preview-collection-panel__toolbar", component)
        self.assertIn("Mostrando 1–15 de 98 registros", source)
        self.assertEqual(source.count("main-preview-collection-panel__row"), 3)
        self.assertIn("10ª SUBDIVISÃO POLICIAL", source)
        self.assertNotIn('class="collection-panel"', source)
        self.assertNotIn('class="record-row', source)

    def test_componentes_piloto_consumem_tokens_principais_sem_aliases(self):
        component_files = (
            "form-card.css",
            "form-card-light.css",
            "form-card-dark.css",
            "entity-card.css",
            "entity-card-light.css",
            "entity-card-dark.css",
            "collection-panel.css",
            "collection-panel-light.css",
            "collection-panel-dark.css",
        )
        source = "\n".join(
            (ROOT / "static/css/dev" / filename).read_text(encoding="utf-8")
            for filename in component_files
        )

        self.assertIn("background: var(--color-primary);", source)
        self.assertIn("background: var(--color-secondary);", source)
        for prefix in ("form-card", "entity-card", "collection-panel"):
            with self.subTest(prefix=prefix):
                self.assertNotIn(f"--color-{prefix}-primary", source)
                self.assertNotIn(f"--color-{prefix}-secondary", source)

    def test_cards_piloto_possuem_espacamento_uniforme_sem_divisor_no_footer(self):
        main = (ROOT / "static/css/dev/main.css").read_text(encoding="utf-8")
        entity = (ROOT / "static/css/dev/entity-card.css").read_text(encoding="utf-8")

        for selector in (
            ".main-preview-form-card-example",
            ".main-preview-entity-card-example",
            ".main-preview-collection-panel-example",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, main)
        self.assertIn("margin-top: 20px;", main)
        self.assertIn(".main-preview-entity-card__header {\n  border-bottom: 0;", entity)
        self.assertIn(".main-preview-entity-card__footer {\n  border-top: 0;", entity)
        self.assertIn("padding: 16px 20px;", entity)
        self.assertIn(".main-preview-entity-card__body {", entity)
        self.assertIn("padding: 16px;", entity)
        self.assertNotIn("padding: 16px 24px;", entity)

    def test_filtros_piloto_usam_o_componente_select_existente(self):
        # NOVO-120: `cotton/ui/forms/select.html` foi apagado; o select de campo e o
        # do trilho passaram a ser o mesmo componente global, `cotton/ui/select.html`,
        # que aceita tanto `options` quanto um `field` do Django.
        get_template("cotton/ui/select.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/ui/select.html").read_text(encoding="utf-8")
        form = MainPreviewFiltersForm()

        self.assertEqual(source.count("<c-ui.select "), 2)
        self.assertNotIn('<select class="main-preview-sub-header__field"', source)
        self.assertIn(":field=\"preview_filters.sort\"", source)
        self.assertIn(":field=\"preview_filters.status\"", source)
        self.assertIn('for="{{ preview_filters.sort.id_for_label }}">Ordenação</label>', source)
        self.assertIn('for="{{ preview_filters.status.id_for_label }}">Status</label>', source)
        self.assertIn("data-entity-picker-renderer=\"select\"", component)
        self.assertEqual(form.fields["sort"].label, "Ordenação")
        self.assertEqual(form.fields["status"].label, "Status")

        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")
        self.assertIn(":is(html[data-theme])", shared)
        self.assertIn(".main-preview-sub-header\n  .custom-select__trigger", shared)
        self.assertIn("background: var(--color-primary);", shared)
        self.assertIn("border: 0;", shared)
        self.assertIn("font-family: inherit;", shared)
        self.assertIn(".custom-select__trigger\n  .custom-select__chevron", shared)
        self.assertIn(".custom-select__chevron::before", shared)
        self.assertIn("border-bottom: 2px solid currentColor;", shared)
        self.assertIn("border-right: 2px solid currentColor;", shared)
        self.assertIn('aria-expanded="true"', shared)
        self.assertIn("transform: rotate(225deg);", shared)
        self.assertIn(":has(.main-preview-shell)", shared)
        self.assertIn(".custom-select__option-check::before", shared)
        self.assertIn("height: 10px;", shared)
        self.assertIn("width: 6px;", shared)
        self.assertIn("transform: rotate(45deg);", shared)
        self.assertIn(":is(html[data-theme]):has(.main-preview-shell)", shared)
        self.assertIn(".custom-select__option:hover:not(.custom-select__option--disabled)", shared)
        self.assertIn(".custom-select__option--focused", shared)
        self.assertIn("background: var(--color-primary);", shared)

    def test_sub_header_tem_slots_flexiveis_sem_importar_o_rail_legado(self):
        component = (ROOT / "templates/cotton/dev/sub_header.html").read_text(encoding="utf-8")
        preview = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn("{{ slot }}", component)
        self.assertEqual(preview.count("<c-dev.sub_header "), 3)
        self.assertNotIn("<c-dev.header", component)
        self.assertNotIn("main-preview-header", component)
        self.assertNotIn("main-preview-sub-header__header", component + shared)
        self.assertNotIn("list-header", component + preview + shared)
        self.assertNotIn("page-stepper", component)
        self.assertIn("page_stepper", preview)
        self.assertNotIn("wizard-stepper", component + preview + shared)

    def test_sub_header_usa_tokens_principais_sem_alias(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")
        light = (ROOT / "static/css/dev/sub-header-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/sub-header-dark.css").read_text(encoding="utf-8")

        for token in ("--color-primary", "--color-sub-header-border", "--color-sub-header-text"):
            with self.subTest(token=token):
                self.assertIn(f"{token}:", light)
                self.assertIn(f"{token}:", dark)
                self.assertIn(f"var({token})", shared)
        self.assertIn("--color-secondary:", light)
        self.assertIn("--color-secondary:", dark)
        self.assertIn("--color-secondary: #223348;", dark)
        self.assertIn("--color-secondary: #ffffff;", light)
        self.assertIn("--color-primary: #eef4fc;", light)
        self.assertIn("--color-primary: #132132;", dark)
        self.assertNotIn("color-mix", light + dark)
        self.assertNotIn("from var(", light + dark)
        self.assertNotIn("--color-sub-header-bg", shared + light + dark)

    def test_sub_header_usa_primaria_e_controles_usam_secundaria(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertGreaterEqual(shared.count("background: var(--color-primary);"), 2)
        self.assertIn(".main-preview-shell .main-preview-sub-header .main-preview-sub-header__field,", shared)
        self.assertIn(".main-preview-shell .main-preview-sub-header .main-preview-sub-header__control", shared)
        self.assertGreaterEqual(shared.count("background: var(--color-secondary);"), 3)
        self.assertIn(
            ".main-preview-sub-header__quick-add-body\n  .main-preview-sub-header__field,",
            shared,
        )

    def test_controles_do_sub_header_nao_tem_bordas(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn(".main-preview-sub-header :is(input, select, button),", shared)
        self.assertIn(".main-preview-sub-header__control", shared)
        self.assertIn("border: 0;", shared)

    def test_controles_de_filtro_usam_radius_sm(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn(".main-preview-sub-header__field,", shared)
        self.assertIn(".main-preview-sub-header__control", shared)
        self.assertIn(".custom-select__trigger", shared)
        self.assertGreaterEqual(shared.count("border-radius: var(--radius-sm);"), 3)

    def test_menu_select_piloto_usa_secundaria_hover_primaria_e_selecao_accent(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")
        light = (ROOT / "static/css/dev/sub-header-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/sub-header-dark.css").read_text(encoding="utf-8")

        self.assertIn(".custom-select__menu--v2", shared)
        self.assertIn("background: var(--color-secondary);", shared)
        self.assertIn(".custom-select__option:hover:not(.custom-select__option--disabled)", shared)
        self.assertIn(".custom-select__option--focused", shared)
        self.assertIn(".custom-select__option--selected:hover:not(.custom-select__option--disabled)", shared)
        self.assertIn(".custom-select__option--selected.custom-select__option--focused", shared)
        self.assertIn(".custom-select__option--selected {", shared)
        self.assertGreaterEqual(shared.count("background: var(--color-acent-secundary);"), 2)
        self.assertGreaterEqual(shared.count("background: var(--color-primary);"), 1)
        self.assertIn("border: 1px solid var(--color-sub-header-border);", shared)
        self.assertIn(".custom-select__menu--v2", light)
        self.assertIn("--color-primary: #eef4fc;", light)
        self.assertIn("--color-secondary: #ffffff;", light)
        self.assertGreaterEqual(light.count("--color-acent-secundary: #e3eaf2;"), 2)
        self.assertIn("--color-sub-header-border: rgba(11, 58, 102, 0.16);", light)
        self.assertIn(".custom-select__menu--v2", dark)
        self.assertIn("--color-primary: #132132;", dark)
        self.assertIn("--color-secondary: #223348;", dark)
        self.assertGreaterEqual(dark.count("--color-acent-secundary: rgba(216, 162, 27, 0.16);"), 2)
        self.assertIn("--color-sub-header-border: rgba(175, 192, 211, 0.2);", dark)

    def test_cada_sub_header_fica_emendado_ao_seu_header(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn(".main-preview-sub-header-example > .main-preview-header", shared)
        self.assertIn("border-radius: 18px 18px 0 0;", shared)
        self.assertIn(".main-preview-sub-header-example > .main-preview-sub-header", shared)
        self.assertIn("border-radius: 0 0 14px 14px;", shared)
        self.assertNotIn("border-top: 0;", shared)
        self.assertIn("margin: 0;", shared)

    def test_headers_de_teste_ficam_intactos_e_cada_sub_header_recebe_outro_header(self):
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")

        examples_start = source.index('<section class="main-preview-sub-header-example">')
        test_catalog = source[:examples_start]
        paired_catalog = source[examples_start:]

        self.assertEqual(test_catalog.count("<c-dev.header "), 3)
        self.assertEqual(test_catalog.count("<c-dev.sub_header "), 0)
        self.assertEqual(paired_catalog.count('<section class="main-preview-sub-header-example">'), 3)
        self.assertEqual(paired_catalog.count("<c-dev.header "), 3)
        self.assertEqual(paired_catalog.count("<c-dev.sub_header "), 3)

    def test_quick_add_piloto_retrata_fluxo_completo_de_justificativas(self):
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        quick_add_start = source.index('variant="quick-add"')
        quick_add_end = source.index("</c-dev.sub_header>", quick_add_start)
        quick_add = source[quick_add_start:quick_add_end]

        self.assertIn('placeholder="Buscar justificativas"', quick_add)
        self.assertIn("Ofício vinculado</h3>", quick_add)
        self.assertIn("Selecione um ou mais ofícios", quick_add)
        self.assertIn("Limpar filtros", quick_add)
        self.assertIn("Ofício 152/2026", quick_add)
        self.assertIn("Ofício 151/2026", quick_add)
        self.assertEqual(
            quick_add.count('class="main-preview-sub-header__quick-add-result"'),
            2,
        )

    def test_stepper_piloto_reusa_o_componente_oficial_de_oficios(self):
        get_template("cotton/ui/navigation/page_stepper.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        view_source = (ROOT / "core/views.py").read_text(encoding="utf-8")
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn('<c-ui.navigation.page_stepper :steps="preview_steps"', source)
        self.assertNotIn("main-preview-sub-header__steps", source + shared)
        self.assertIn('"state_class": "is-complete"', view_source)
        self.assertIn('"state_class": "is-current"', view_source)
        self.assertIn(".main-preview-sub-header--stepper .page-stepper", shared)
        self.assertIn("--stepper-marker-size: 32px;", shared)
        self.assertIn("background: transparent;", shared)
        self.assertIn("padding: var(--space-1) 0;", shared)
        self.assertIn(".page-stepper__item.is-current", shared)
        self.assertIn("background: var(--color-acent-primary);", shared)
        self.assertIn(".page-stepper__item.is-complete", shared)
        self.assertIn("background: var(--color-acent-secundary);", shared)

        light = (ROOT / "static/css/dev/sub-header-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/sub-header-dark.css").read_text(encoding="utf-8")
        self.assertIn("--color-acent-primary: #0b3a66;", light)
        self.assertIn("--color-acent-primary: #d8a21b;", dark)
        self.assertIn("--color-acent-secundary: #e3eaf2;", light)
        self.assertIn("--color-acent-secundary: rgba(216, 162, 27, 0.16);", dark)

    def test_temas_definem_fundo_e_main_tem_somente_fundo_e_padding(self):
        shared = (ROOT / "static/css/dev/main.css").read_text(encoding="utf-8")
        light = (ROOT / "static/css/dev/main-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/main-dark.css").read_text(encoding="utf-8")

        self.assertIn(".main-preview-shell .app-main", shared)
        self.assertNotIn('data-theme="light"', shared)
        self.assertNotIn('data-theme="dark"', shared)
        self.assertIn('html[data-theme="light"]', light)
        self.assertNotIn('html[data-theme="dark"]', light)
        self.assertIn('html[data-theme="dark"]', dark)
        self.assertNotIn('html[data-theme="light"]', dark)

        self.assertIn("--color-app-bg:", light)
        self.assertIn("--color-app-bg:", dark)
        self.assertNotIn("var(--app-body-bg)", light + dark)
        self.assertIn("background: var(--color-app-bg);", shared)
        self.assertIn("padding: clamp(20px, 2.6vw, 40px);", shared)
        self.assertNotIn("--main-preview-", shared + light + dark)
        self.assertNotIn("color:", shared)
        self.assertNotIn("min-height:", shared)
        self.assertNotIn(".content-wrap", shared)

    def test_header_possui_tres_variacoes_sem_importar_o_legado(self):
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        header = (ROOT / "templates/cotton/dev/header.html").read_text(encoding="utf-8")

        examples_start = source.index('<section class="main-preview-sub-header-example">')
        self.assertEqual(source[:examples_start].count("<c-dev.header "), 3)
        self.assertNotIn("main-preview__", source)
        self.assertIn("main-preview-header--{{ variant|default:'standard' }}", header)
        self.assertIn('variant == "toggle"', header)
        self.assertIn('variant == "button"', header)
        self.assertNotIn("list-header", header + source)
        self.assertNotIn("page-header", header + source)

    def test_header_e_tira_arredondada_com_token_principal_por_tema(self):
        shared = (ROOT / "static/css/dev/header.css").read_text(encoding="utf-8")
        light = (ROOT / "static/css/dev/header-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/header-dark.css").read_text(encoding="utf-8")

        self.assertIn("background: var(--color-header-bg);", shared)
        self.assertIn("border: 1px solid var(--color-header-border);", shared)
        self.assertIn("border-radius: 18px;", shared)
        self.assertIn("display: flex;", shared)
        self.assertIn("width: 100%;", shared)
        self.assertIn(".main-preview-header__title", shared)
        self.assertIn("margin: 0;", shared)
        self.assertNotIn('data-theme="light"', shared)
        self.assertNotIn('data-theme="dark"', shared)
        self.assertIn("--color-header-bg: #155b9a;", light)
        self.assertIn("--color-header-bg: #062847;", dark)
        self.assertIn("--color-header-border: rgba(255, 255, 255, 0.22);", light)
        self.assertIn("--color-header-border: rgba(255, 255, 255, 0.1);", dark)
        self.assertIn("--color-header-eyebrow: #d8a21b;", dark)
        self.assertNotIn("gradient", light + dark)
        for token in ("--color-header-eyebrow", "--color-header-title"):
            with self.subTest(token=token):
                self.assertIn(f"{token}:", light)
                self.assertIn(f"{token}:", dark)
        self.assertNotIn("var(--", light + dark)

    def test_header_usa_tipografia_oficial_do_sistema(self):
        shared = (ROOT / "static/css/dev/header.css").read_text(encoding="utf-8")

        self.assertIn("font-family: var(--font-sans);", shared)
        self.assertIn("font-size: var(--font-size-xs);", shared)
        self.assertIn("font-weight: var(--font-weight-bold);", shared)
        self.assertIn("letter-spacing: normal;", shared)
        self.assertIn("font-size: clamp(1.5rem, 2.2vw, 2rem);", shared)
        self.assertIn("font-weight: var(--font-weight-extrabold);", shared)

    def test_todo_piloto_e_seus_controles_usam_a_fonte_oficial(self):
        main = (ROOT / "static/css/dev/main.css").read_text(encoding="utf-8")
        header = (ROOT / "static/css/dev/header.css").read_text(encoding="utf-8")
        sub_header = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn(".main-preview-shell", main)
        self.assertIn("font-family: var(--font-sans);", main)
        self.assertIn("font-family: var(--font-sans);", header)
        self.assertIn("font-family: var(--font-sans);", sub_header)
        self.assertIn("font-family: inherit;", sub_header)

    def test_todas_as_variacoes_de_sub_header_possuem_borda_discreta(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")
        light = (ROOT / "static/css/dev/sub-header-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/sub-header-dark.css").read_text(encoding="utf-8")

        self.assertIn("border: 1px solid var(--color-sub-header-border);", shared)
        self.assertNotIn("border-top: 0;", shared)
        self.assertIn("--color-sub-header-border: rgba(11, 58, 102, 0.16);", light)
        self.assertIn("--color-sub-header-border: rgba(175, 192, 211, 0.2);", dark)

    def test_header_nao_permite_span_nem_status(self):
        shared = (ROOT / "static/css/dev/header.css").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/dev/header.html").read_text(encoding="utf-8")
        preview = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        header_calls = "\n".join(
            line for line in preview.splitlines() if "<c-dev.header" in line
        )

        for selector in (
            ".main-preview-header__toggle-item",
            ".main-preview-header__button",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, shared)
        self.assertIn("color: var(--color-header-title);", shared)
        self.assertNotIn("<span", component)
        self.assertNotIn("status", component.lower())
        self.assertNotIn("status=", header_calls.lower())
        self.assertNotIn("FINALIZADO (LEGADO)", header_calls)
        self.assertNotIn(".main-preview-header__status", shared)

    def test_rota_de_previa_existe_somente_sob_debug(self):
        source = (ROOT / "core/urls.py").read_text(encoding="utf-8")
        view_source = (ROOT / "core/views.py").read_text(encoding="utf-8")

        self.assertIn("if settings.DEBUG:", source)
        self.assertIn('path("dev/main-preview/", views.main_preview', source)
        self.assertIn("@login_not_required\ndef main_preview", view_source)
