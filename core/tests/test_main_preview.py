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
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")

        shared = source.index("css/dev/header.css")
        light = source.index("css/dev/header-light.css")
        dark = source.index("css/dev/header-dark.css")

        self.assertLess(shared, light)
        self.assertLess(light, dark)
        for variant in ("standard", "toggle", "button"):
            with self.subTest(variant=variant):
                self.assertIn(f'variant="{variant}"', source)

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

    def test_filtros_piloto_usam_o_componente_select_existente(self):
        get_template("cotton/ui/forms/select.html")
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/ui/forms/select.html").read_text(encoding="utf-8")
        form = MainPreviewFiltersForm()

        self.assertEqual(source.count("<c-ui.forms.select "), 2)
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
        self.assertIn('html[data-theme="light"]:has(.main-preview-shell)', shared)
        self.assertIn(".custom-select__option:hover:not(.custom-select__option--disabled)", shared)
        self.assertIn(".custom-select__option--focused", shared)
        self.assertIn("background: var(--theme-list-row-hover);", shared)

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
        self.assertNotIn("page-stepper", component + preview + shared)
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
        self.assertIn("from var(--color-bg-strong)", light)
        self.assertIn(
            "--color-primary: color-mix(in srgb, var(--color-surface-muted) 88%, var(--color-secondary) 12%);",
            dark,
        )
        self.assertNotIn("--color-sub-header-bg", shared + light + dark)

    def test_sub_header_usa_primaria_e_controles_usam_secundaria(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertGreaterEqual(shared.count("background: var(--color-primary);"), 2)
        self.assertIn(".main-preview-shell .main-preview-sub-header .main-preview-sub-header__field,", shared)
        self.assertIn(".main-preview-shell .main-preview-sub-header .main-preview-sub-header__control", shared)
        self.assertGreaterEqual(shared.count("background: var(--color-secondary);"), 3)

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

    def test_menu_select_piloto_usa_a_cor_primaria_de_cada_tema(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")
        light = (ROOT / "static/css/dev/sub-header-light.css").read_text(encoding="utf-8")
        dark = (ROOT / "static/css/dev/sub-header-dark.css").read_text(encoding="utf-8")

        self.assertIn(".custom-select__menu--v2", shared)
        self.assertIn("background: var(--color-primary);", shared)
        self.assertIn("border: 1px solid var(--color-sub-header-border);", shared)
        self.assertIn(".custom-select__menu--v2", light)
        self.assertIn("--color-secondary: #ffffff;", light)
        self.assertIn("--color-sub-header-border: rgba(255, 255, 255, 0.14);", light)
        self.assertIn(".custom-select__menu--v2", dark)
        self.assertIn("--color-secondary: #223348;", dark)
        self.assertIn("--color-sub-header-border: rgba(255, 255, 255, 0.1);", dark)

    def test_cada_sub_header_fica_emendado_ao_seu_header(self):
        shared = (ROOT / "static/css/dev/sub-header.css").read_text(encoding="utf-8")

        self.assertIn(".main-preview-sub-header-example > .main-preview-header", shared)
        self.assertIn("border-radius: 18px 18px 0 0;", shared)
        self.assertIn(".main-preview-sub-header-example > .main-preview-sub-header", shared)
        self.assertIn("border-radius: 0 0 14px 14px;", shared)
        self.assertIn("border-top: 0;", shared)
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

    def test_quick_add_piloto_mantem_apenas_o_campo_de_busca(self):
        source = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")
        quick_add_start = source.index('variant="quick-add"')
        quick_add_end = source.index("</c-dev.sub_header>", quick_add_start)
        quick_add = source[quick_add_start:quick_add_end]

        self.assertIn('placeholder="Buscar ofício"', quick_add)
        self.assertNotIn("Ofício vinculado</strong>", quick_add)
        self.assertNotIn("Selecione um ou mais ofícios", quick_add)
        self.assertNotIn("Limpar filtros", quick_add)

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
        self.assertIn('main-preview-header--{{ variant }}', header)
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

    def test_header_nao_permite_span_nem_status(self):
        shared = (ROOT / "static/css/dev/header.css").read_text(encoding="utf-8")
        component = (ROOT / "templates/cotton/dev/header.html").read_text(encoding="utf-8")
        preview = (ROOT / "templates/core/main_preview.html").read_text(encoding="utf-8")

        for selector in (
            ".main-preview-header__toggle-item",
            ".main-preview-header__button",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, shared)
        self.assertIn("color: var(--color-header-title);", shared)
        self.assertNotIn("<span", component)
        self.assertNotIn("status", component.lower())
        self.assertNotIn("status=", preview.lower())
        self.assertNotIn("FINALIZADO (LEGADO)", preview)
        self.assertNotIn(".main-preview-header__status", shared)

    def test_rota_de_previa_existe_somente_sob_debug(self):
        source = (ROOT / "core/urls.py").read_text(encoding="utf-8")
        view_source = (ROOT / "core/views.py").read_text(encoding="utf-8")

        self.assertIn("if settings.DEBUG:", source)
        self.assertIn('path("dev/main-preview/", views.main_preview', source)
        self.assertIn("@login_not_required\ndef main_preview", view_source)
