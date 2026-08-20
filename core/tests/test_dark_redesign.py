from pathlib import Path

import tinycss2
from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class DarkRedesignContractTests(SimpleTestCase):
    def setUp(self):
        self.base_path = Path(settings.BASE_DIR) / "templates" / "base.html"
        css_root = Path(settings.BASE_DIR) / "static" / "css"
        self.tokens_path = css_root / "base" / "03-theme-dark.css"
        self.base_tokens_path = css_root / "base" / "tokens.css"
        self.shared_components_path = (
            css_root / "components" / "theme-shared-components.css"
        )
        self.components_path = css_root / "components" / "theme-dark-components.css"
        self.page_shell_path = css_root / "layout" / "page-shell.css"
        self.base = self.base_path.read_text(encoding="utf-8")
        self.tokens_css = self.tokens_path.read_text(encoding="utf-8")
        self.base_tokens_css = self.base_tokens_path.read_text(encoding="utf-8")
        self.shared_components_css = self.shared_components_path.read_text(encoding="utf-8")
        self.dark_components_css = self.components_path.read_text(encoding="utf-8")
        # As duas folhas de tema encolheram 2.400 linhas em 2026-08-20: o que
        # descrevia um componente do v2 foi para a folha DELE (a pele do editor
        # de roteiro, a lista de opções, o picker, o bloco de formulário, o
        # calendário e a grade de campos).
        #
        # O que este arquivo guarda é CONTRATO DE DESENHO — "claro e escuro
        # mudam de paleta, não de geometria" —, e esse contrato não depende de
        # em qual arquivo a regra mora. Por isso a camada medida é a soma: as
        # duas folhas de tema mais as folhas que receberam as regras.
        v2 = Path(settings.BASE_DIR) / "static" / "css" / "v2"
        self.route_editor_css = (v2 / "route-editor.css").read_text(encoding="utf-8")
        # A CAMADA DE TEMA, e só ela: é sobre ela que valem as proibições
        # ("o tema não escolhe geometria", "o tema não mira o claro").
        self.components_css = "\n".join(
            (self.dark_components_css, self.shared_components_css)
        )
        # A camada de tema MAIS as folhas que receberam as regras dela. Serve às
        # asserções que guardam DESENHO — "claro e escuro mudam de paleta, não de
        # geometria" —, porque esse contrato não depende de em qual arquivo a
        # regra mora, e em 2026-08-20 seis componentes levaram a sua para casa.
        self.desenho_css = "\n".join(
            [self.components_css]
            + [
                (v2 / nome).read_text(encoding="utf-8")
                for nome in (
                    "route-editor.css",
                    "listbox.css",
                    "picker.css",
                    "form-block.css",
                    "date-picker.css",
                    "field.css",
                    "person-row.css",
                    "fact.css",
                )
            ]
        )
        self.page_shell_css = self.page_shell_path.read_text(encoding="utf-8")
        # Os asserts abaixo localizam o primeiro bloco textual de alguns
        # seletores. Preserve a ordem histórica do arquivo monolítico para que
        # o teste continue descrevendo o contrato, não a ordem dos novos
        # arquivos no bundle.
        self.css = (
            f"{self.tokens_css}\n{self.shared_components_css}\n"
            f"{self.dark_components_css}"
        )

    def test_dark_redesign_is_the_final_global_css_layer(self):
        # NOVO-12: ordem canônica está no shell.bundle.css; base só linka o bundle.
        bundle = (
            Path(settings.BASE_DIR) / "static" / "css" / "shell.bundle.css"
        ).read_text(encoding="utf-8")
        form_bundle = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "shell.form-components.bundle.css"
        ).read_text(encoding="utf-8")
        style_index = bundle.index(">>> css/style.css >>>")
        theme_dark_tokens_index = bundle.index(">>> css/base/03-theme-dark.css >>>")
        page_shell_index = bundle.index(">>> css/layout/page-shell.css >>>")
        theme_shared_components_index = bundle.index(
            ">>> css/components/theme-shared-components.css >>>"
        )
        theme_dark_components_index = bundle.index(
            ">>> css/components/theme-dark-components.css >>>"
        )
        extra_css_index = self.base.index("{% block extra_css %}")
        shell_bundle_index = self.base.index("css/shell.bundle.css")

        self.assertLess(style_index, theme_dark_tokens_index)
        self.assertNotIn("css/dark-redesign.css", self.base)
        self.assertNotIn("css/dark-redesign.css", bundle)
        self.assertLess(shell_bundle_index, extra_css_index)
        # `fields/file-picker.css` foi fundida em `v2/file-picker.css` em
        # 2026-08-20: a folha era a BASE do componente do v2, não legado.
        # `lists/filter-header.css` saiu do bundle em 2026-08-19 — ela mesma se
        # descrevia como "compat residual", e nenhuma tela emitia as classes dela.
        # `lists/record-list.css` saiu em 2026-08-20: das nove regras dela só a
        # pilha continuava viva, e foi para `v2/record.css`.
        # `actions/action-system.css` foi APAGADA em 2026-08-20, com o último
        # menu do sistema antigo (o do card de prestação) virando `c-v2.menu`.
        # Quem ocupa o lugar dela na ordem — depois dos tokens, antes das duas
        # camadas de tema — é `layout/page-shell.css`, e é isso que se mede.
        self.assertLess(page_shell_index, theme_dark_components_index)
        self.assertNotIn(">>> css/actions/action-system.css >>>", bundle)
        self.assertNotIn(">>> css/actions/action-system.css >>>", form_bundle)
        # `layout/app-shell.css` saiu do shell em 2026-08-20 junto com a pasta
        # `layout/`: a casca virou `v2/shell.css` e viaja no pacote do v2.
        # `lists/content-cards.css` saiu pelo mesmo motivo — o cartão de módulo
        # virou componente (`v2/module-card.css`) —, e
        # `pages/document-viewer.css` um dia antes, quando o visualizador virou
        # tela com folha própria (`v2/pdf-viewer.css`). `feedback/dialog.css`
        # saiu no mesmo dia: o diálogo global de `core/app.js` passou a montar o
        # `<dialog class="modal">` do v2, e a folha do `cv-dialog` ficou sem
        # nenhuma marcação para vestir.
        self.assertLess(theme_dark_components_index, theme_shared_components_index)

    def test_theme_layer_does_not_target_official_light_theme(self):
        for layer_css in (self.tokens_css, self.components_css):
            self.assertNotIn('html[data-theme="light"]', layer_css)
            self.assertNotIn('html[data-theme="light-light"]', layer_css)
            self.assertNotIn('html[data-theme="dark-light"]', layer_css)

    def test_geometry_no_longer_lives_in_dark_theme_file(self):
        def selectors_from(css):
            rules = tinycss2.parse_stylesheet(
                css,
                skip_comments=True,
                skip_whitespace=True,
            )
            selectors = []
            for rule in rules:
                if rule.type == "qualified-rule":
                    selectors.append(tinycss2.serialize(rule.prelude))
                elif rule.type == "at-rule" and rule.at_keyword == "media":
                    selectors.extend(
                        tinycss2.serialize(child.prelude)
                        for child in tinycss2.parse_rule_list(
                            rule.content,
                            skip_comments=True,
                            skip_whitespace=True,
                        )
                        if child.type == "qualified-rule"
                    )
            return selectors

        selectors = selectors_from(self.dark_components_css)
        self.assertGreater(len(selectors), 0)
        self.assertTrue(all("dark" in selector for selector in selectors))
        self.assertTrue(
            all(
                "dark" not in selector
                for selector in selectors_from(self.shared_components_css)
            )
        )

    def test_semantic_dark_contract_covers_core_component_needs(self):
        required_tokens = (
            "--color-bg:",
            "--color-surface:",
            "--color-surface-elevated:",
            "--color-text:",
            "--color-text-muted:",
            "--color-border:",
            "--color-focus:",
            "--color-success:",
            "--color-info:",
            "--color-warning:",
            "--color-danger:",
            "--color-input-bg:",
        )
        # `--sidebar-width` saiu desta lista no `NOVO-63`, e a saída é o ponto.
        #
        # Todo o resto aqui é `--color-*`: são as cores que um tema precisa
        # declarar para os componentes funcionarem. Largura de barra lateral
        # nunca foi cor — estava aqui porque o tema escuro a redefinia
        # (`clamp(238px, 17.5vw, 276px)` contra os `15%` do sistema), e a lista
        # apenas registrava esse fato.
        #
        # Agora a largura é decidida uma vez, em `tokens.css`, e vale nos dois
        # temas. Exigi-la de volta neste arquivo seria exigir que a divergência
        # voltasse.

        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, self.tokens_css)

    def test_reduced_motion_and_mobile_shell_are_explicit(self):
        """A casca do celular e o respeito a "menos movimento" continuam escritos.

        A gaveta da barra lateral saiu das folhas de tema em 2026-08-20 e foi
        para `v2/sidebar.css`, que é de quem ela é. O contrato não é sobre o
        arquivo: é que as duas coisas estejam DECLARADAS em algum lugar do
        sistema, e não deduzidas.
        """
        sidebar = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "sidebar.css"
        ).read_text(encoding="utf-8")
        casca = "\n".join((self.desenho_css, sidebar))
        self.assertIn("@media (prefers-reduced-motion: reduce)", casca)
        self.assertIn("@media (max-width: 600px)", casca)
        self.assertIn("height: 100dvh;", casca)
        self.assertIn("max-height: none;", casca)

    def test_event_wizard_geometry_is_shared_by_both_themes(self):
        # NOVO-58/NOVO-100: o claro e o escuro mudam de paleta, não de desenho.
        self.assertIn(
            ':is(html[data-theme])\n  :is([data-travel-document-wizard-step1] .travel-document-block',
            self.desenho_css,
        )
        self.assertIn(
            ':is(html[data-theme])\n  :is([data-travel-document-wizard-roteiro], [data-travel-document-wizard-step1]) .route-destinos-block.route-destinos-block--split',
            self.desenho_css,
        )
        self.assertIn(
            ':is(html[data-theme])\n  .custom-select__trigger--v2 .custom-select__chevron',
            self.desenho_css,
        )
        self.assertNotIn(
            ':is(html[data-theme="dark"])\n  .custom-select__trigger--v2 .custom-select__chevron',
            self.desenho_css,
        )

    def test_event_stepper_uses_one_shared_ring_and_shared_typography(self):
        """Um anel no passo ativo, e a mesma tipografia nos dois temas.

        A decisão é do dono (11/08/2026) e continua valendo; o que mudou foi
        onde ela mora. O `page-stepper__*` era a fileira do sistema antigo e
        morreu em 2026-08-20 — nenhum template a emitia desde que a etapa virou
        `c-v2.stepper`, e as regras que restavam vestiam ar.
        """
        stepper = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "stepper.css"
        ).read_text(encoding="utf-8")

        # O anel: um só, no nó da etapa atual, e sem aumentar o círculo.
        self.assertIn("box-shadow: 0 0 0 5px color-mix(", stepper)
        self.assertEqual(stepper.count("box-shadow: 0 0 0 5px color-mix("), 1)

        # Tipografia compartilhada: o rótulo é descrito uma vez, sob a raiz dos
        # dois temas, e o escuro não redeclara nada dele.
        self.assertIn(":is(html[data-theme]) .stepper__label {", stepper)
        self.assertNotIn(':is(html[data-theme="dark"]) .stepper__label', stepper)
        self.assertNotIn('html[data-theme="dark"] .stepper__label', stepper)

    def test_custom_select_v2_uses_one_geometry_for_both_themes(self):
        # NOVO-112: o claro espelha o escuro; somente os tokens de paleta mudam.
        selectors = (
            ".custom-select__menu--v2 {",
            ".custom-select__menu--v2 .custom-select__option {",
            ".custom-select__menu--v2 .custom-select__option--selected {",
            ".custom-select__menu--v2 .custom-select__option-check {",
        )
        for selector in selectors:
            with self.subTest(selector=selector):
                shared = f':is(html[data-theme])\n  {selector}'
                dark_only = f':is(html[data-theme="dark"])\n  {selector}'
                self.assertIn(shared, self.desenho_css)
                self.assertNotIn(dark_only, self.desenho_css)

        self.assertIn("box-shadow: var(--shadow-custom-select-menu);", self.desenho_css)
        self.assertIn("--shadow-custom-select-menu:", self.tokens_css)

    def test_entity_cards_use_one_structure_for_both_themes(self):
        """Claro e escuro mudam de PALETA, nunca de geometria.

        O contrato era medido por um par: a regra existe sob
        `:is(html[data-theme])` e NÃO existe uma gêmea sob
        `:is(html[data-theme="dark"])`. Em 2026-08-20 as regras compartilhadas
        da linha de pessoa e do bloco de fato saíram das folhas de tema — a
        medição (33 telas, 23.034 elementos, com e sem a folha) mostrou que o
        v2 já vencia cada propriedade que elas declaravam.

        O contrato ficou mais forte, e é assim que se mede agora: a peça é
        vestida pela folha do componente, e a camada de TEMA não fala dela em
        nenhum dos dois escopos. Zero regra por tema é o caso perfeito de
        "mesma geometria nos dois temas".

        `.itinerary__leg` e `.record-card__subcard` não entram: nenhum template
        as emite, e a poda as levou junto.
        """
        for classe, folha in ((".person-row", "person-row.css"), (".fact-block", "fact.css")):
            with self.subTest(classe=classe):
                self.assertIn(classe, self.desenho_css)
                self.assertNotIn(f'{classe} ', self.components_css)
                self.assertIn(
                    classe,
                    (
                        Path(settings.BASE_DIR) / "static" / "css" / "v2" / folha
                    ).read_text(encoding="utf-8"),
                    f"{classe} deixou de ser vestida por v2/{folha}",
                )

        for morta in (".itinerary__leg", ".record-card__subcard"):
            with self.subTest(morta=morta):
                self.assertNotIn(morta, self.components_css)

    def test_light_wizard_uses_blue_gray_sections_with_white_fields(self):
        # NOVO-113: a referencia aprovada inverte a hierarquia que havia
        # regredido: painel interno azul-cinza, controle branco.
        light_contracts = (
            "--wizard-card-bg: var(--color-surface);",
            "--wizard-panel-bg: var(--color-surface-powder);",
            "--wizard-field-bg: var(--color-surface);",
        )
        dark_contracts = (
            "--wizard-panel-bg: var(--color-surface-soft);",
            "--wizard-field-bg: var(--wizard-card-bg);",
        )
        for contract in light_contracts:
            self.assertIn(contract, self.base_tokens_css)
        for contract in dark_contracts:
            self.assertIn(contract, self.tokens_css)

        # A LIGAÇÃO entre `--wizard-*` e `--step1-*` era feita numa regra presa
        # aos cartões do wizard antigo (`.travel-document-card`,
        # `.oficio-roteiro-card` e mais três), e os cinco deixaram de ser
        # emitidos — a etapa é `c-v2.form_block` desde a migração dos wizards.
        # A regra saiu em 2026-08-20; os tokens ficam, porque é deles que a
        # decisão do dono (painel azul-cinza, campo branco) é feita, e o v2 os
        # lê pela escada de superfície.
        for morta in (
            "--step1-surface: var(--wizard-card-bg);",
            "--step1-panel: var(--wizard-panel-bg);",
            "--step1-field: var(--wizard-field-bg);",
        ):
            with self.subTest(ligacao=morta):
                self.assertNotIn(morta, self.desenho_css)

    def test_templates_do_not_reintroduce_inline_visual_or_event_contracts(self):
        templates = Path(settings.BASE_DIR) / "templates"
        forbidden = (" style=", " onclick=", " onchange=", " oninput=", " onsubmit=")

        for template in templates.rglob("*.html"):
            source = template.read_text(encoding="utf-8")
            for contract in forbidden:
                with self.subTest(template=template, contract=contract):
                    self.assertNotIn(contract, source)

    def test_global_app_owns_confirmation_behavior(self):
        app_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "core" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn("initConfirmSubmitContracts", app_js)
        self.assertIn("[data-confirm-submit]", app_js)
        self.assertIn("form[data-confirm-submit]", app_js)

    def test_global_app_owns_dynamic_component_initialization(self):
        app_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "core" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn("window.CV.registerEnhancer", app_js)
        self.assertIn("window.CV.enhance", app_js)
        self.assertIn("new MutationObserver", app_js)

        component_files = (
            "picker.js",
            "date-picker.js",
            "collection.js",
            "overlay.js",
        )
        components = Path(settings.BASE_DIR) / "static" / "js" / "components"
        for filename in component_files:
            with self.subTest(component=filename):
                source = (components / filename).read_text(encoding="utf-8")
                self.assertIn("registerEnhancer", source)

        picker_select = (components / "picker-select.js").read_text(encoding="utf-8")
        self.assertIn("window.CV.picker.registerRenderer(initAll)", picker_select)

    def test_page_header_has_one_canonical_markup_without_legacy_wrappers(self):
        headers = Path(settings.BASE_DIR) / "templates" / "components" / "ui" / "headers"
        canonical = (
            Path(settings.BASE_DIR) / "templates" / "cotton" / "v2" / "header.html"
        ).read_text(encoding="utf-8")

        self.assertIn('<div class="header', canonical)
        self.assertIn("<c-v2.button", canonical)

        for wrapper_name in (
            "header_stack_simple.html",
            "header_stack_back_action.html",
            "header_stack_stepper.html",
        ):
            with self.subTest(wrapper=wrapper_name):
                self.assertFalse((headers / wrapper_name).exists())

        self.assertIn("header__title", canonical)

    def test_canonical_header_uses_a_valid_multiline_template_comment(self):
        canonical = (
            Path(settings.BASE_DIR)
            / "templates"
            / "cotton"
            / "v2"
            / "header.html"
        ).read_text(encoding="utf-8")

        self.assertIn("{% comment %}", canonical)
        self.assertIn("{% endcomment %}", canonical)
        self.assertNotIn("{#\n", canonical)

    def test_canonical_button_exposes_loading_and_disabled_contracts(self):
        button = (
            Path(settings.BASE_DIR)
            / "templates"
            / "cotton"
            / "v2"
            / "button.html"
        ).read_text(encoding="utf-8")

        self.assertIn("is-loading", button)
        self.assertIn('aria-busy="true"', button)
        self.assertIn("disabled or loading", button)

    def test_legacy_field_entrypoint_was_removed(self):
        wrapper = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "forms"
            / "form_field.html"
        )

        self.assertFalse(wrapper.exists())
        canonical = Path(settings.BASE_DIR) / "templates" / "cotton" / "v2" / "form_field.html"
        self.assertTrue(canonical.exists())

    def test_canonical_feedback_supports_existing_contracts(self):
        feedback = Path(settings.BASE_DIR) / "templates" / "cotton" / "v2"
        alert = (feedback / "alert.html").read_text(encoding="utf-8")
        empty_state = (feedback / "panel.html").read_text(encoding="utf-8")
        form_errors = (feedback / "form_errors.html").read_text(encoding="utf-8")

        self.assertIn('class="alert', alert)
        self.assertIn('data-tone=', alert)
        self.assertIn("panel__empty", empty_state)
        # `HT-03`: a guarda era `form.errors or errors`, num `{% if %}` só. Virou dois
        # ramos porque a forma antiga **estourava** quando o chamador passava `errors`
        # sem `form`: variável em argumento de filtro levanta `VariableDoesNotExist`
        # em vez de cair no `string_if_invalid`, e os dois chamadores de formset são
        # exatamente assim. O contrato afirmado aqui é o mesmo — o componente atende
        # tanto um formulário quanto uma lista explícita —, e agora são duas asserções
        # em vez de uma.
        self.assertIn("{% if errors %}", form_errors)
        self.assertIn("form.non_field_errors", form_errors)

    def test_file_picker_is_a_global_accessible_component(self):
        component = (
            Path(settings.BASE_DIR)
            / "templates"
            / "cotton"
            / "v2"
            / "file_picker.html"
        ).read_text(encoding="utf-8")
        component_css = (
            # A folha vive em `v2/` desde 2026-08-20: era a base do componente,
            # não legado — `fields/` só era onde ela tinha nascido.
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "v2"
            / "file-picker.css"
        ).read_text(encoding="utf-8")

        self.assertIn("file-picker", component)
        self.assertIn("file-selection", component)
        self.assertIn('{{ field_id }}-status', component)
        self.assertIn('role="status"', component)
        self.assertIn('data-file-picker-status', component)
        self.assertIn(".file-picker", component_css)
        self.assertIn(".is-dragover", component_css)
        self.assertIn("@media (max-width: 640px)", component_css)

        script = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "file-picker.js"
        ).read_text(encoding="utf-8")
        self.assertIn('registerEnhancer("filePicker", init)', script)
        self.assertIn('data-file-picker-bound', script)
        self.assertIn('addEventListener("drop"', script)

    def test_confirmation_flows_share_the_canonical_dialog_structure(self):
        modals = Path(settings.BASE_DIR) / "templates" / "cotton" / "v2"
        shell = (modals / "modal.html").read_text(encoding="utf-8")
        self.assertIn("modal__header", shell)
        self.assertIn("modal__body", shell)
        self.assertIn("modal__actions", shell)
        for filename, hook in (
            ("delete_modal.html", "data-delete-confirm-modal"),
            ("cancel_modal.html", "data-cancel-reason-modal"),
            ("confirm_modal.html", "data-confirm-action-modal"),
            ("attach_signed_modal.html", "data-attach-signed-modal"),
        ):
            with self.subTest(modal=filename):
                source = (modals / filename).read_text(encoding="utf-8")
                self.assertIn("<c-v2.modal", source)
                self.assertIn(hook, source)

        attach_script = (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "components"
            / "attach-signed-modal.js"
        ).read_text(encoding="utf-8")
        self.assertIn('registerEnhancer("attachSignedModal", init, destroy)', attach_script)
        self.assertIn("window.CV.overlay.openDialog", attach_script)
        self.assertIn("window.CV.overlay.closeDialog", attach_script)

    def test_incomplete_form_section_component_was_removed(self):
        templates = Path(settings.BASE_DIR) / "templates"
        incomplete_component = templates / "cotton" / "ui" / "layouts" / "form_section.html"
        self.assertFalse(incomplete_component.exists())

        offenders = []
        for template in templates.rglob("*.html"):
            source = template.read_text(encoding="utf-8")
            if "cotton/ui/layouts/form_section.html" in source:
                offenders.append(str(template.relative_to(templates)))

        self.assertEqual(offenders, [])

    def test_event_guided_flow_uses_task_sections_and_accessible_tabs(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "detalhe.html"
        ).read_text(encoding="utf-8")
        script = (
            Path(settings.BASE_DIR) / "static" / "js" / "pages" / "eventos-detalhe.js"
        ).read_text(encoding="utf-8")
        # 2026-08-18: o painel migrou para o v2 e a casca virou
        # `c-v2.wizard_page` — header, trilho e stepper numa peça só. O
        # `flow_base.html` do sistema antigo saiu de cena aqui.
        self.assertIn("<c-v2.wizard_page", template)
        self.assertNotIn('extends "cotton/page/flow_base.html"', template)
        eventos_views = (
            Path(settings.BASE_DIR) / "eventos" / "views.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"flow_eyebrow": "EVENTOS"', eventos_views)
        self.assertNotIn("CADASTRO DE OFICIO", template)
        # `H-05`: o card da etapa 1 saiu do `detalhe.html` e virou
        # `cotton/form/card.html` com slot de corpo; os títulos dos
        # blocos internos moraram para o partial extraído.
        etapa1_body = (
            Path(settings.BASE_DIR)
            / "templates"
            / "eventos"
            / "partials"
            / "_detalhe_etapa1_body.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Identificação", etapa1_body)
        self.assertIn("Motivo", etapa1_body)
        # Data e destinos são assuntos independentes e usam dois blocos split
        # do v2, mantendo seus controles e motores próprios.
        self.assertIn('title="Data do evento"', etapa1_body)
        self.assertIn('title="Destinos"', etapa1_body)
        self.assertEqual(etapa1_body.count(':split="True"'), 3)
        self.assertIn("Documentos vinculados", etapa1_body)
        # Scripts de página depois do shell.bundle (extra_js), senão
        # CV.locationRows ainda não existe e destinos/cidade quebram.
        self.assertIn("{% block extra_js %}", template)
        self.assertIn("eventos-detalhe.js", template)
        self.assertLess(
            template.index("{% block extra_js %}"),
            template.index("eventos-detalhe.js"),
        )
        documentos_body = (
            Path(settings.BASE_DIR)
            / "templates"
            / "eventos"
            / "partials"
            / "_detalhe_documentos_body.html"
        ).read_text(encoding="utf-8")
        # O alternador é o toggle do sistema, agora num componente próprio
        # (`c-v2.evento_doc_toggle`) — mesmo caminho do Condução/Técnico/Apoio
        # da OS, porque `data-doc-tab-target` carrega valor e valor dentro do
        # `hook` do botão do v2 sai escapado.
        self.assertIn("<c-v2.evento_doc_toggle", documentos_body)
        doc_toggle = (
            Path(settings.BASE_DIR)
            / "templates"
            / "cotton"
            / "v2"
            / "evento_doc_toggle.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-evento-doc-toggle", doc_toggle)
        self.assertIn('data-doc-tab-target="oficios"', doc_toggle)
        self.assertIn("event.key === 'ArrowRight'", script)
        self.assertIn("event.key === 'Home'", script)
        self.assertIn("registerEnhancer('eventoGuided', initD)", script)
        # Sem botão flutuante: a ação de cada etapa foi para o cabeçalho do
        # painel dela, como nas listas já migradas.
        self.assertNotIn('class="fab-container"', template)
        self.assertNotIn('extra_class="fab"', template)

        # `collection_header.html` era conferido aqui; saiu na cascata do
        # `NOVO-44` — o componente só vivia no UI Lab, que o `BE-25` apagou.

        obsolete_wizard = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "wizard_novo.html"
        )
        self.assertFalse(obsolete_wizard.exists())

    def test_protocolos_product_module_was_removed(self):
        settings_source = (
            Path(settings.BASE_DIR) / "config" / "settings" / "base.py"
        ).read_text(encoding="utf-8")
        urls_source = (Path(settings.BASE_DIR) / "config" / "urls.py").read_text(encoding="utf-8")
        navigation_source = (
            Path(settings.BASE_DIR) / "core" / "navigation.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('"protocolos",', settings_source)
        self.assertNotIn('include("protocolos.urls")', urls_source)
        self.assertNotIn('"url_name": "protocolos:index"', navigation_source)
        self.assertFalse(list((Path(settings.BASE_DIR) / "protocolos").rglob("*.py")))
        self.assertFalse(list((Path(settings.BASE_DIR) / "integracoes" / "eprotocolo").rglob("*.py")))
        self.assertFalse(list((Path(settings.BASE_DIR) / "templates" / "protocolos").rglob("*.html")))

    def test_global_shell_has_accessible_mobile_navigation_contract(self):
        sidebar_template = (
            Path(settings.BASE_DIR) / "templates" / "cotton" / "v2" / "sidebar.html"
        ).read_text(encoding="utf-8")
        sidebar_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "sidebar.js"
        ).read_text(encoding="utf-8")
        # A pasta `layout/` foi extinta em 2026-08-20: a casca virou
        # `v2/shell.css` e o comportamento da gaveta foi para a folha da
        # própria barra, que é de quem ele é.
        shell_css = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "sidebar.css"
        ).read_text(encoding="utf-8")

        self.assertIn('href="#main-content"', self.base)
        self.assertIn('id="main-content"', self.base)
        self.assertIn("data-sidebar-drawer-toggle", self.base)
        self.assertIn('id="app-sidebar"', sidebar_template)
        self.assertIn('aria-label="Módulos da Central de Viagens"', sidebar_template)
        self.assertIn("accordion.hidden = !isOpen", sidebar_js)
        self.assertIn("sidebar.inert = !shouldOpen", sidebar_js)
        self.assertIn('event.key === "Escape"', sidebar_js)
        self.assertIn("body.has-sidebar-open", shell_css)
        self.assertIn("@media (max-width: 840px)", shell_css)

    def test_delete_confirmation_page_keeps_cancel_and_submit_actions(self):
        component = (
            Path(settings.BASE_DIR)
            / "templates"
            / "cotton"
            / "v2"
            / "confirm_delete_page.html"
        ).read_text(encoding="utf-8")

        self.assertIn("delete-page", component)
        self.assertIn(':href="back_url"', component)
        self.assertIn('variant="danger"', component)
        self.assertIn('type="submit"', component)

    def test_summary_and_document_cards_share_global_contracts(self):
        # `document_card.html` era lido aqui; saiu na cascata do `NOVO-44` —
        # os últimos citadores dele eram o UI Lab e o `list_grid`, apagados
        # pelo `BE-25`. `summary_card.html` saiu pela MESMA razão, um ID depois:
        # o único citador era o painel de `/`, esvaziado a pedido do dono, e a
        # trava de órfãos reprovou antes do merge — o que o `NOVO-44` só
        # descobriu depois. O vocabulário `metric` não morreu com ele; segue
        # vivo em `planos_trabalho`, que é o que este teste continua medindo.
        #
        # 2026-08-18: o resumo do evento migrou para o v2. O casco é o
        # `c-v2.panel` e o corpo é `c-v2.fact` — o vocabulário `summary-card` /
        # `summary-grid--4` saiu junto com a folha de página que o pintava. O que
        # este teste guarda continua sendo o mesmo: o resumo usa peças GLOBAIS, e
        # não um desenho próprio, e o corpo é responsivo por definição de grade,
        # não por um `@media` escrito só para ele.
        plan_summary = (
            Path(settings.BASE_DIR)
            / "templates"
            / "planos_trabalho"
            / "partials"
            / "_resumo_evento_record.html"
        ).read_text(encoding="utf-8")
        plan_summary_body = (
            Path(settings.BASE_DIR)
            / "templates"
            / "planos_trabalho"
            / "partials"
            / "_resumo_evento_body.html"
        ).read_text(encoding="utf-8")
        fact_css = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "fact.css"
        ).read_text(encoding="utf-8")

        # O casco passou a ser o `c-v2.record` na variante de painel
        # (`box="panel"`): o resumo é um registro com título, selo e miolo, e
        # era isso que o `panel` mais os três parciais reconstruíam à mão.
        self.assertIn("<c-v2.record", plan_summary)
        self.assertIn('box="panel"', plan_summary)
        # `H-05`: o grid saiu do casco e vive no partial do corpo.
        self.assertIn('class="fact-list"', plan_summary_body)
        self.assertNotIn('class="summary-grid', plan_summary_body)
        # A `fact-list` decide o número de colunas pelo número de fatos, sem que
        # a tela escolha uma grade — é o que substitui o `summary-grid--N`.
        self.assertIn(".fact-list", fact_css)

        # As classes do card mestre das 4 telas de prestação são medidas no HTML
        # **renderizado**, não no texto-fonte do arquivo da página.
        #
        # A versão anterior lia o `.html` da página com `read_text` e procurava a
        # string. Isso confundia "onde a string está escrita" com "o que a página
        # entrega": no `H-02` o card mestre passou a vir de
        # `cotton/form/card.html`, o HTML final ficou idêntico e o teste
        # falhou mesmo assim — ele guardava o arquivo, não o contrato.
        for relative, card in (
            ("relatorio_tecnico_form.html", "rt-wizard-card"),
            ("diario_bordo_form.html", "diario-wizard-card"),
            ("documentos_form.html", "docs-wizard-card"),
            ("consolidado.html", "consolidado-wizard-card"),
        ):
            with self.subTest(template=relative):
                html = render_to_string(
                    f"prestacoes_contas/{relative}",
                    {"page_title": "Contrato", "wizard_page_steps": []},
                )
                self.assertIn('class="panel', html)
                self.assertIn("panel__header", html)
                self.assertIn("panel__footer", html)
                self.assertIn(card, html)

    def test_rich_list_cards_share_the_entity_card_contract(self):
        templates = Path(settings.BASE_DIR) / "templates"
        canonical = (
            templates / "cotton" / "v2" / "record.html"
        ).read_text(encoding="utf-8")
        for contract in (
            "record",
            "record__body",
            "record__row",
            "record__heading",
        ):
            self.assertIn(contract, canonical)

        # Migrados para o v2 e portanto fora deste contrato: termos
        # (2026-08-15), ordens de serviço (2026-08-15), roteiros (2026-08-17),
        # eventos e prestações de contas (2026-08-18), ofícios e planos de
        # trabalho (2026-08-18). Com os dois últimos, NENHUM card de lista usa
        # mais o `entity_card` — o contrato segue afirmado sobre o componente
        # canônico acima, que ainda serve o detalhe do evento até ele migrar.
        # Foram apagados junto os arquivos que só existiam para o motor legado:
        # `_oficio_card_body.html`, `_plano_card_body.html`,
        # `roteiro_list_card.html`, `_roteiro_card_body.html` e o
        # `includes/performance/entity_card_flat.html`.
        for relative in ():
            with self.subTest(template=relative):
                source = (templates / relative).read_text(encoding="utf-8")
                self.assertTrue(
                    '<c-ui.lists.entity_card' in source
                    or 'include "cotton/ui/lists/entity_card.html"' in source
                    or 'include "includes/performance/entity_card_flat.html"' in source
                    or (
                        "entity-card record-card" in source
                        and "entity-card__footer record-card__footer" in source
                    ),
                    msg=f"{relative} deixou de usar o contrato canônico de entity card",
                )

        # `HT-06`: o antigo `main_list_card.html` foi apagado. Ele afirmava o
        # mesmo contrato de `entity_card.html` e **nada o renderizava** — o único
        # citador do repositório era este arquivo de teste, e ainda por cima numa
        # asserção de que ele *não* aparece no lab (linha ~681). O contrato de
        # `entity-card` continua afirmado logo acima, sobre o componente canônico.

    def test_document_viewer_and_signature_use_canonical_components(self):
        """O visualizador é TELA desde 2026-08-19.

        Era um componente com um consumidor só e um ramo `is_demo` que nenhuma
        tela chamava. O que se guarda aqui continua sendo o mesmo: os botões da
        barra são os do sistema, e os `id` que o `documentos-pdf-viewer.js`
        procura seguem existindo.
        """
        templates = Path(settings.BASE_DIR) / "templates"
        viewer_page = (templates / "documentos" / "pdf_viewer.html").read_text(encoding="utf-8")
        signature_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "signature-actions.js"
        ).read_text(encoding="utf-8")

        self.assertFalse((templates / "cotton" / "documents" / "pdf_viewer.html").exists())
        self.assertIn("<c-v2.button", viewer_page)
        self.assertNotIn("cv-btn", viewer_page)
        for gancho in ("doc-pdf-canvas-wrap", "doc-pdf-thumbs", "doc-pdf-zoom", "doc-pdf-page-label"):
            self.assertIn(gancho, viewer_page)
        self.assertIn("[data-cv-signature-copy]", signature_js)
        self.assertFalse((templates / "cotton" / "documents" / "signature_card.html").exists())
        self.assertFalse((templates / "prestacoes_contas" / "partials" / "assinatura_card.html").exists())
        self.assertFalse((Path(settings.BASE_DIR) / "static" / "css" / "documentos-viewer.css").exists())

    def test_wizard_transport_uses_canonical_section_and_action_contracts(self):
        """A etapa de transporte não desenha caixa nem botão próprios.

        O `H-05` guardava isto contra `cotton/form/card.html`, o cartão do
        sistema antigo. Com a migração de Ofícios para o v2
        (`NOVO-20260818-213853-fab772ef1b6e`) o casco passou a ser o
        `c-v2.panel`, e o rodapé o `c-v2.card_footer` — o contrato é o mesmo,
        muda o componente canônico que o cumpre.
        """
        templates = Path(settings.BASE_DIR) / "templates"
        source = (templates / "oficios" / "wizard_transporte.html").read_text(encoding="utf-8")
        panel = (templates / "cotton" / "v2" / "panel.html").read_text(encoding="utf-8")

        self.assertIn("<c-v2.panel", source)
        self.assertIn("<c-v2.card_footer", source)
        self.assertIn('class="panel', panel)
        self.assertIn("panel__header", panel)
        self.assertIn("panel__empty", panel)
        # Nada do vocabulário anterior volta pela porta dos fundos.
        self.assertNotIn("<c-form.card", source)
        self.assertNotIn("form-section app-form-section", source)
        self.assertNotIn("btn btn-secondary", source)
        self.assertNotIn("<button", source)

    def test_dashboard_uses_global_header_summary_and_module_cards(self):
        templates = Path(settings.BASE_DIR) / "templates"
        dashboard = (templates / "core" / "dashboard.html").read_text(encoding="utf-8")
        module_card = (templates / "cotton" / "v2" / "module_card.html").read_text(encoding="utf-8")

        # O painel foi esvaziado a pedido do dono. O contrato mudou de "usa os
        # tres componentes globais" para "**nao tem vocabulario proprio**": o que
        # sobrou em `/` e cabecalho de pagina mais cartao de modulo, e nenhuma
        # classe `dashboard-*` pode voltar — era ela que justificava um CSS so
        # dela (`dashboard.css`, apagado) e 4 blocos no tema escuro.
        #
        # 2026-08-20: `page-shell` saiu das duas telas. Ele era o casco do
        # sistema antigo, e o do v2 é a `list-page` — a mesma casca que as
        # listas usam. O cartão perdeu o prefixo `cv-`: passou a ser
        # `module-card`, com folha própria (`v2/module-card.css`).
        self.assertIn('class="list-page"', dashboard)
        self.assertIn('<c-v2.header', dashboard)
        self.assertIn('<c-v2.module_card', dashboard)
        self.assertNotIn("dashboard-page", dashboard)
        self.assertNotIn('class="page-shell', dashboard)
        self.assertNotIn("summary_card.html", dashboard)
        self.assertIn('class="module-card', module_card)
        self.assertIn('<c-v2.button', module_card)

        cadastros = (templates / "cadastros" / "index.html").read_text(encoding="utf-8")
        # `catalog-hub` / `catalog-grid` / `catalog-section` sairam em
        # 2026-08-20: as tres classes **nao tinham CSS em lugar nenhum** — os
        # cartoes da Administracao vinham empilhados numa coluna. A tela e a
        # mesma casca das listas mais a grade do cartao de modulo.
        self.assertIn('class="list-page"', cadastros)
        self.assertIn('class="module-card-grid"', cadastros)
        self.assertIn('<c-v2.header', cadastros)
        self.assertIn('<c-v2.module_card', cadastros)
        self.assertNotIn("app-page-hero", cadastros)
        # A busca é pela CLASSE, não pelo nome: o comentário da tela cita o
        # casco antigo para registrar de onde ela veio.
        self.assertNotIn('class="page-shell', cadastros)

    def test_login_is_a_solid_responsive_dark_surface_without_flow_changes(self):
        """A folha mudou de lugar com a reconstrução no v2.

        Os campos deixaram de ser `{{ form.username }}` cru: passam por
        `c-v2.input`, que é quem os põe na mesma superfície do resto do sistema
        (`NOVO-20260819-220313-df2a5685481a`). O que este contrato guarda
        continua sendo o mesmo — o POST, o CSRF, as duas colunas, e a folha sem
        gradiente, com quebra estreita e respeito a movimento reduzido.
        """
        login = (
            Path(settings.BASE_DIR) / "templates" / "core" / "login.html"
        ).read_text(encoding="utf-8")
        auth_css = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "auth.css"
        ).read_text(encoding="utf-8")

        self.assertIn('method="post"', login)
        self.assertIn(':field="form.username"', login)
        self.assertIn(':field="form.password"', login)
        self.assertIn("{% csrf_token %}", login)
        self.assertIn("auth-intro", login)
        self.assertIn("auth-panel", login)
        self.assertNotIn("gradient(", auth_css)
        self.assertIn("@media (max-width: 820px)", auth_css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", auth_css)

    def test_dark_primary_actions_stay_in_the_primary_blue_family(self):
        for token in (
            "--action-primary-bg:",
            "--btn-primary-bg:",
            "--route-button-primary-bg:",
        ):
            with self.subTest(token=token):
                # A ÚLTIMA declaração, não a primeira: é a que vence a cascata.
                # Até a E7 dava no mesmo, porque cada token aparecia uma vez só
                # neste arquivo. Ao dissolver `base/theme.css` (UI-03) o bloco
                # escuro dele passou a conviver aqui, e com ele 87 declarações
                # que o bloco de baixo já sobrescrevia desde sempre (`NOVO-82`).
                # Ler a primeira passou a significar ler justamente a perdedora.
                declaration = [
                    line.strip()
                    for line in self.tokens_css.splitlines()
                    if line.strip().startswith(token)
                ][-1]
                self.assertIn("var(--color-primary", declaration)
                self.assertNotIn("var(--color-accent", declaration)

    def test_o_filete_do_wizard_antigo_nao_voltou(self):
        """O filete dourado era do cabeçalho de seção do sistema antigo.

        `--_wizard-filete-*` desenhava a listra vertical de
        `.cv-form-section-header`, que saiu em 2026-08-20 com o resto do casco.
        No v2 quem marca a seção é o título do `form_block`, sem listra: um
        bloco não precisa de duas marcas para dizer onde começa.
        """
        page_shell = (
            Path(settings.BASE_DIR) / "static" / "css" / "layout" / "page-shell.css"
        ).read_text(encoding="utf-8")
        self.assertNotIn("--_wizard-filete", page_shell)
        self.assertNotIn(".cv-form-section-header", page_shell)

    def test_o_casco_antigo_nao_centraliza_mais_nada(self):
        """`page-shell--standard-simple > .main-form-panel` não existe mais.

        Era o painel centrado com largura máxima do sistema antigo. As cinco
        telas que o usavam migraram em 2026-08-20 (índice de Documentos, modelos
        de texto, as duas prévias de termo e a espera de geração): a casca do v2
        é a `form-page`, e a largura vem do `content-wrap`.
        """
        page_shell = (
            Path(settings.BASE_DIR) / "static" / "css" / "layout" / "page-shell.css"
        ).read_text(encoding="utf-8")
        self.assertNotIn(".page-shell--standard-simple", page_shell)
        self.assertNotIn(".main-form-panel", page_shell)
        self.assertIn("css/shell.bundle.css", self.base)

    def test_a_familia_de_cartao_do_sistema_antigo_nao_voltou(self):
        """`--card-family-*` morreu com os três cartões que a consumiam.

        O contrato original era "lista, wizard e formulário simples usam a MESMA
        família de cartão" — sete tokens compartilhados por `.record-card`,
        `.cv-form-section-header` e `.main-form-panel > .form-section >
        .section-header`. Em 2026-08-20 os três deixaram de existir: a lista é
        `c-v2.record`, o wizard é `c-v2.form_block` e o formulário simples é a
        `form-page`. A família ficou sem consumidor.

        O que o v2 põe no lugar é a escada de superfície (`--surface-rail`,
        `--surface-field`), que vale para os três pelo mesmo motivo: eles são a
        mesma caixa em papéis diferentes.
        """
        for morta in (".record-card {", ".cv-form-section-header {"):
            with self.subTest(seletor=morta):
                self.assertNotIn(morta, self.desenho_css)

        folhas = " ".join(
            caminho.read_text(encoding="utf-8")
            for caminho in (Path(settings.BASE_DIR) / "static" / "css").rglob("*.css")
            if "bundle" not in caminho.name and "profiles" not in str(caminho)
        )
        # O CABEÇALHO da família e a listra de destaque morreram com os três
        # cartões. `--card-family-bg`, `-border` e `-shadow` seguem vivos: a
        # faixa do cartão de OS e a perna do itinerário ainda os leem, e são
        # superfície, não cabeçalho.
        for morto in (
            "var(--card-family-header-image)",
            "var(--card-family-border-strong)",
            "var(--card-family-accent-bg)",
            "var(--card-family-accent-shadow)",
            "var(--card-family-accent-width)",
        ):
            with self.subTest(token=morto):
                self.assertNotIn(morto, folhas)
