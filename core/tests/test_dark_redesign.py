from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class DarkRedesignContractTests(SimpleTestCase):
    def setUp(self):
        self.base_path = Path(settings.BASE_DIR) / "templates" / "base.html"
        css_root = Path(settings.BASE_DIR) / "static" / "css"
        self.tokens_path = css_root / "03-theme-dark.css"
        self.components_path = css_root / "components" / "theme-dark-components.css"
        self.base = self.base_path.read_text(encoding="utf-8")
        self.tokens_css = self.tokens_path.read_text(encoding="utf-8")
        self.components_css = self.components_path.read_text(encoding="utf-8")
        self.css = f"{self.tokens_css}\n{self.components_css}"

    def test_dark_redesign_is_the_final_global_css_layer(self):
        style_index = self.base.index("css/style.css")
        theme_dark_tokens_index = self.base.index("css/03-theme-dark.css")
        extra_css_index = self.base.index("{% block extra_css %}")
        file_picker_index = self.base.index("css/components/file-picker.css")
        action_system_index = self.base.index("css/components/action-system.css")
        record_list_index = self.base.index("css/components/record-list.css")
        filter_header_index = self.base.index("css/components/filter-header.css")
        form_panel_index = self.base.index("css/components/form-panel.css")
        app_shell_index = self.base.index("css/components/app-shell.css")
        content_cards_index = self.base.index("css/components/content-cards.css")
        document_viewer_index = self.base.index("css/components/document-viewer.css")
        dialog_index = self.base.index("css/components/dialog.css")
        theme_dark_components_index = self.base.index(
            "css/components/theme-dark-components.css"
        )

        self.assertLess(style_index, theme_dark_tokens_index)
        self.assertNotIn("css/dark-redesign.css", self.base)
        self.assertLess(extra_css_index, file_picker_index)
        self.assertLess(file_picker_index, action_system_index)
        self.assertLess(extra_css_index, action_system_index)
        self.assertLess(action_system_index, dialog_index)
        self.assertLess(action_system_index, record_list_index)
        self.assertLess(record_list_index, filter_header_index)
        self.assertLess(filter_header_index, form_panel_index)
        self.assertLess(form_panel_index, app_shell_index)
        self.assertLess(app_shell_index, content_cards_index)
        self.assertLess(content_cards_index, document_viewer_index)
        self.assertLess(document_viewer_index, dialog_index)
        self.assertLess(content_cards_index, dialog_index)
        self.assertLess(dialog_index, theme_dark_components_index)
        self.assertLess(action_system_index, theme_dark_components_index)

    def test_theme_layer_does_not_target_official_light_theme(self):
        for layer_css in (self.tokens_css, self.components_css):
            self.assertNotIn('html[data-theme="light"]', layer_css)
            self.assertNotIn('html[data-theme="light-light"]', layer_css)
            self.assertNotIn('html[data-theme="dark-light"]', layer_css)

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
            "--sidebar-width:",
        )

        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, self.tokens_css)

    def test_reduced_motion_and_mobile_shell_are_explicit(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.components_css)
        self.assertIn("@media (max-width: 600px)", self.components_css)
        self.assertIn("height: 100dvh;", self.components_css)
        self.assertIn("max-height: none;", self.components_css)

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
            "cv-date-picker.js",
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
        canonical = (headers / "page_header.html").read_text(encoding="utf-8")

        self.assertIn('<header class="page-header-stack', canonical)
        self.assertIn("components/ui/buttons/button.html", canonical)
        self.assertIn("components/ui/badges/status_badge.html", canonical)

        for wrapper_name in (
            "header_stack_simple.html",
            "header_stack_back_action.html",
            "header_stack_stepper.html",
        ):
            with self.subTest(wrapper=wrapper_name):
                self.assertFalse((headers / wrapper_name).exists())

        self.assertIn("band_only", canonical)

    def test_canonical_header_uses_a_valid_multiline_template_comment(self):
        canonical = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "ui"
            / "headers"
            / "page_header.html"
        ).read_text(encoding="utf-8")

        self.assertIn("{% comment %}", canonical)
        self.assertIn("{% endcomment %}", canonical)
        self.assertNotIn("{#\n", canonical)

    def test_canonical_button_exposes_loading_and_disabled_contracts(self):
        button = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "ui"
            / "buttons"
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
        canonical = wrapper.parents[1] / "ui" / "forms" / "field.html"
        self.assertTrue(canonical.exists())

    def test_selection_lab_uses_real_field_and_filter_components(self):
        lab = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dev"
            / "ui_lab"
            / "selects_filters.html"
        ).read_text(encoding="utf-8")

        self.assertIn('components/ui/forms/field.html', lab)
        self.assertIn('components/ui/headers/filter_page_header.html', lab)
        self.assertIn('data-collection-mode="client"', lab)
        self.assertNotIn('<select name="lab-', lab)

    def test_feedback_lab_uses_canonical_feedback_components(self):
        lab = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dev"
            / "ui_lab"
            / "feedback.html"
        ).read_text(encoding="utf-8")

        self.assertIn('components/ui/feedback/alert.html', lab)
        self.assertIn('components/ui/feedback/form_errors.html', lab)
        self.assertIn('components/ui/feedback/empty_state.html', lab)
        self.assertNotIn("ui-lab-feedback-card", lab)

    def test_canonical_feedback_supports_existing_contracts(self):
        feedback = (
            Path(settings.BASE_DIR) / "templates" / "components" / "ui" / "feedback"
        )
        alert = (feedback / "alert.html").read_text(encoding="utf-8")
        empty_state = (feedback / "empty_state.html").read_text(encoding="utf-8")
        form_errors = (feedback / "form_errors.html").read_text(encoding="utf-8")

        self.assertIn("alert-{{ alert_variant }}", alert)
        self.assertIn("alert--{{ alert_variant }}", alert)
        self.assertIn("cv-notice", alert)
        self.assertIn("cv-notice--", alert)
        self.assertIn("action_label and action_url", empty_state)
        self.assertIn('components/ui/buttons/button.html', empty_state)
        self.assertIn("form.errors or errors", form_errors)

    def test_overlay_lab_uses_the_real_confirmation_modal(self):
        lab = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dev"
            / "ui_lab"
            / "overlays.html"
        ).read_text(encoding="utf-8")
        overlay_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "overlay.js"
        ).read_text(encoding="utf-8")

        self.assertIn('components/ui/modals/delete_confirm_modal.html', lab)
        self.assertIn("data_delete_url", lab)
        self.assertNotIn("ui-lab-overlay-frame", lab)
        self.assertIn("window.CV.overlay", overlay_js)
        self.assertIn('event.key === "Tab"', overlay_js)
        self.assertIn('event.key === "Escape"', overlay_js)
        self.assertIn('data-overlay-kind="menu"', lab)
        self.assertIn("data-tooltip", lab)
        self.assertIn("data-sidebar-drawer-toggle", lab)
        self.assertIn('components/ui/menus/rich_menu_link.html', lab)

    def test_table_lab_uses_canonical_table_and_pagination(self):
        lab = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dev"
            / "ui_lab"
            / "tables.html"
        ).read_text(encoding="utf-8")
        table = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "ui"
            / "tables"
            / "data_table.html"
        ).read_text(encoding="utf-8")

        self.assertIn('components/ui/tables/data_table.html', lab)
        self.assertIn('components/ui/lists/pagination.html', lab)
        self.assertNotIn('class="ui-lab-table"', lab)
        self.assertIn('scope="col"', table)
        self.assertIn('components/ui/badges/status_badge.html', table)

    def test_file_picker_is_a_global_accessible_component(self):
        component = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "ui"
            / "forms"
            / "file_picker.html"
        ).read_text(encoding="utf-8")
        component_css = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "components"
            / "file-picker.css"
        ).read_text(encoding="utf-8")

        self.assertIn("cv-file-picker", component)
        self.assertIn("cv-file-selection", component)
        self.assertIn('{{ field_id }}-status', component)
        self.assertIn('role="status"', component)
        self.assertIn('data-file-picker-status', component)
        self.assertIn(".cv-file-picker", component_css)
        self.assertIn(".is-dragover", component_css)
        self.assertIn("@media (max-width: 640px)", component_css)

        script = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "file-picker.js"
        ).read_text(encoding="utf-8")
        self.assertIn('registerEnhancer("filePicker", init)', script)
        self.assertIn('data-file-picker-bound', script)
        self.assertIn('addEventListener("drop"', script)

    def test_confirmation_flows_share_the_canonical_dialog_structure(self):
        modals = (
            Path(settings.BASE_DIR) / "templates" / "components" / "ui" / "modals"
        )
        header = (modals / "dialog_header.html").read_text(encoding="utf-8")

        self.assertIn("cv-dialog__header", header)
        self.assertIn("cv-dialog__close", header)
        for filename, hook in (
            ("delete_confirm_modal.html", "data-delete-confirm-modal"),
            ("cancel_reason_modal.html", "data-cancel-reason-modal"),
            ("confirm_action_modal.html", "data-confirm-action-modal"),
        ):
            with self.subTest(modal=filename):
                source = (modals / filename).read_text(encoding="utf-8")
                self.assertIn("cv-dialog__panel", source)
                self.assertIn("components/ui/modals/dialog_header.html", source)
                self.assertIn("cv-dialog__body", source)
                self.assertIn("cv-dialog__footer", source)
                self.assertIn(hook, source)

        attach_script = (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "components"
            / "attach-signed-modal.js"
        ).read_text(encoding="utf-8")
        self.assertIn('registerEnhancer("attachSignedModal", init)', attach_script)
        self.assertIn("window.CV.overlay.openDialog", attach_script)
        self.assertIn("window.CV.overlay.closeDialog", attach_script)

    def test_incomplete_form_section_component_was_removed(self):
        templates = Path(settings.BASE_DIR) / "templates"
        legacy_component = templates / "components" / "ui" / "layouts" / "form_section.html"
        self.assertFalse(legacy_component.exists())

        offenders = []
        for template in templates.rglob("*.html"):
            source = template.read_text(encoding="utf-8")
            if "components/ui/layouts/form_section.html" in source:
                offenders.append(str(template.relative_to(templates)))

        self.assertEqual(offenders, [])

    def test_event_guided_flow_uses_task_sections_and_accessible_tabs(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "detalhe.html"
        ).read_text(encoding="utf-8")
        script = (
            Path(settings.BASE_DIR) / "static" / "js" / "pages" / "eventos-detalhe.js"
        ).read_text(encoding="utf-8")
        page_shell = (
            Path(settings.BASE_DIR) / "static" / "css" / "page-shell.css"
        ).read_text(encoding="utf-8")

        # `H-02`: a página passou a estender `components/page/flow_base.html`,
        # que já é coberto por teste próprio. O eyebrow não é mais escrito à mão
        # no template — vem do contexto da view (`flow_eyebrow`), então o
        # contrato certo a medir é "a view manda EVENTOS", não "o template tem a
        # string" (mesma lição do card mestre de Prestações, ver
        # `test_summary_and_document_cards_share_global_contracts`).
        self.assertIn('extends "components/page/flow_base.html"', template)
        eventos_views = (
            Path(settings.BASE_DIR) / "eventos" / "views.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"flow_eyebrow": "EVENTOS"', eventos_views)
        self.assertNotIn("CADASTRO DE OFICIO", template)
        # `H-05`: o card da etapa 1 saiu do `detalhe.html` e virou
        # `components/form/card.html` com `body_template`; os títulos dos
        # blocos internos moraram para o partial extraído.
        etapa1_body = (
            Path(settings.BASE_DIR)
            / "templates"
            / "eventos"
            / "partials"
            / "_detalhe_etapa1_body.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Identificação", etapa1_body)
        self.assertIn("Quando e onde", etapa1_body)
        self.assertIn("Documentos vinculados", etapa1_body)
        documentos_body = (
            Path(settings.BASE_DIR)
            / "templates"
            / "eventos"
            / "partials"
            / "_detalhe_documentos_body.html"
        ).read_text(encoding="utf-8")
        # Toggle segmentado (mesmo componente do Condução/Técnico/Apoio da OS)
        self.assertIn("cv-segment-toggle evento-doc-toggle", documentos_body)
        self.assertIn("data-evento-doc-toggle", documentos_body)
        self.assertIn('data-doc-tab-target="oficios"', documentos_body)
        self.assertIn("cv-form-section-card--compact", page_shell)
        self.assertIn("cv-form-section-card--described", page_shell)
        self.assertIn("event.key === 'ArrowRight'", script)
        self.assertIn("event.key === 'Home'", script)
        self.assertIn("registerEnhancer('eventoGuided', initD)", script)
        self.assertIn("components/ui/layouts/collection_header.html", template)
        self.assertIn("Roteiros do evento", template)
        self.assertIn("Ofícios e justificativas", template)
        self.assertIn("Planejamento e autorização", template)
        self.assertIn("Termos por servidor", template)
        self.assertEqual(template.count('class="cv-fab-container"'), 4)
        self.assertIn('extra_class="cv-fab"', template)

        collection_header = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "ui"
            / "layouts"
            / "collection_header.html"
        ).read_text(encoding="utf-8")
        self.assertIn("cv-form-section-header--standalone", collection_header)
        self.assertIn("cv-form-section-header--described", collection_header)
        self.assertIn("cv-form-section-header__actions", collection_header)

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
            Path(settings.BASE_DIR) / "templates" / "components" / "layout" / "sidebar.html"
        ).read_text(encoding="utf-8")
        sidebar_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "sidebar.js"
        ).read_text(encoding="utf-8")
        shell_css = (
            Path(settings.BASE_DIR) / "static" / "css" / "components" / "app-shell.css"
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
            / "components"
            / "ui"
            / "modals"
            / "confirm_delete.html"
        ).read_text(encoding="utf-8")

        self.assertIn("cv-confirm-page", component)
        self.assertIn("href=back_url", component)
        self.assertIn('variant="danger"', component)
        self.assertIn('type="submit"', component)

    def test_summary_and_document_cards_share_global_contracts(self):
        cards = Path(settings.BASE_DIR) / "templates" / "components" / "cards"
        summary = (cards / "summary_card.html").read_text(encoding="utf-8")
        document = (cards / "document_card.html").read_text(encoding="utf-8")
        plan_summary = (
            Path(settings.BASE_DIR)
            / "templates"
            / "planos_trabalho"
            / "partials"
            / "resumo_evento_card.html"
        ).read_text(encoding="utf-8")
        plan_summary_body = (
            Path(settings.BASE_DIR)
            / "templates"
            / "planos_trabalho"
            / "partials"
            / "_resumo_evento_body.html"
        ).read_text(encoding="utf-8")
        component_css = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "components"
            / "content-cards.css"
        ).read_text(encoding="utf-8")

        self.assertIn("cv-summary-tile", summary)
        self.assertIn("cv-metric", summary)
        self.assertIn("cv-metric--tile", summary)
        self.assertIn("cv-document-card", document)
        self.assertIn("cv-summary-card", plan_summary)
        # `H-05`: o grid saiu do casco e vive no partial do corpo.
        self.assertIn("cv-summary-grid--4", plan_summary_body)
        self.assertIn("@media (max-width: 640px)", component_css)

        # As classes do card mestre das 4 telas de prestação são medidas no HTML
        # **renderizado**, não no texto-fonte do arquivo da página.
        #
        # A versão anterior lia o `.html` da página com `read_text` e procurava a
        # string. Isso confundia "onde a string está escrita" com "o que a página
        # entrega": no `H-02` o card mestre passou a vir de
        # `components/form/card.html`, o HTML final ficou idêntico e o teste
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
                self.assertIn("travel-document-card", html)
                self.assertIn("travel-document-body", html)
                self.assertIn("cv-form-card__footer", html)
                self.assertIn(card, html)

    def test_cards_lab_renders_canonical_product_components(self):
        lab = (
            Path(settings.BASE_DIR)
            / "templates"
            / "dev"
            / "ui_lab"
            / "cards.html"
        ).read_text(encoding="utf-8")
        views = (Path(settings.BASE_DIR) / "core" / "views.py").read_text(encoding="utf-8")

        self.assertIn('components/cards/summary_card.html', lab)
        self.assertIn('components/lists/list_grid.html', lab)
        self.assertIn('components/lists/simple_list.html', lab)
        self.assertNotIn('dev/ui_lab/partials/_list_card.html', lab)
        self.assertNotIn('dev/ui_lab/partials/_simple_list_item.html', lab)
        self.assertIn('"dev/ui_lab/cards.html", "cards"', views)
        self.assertFalse(
            (Path(settings.BASE_DIR) / "templates" / "dev" / "ui_lab" / "partials" / "_list_card.html").exists()
        )

    def test_rich_list_cards_share_the_entity_card_contract(self):
        templates = Path(settings.BASE_DIR) / "templates"
        canonical = (
            templates / "components" / "ui" / "lists" / "entity_card.html"
        ).read_text(encoding="utf-8")
        for contract in (
            "cv-entity-card",
            "cv-entity-card__body",
            "components/ui/lists/entity_card_header.html",
            "components/ui/lists/entity_card_footer.html",
        ):
            self.assertIn(contract, canonical)

        for relative in (
            "oficios/partials/oficio_list_card.html",
            "eventos/partials/evento_list_card.html",
            "planos_trabalho/partials/plano_list_card.html",
            "ordens_servico/partials/os_list_card.html",
            "prestacoes_contas/partials/prestacao_list_card.html",
            "roteiros/partials/roteiro_list_card.html",
        ):
            with self.subTest(template=relative):
                source = (templates / relative).read_text(encoding="utf-8")
                self.assertIn('components/ui/lists/entity_card.html', source)

        generic = (
            templates / "components" / "lists" / "main_list_card.html"
        ).read_text(encoding="utf-8")
        self.assertIn("cv-entity-card", generic)
        self.assertIn("cv-entity-card__header", generic)
        self.assertIn("cv-entity-card__body", generic)
        self.assertIn("cv-entity-card__footer", generic)

    def test_document_viewer_and_signature_use_canonical_components(self):
        templates = Path(settings.BASE_DIR) / "templates"
        viewer = (templates / "components" / "documents" / "pdf_viewer.html").read_text(encoding="utf-8")
        signature = (templates / "components" / "documents" / "signature_card.html").read_text(encoding="utf-8")
        signature_body = (
            templates / "components" / "documents" / "partials" / "_signature_card_body.html"
        ).read_text(encoding="utf-8")
        viewer_page = (templates / "documentos" / "pdf_viewer.html").read_text(encoding="utf-8")
        documents_lab = (templates / "dev" / "ui_lab" / "documents.html").read_text(encoding="utf-8")
        signature_lab = (templates / "dev" / "ui_lab" / "signature.html").read_text(encoding="utf-8")
        signature_js = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "signature-actions.js"
        ).read_text(encoding="utf-8")

        self.assertIn("cv-document-viewer", viewer)
        self.assertIn("doc-pdf-canvas-wrap", viewer)
        self.assertIn('components/documents/pdf_viewer.html', viewer_page)
        self.assertIn('components/documents/pdf_viewer.html', documents_lab)
        self.assertIn("cv-signature-card", signature)
        # `H-05`: o hook de cópia mora no partial do corpo, não no casco.
        self.assertIn("data-cv-signature-copy", signature_body)
        self.assertIn('components/documents/signature_card.html', signature_lab)
        self.assertIn('components/documents/signature_card.html', (
            templates / "prestacoes_contas" / "diario_bordo_form.html"
        ).read_text(encoding="utf-8"))
        self.assertIn("[data-cv-signature-copy]", signature_js)
        self.assertNotIn("<script>", signature)
        self.assertFalse((templates / "prestacoes_contas" / "partials" / "assinatura_card.html").exists())
        self.assertFalse((Path(settings.BASE_DIR) / "static" / "css" / "documentos-viewer.css").exists())

    def test_wizard_transport_uses_canonical_section_and_action_contracts(self):
        source = (
            Path(settings.BASE_DIR) / "templates" / "oficios" / "wizard_transporte.html"
        ).read_text(encoding="utf-8")
        card = (
            Path(settings.BASE_DIR) / "templates" / "components" / "form" / "card.html"
        ).read_text(encoding="utf-8")
        header_actions = (
            Path(settings.BASE_DIR)
            / "templates"
            / "oficios"
            / "partials"
            / "_transporte_header_actions.html"
        ).read_text(encoding="utf-8")

        # `H-05`: o casco do card veio de `components/form/card.html`; a página
        # só aponta o include. O contrato visual continua no componente canônico.
        self.assertIn('components/form/card.html', source)
        self.assertIn("cv-form-section-card", card)
        self.assertIn("cv-form-section-header", card)
        self.assertIn("cv-form-section-body", card)
        self.assertIn("cv-btn cv-btn--secondary", header_actions)
        self.assertNotIn("form-section app-form-section", source)
        self.assertNotIn("btn btn-secondary", source)

    def test_event_labs_render_the_real_form_sections_and_list_card(self):
        lab_root = Path(settings.BASE_DIR) / "templates" / "dev" / "ui_lab"
        form_lab = (lab_root / "eventos_cadastro.html").read_text(encoding="utf-8")
        list_lab = (lab_root / "eventos_lista.html").read_text(encoding="utf-8")

        self.assertIn('eventos/includes/_evento_form_sections.html', form_lab)
        self.assertIn('eventos/partials/evento_list_card.html', list_lab)
        self.assertIn('css/eventos-list.css', list_lab)
        self.assertNotIn('components/lists/main_list_card.html', list_lab)
        self.assertNotIn("ui-lab-status-pill--review", form_lab)
        self.assertNotIn("ui-lab-status-pill--review", list_lab)

    def test_dashboard_uses_global_header_summary_and_module_cards(self):
        templates = Path(settings.BASE_DIR) / "templates"
        dashboard = (templates / "core" / "dashboard.html").read_text(encoding="utf-8")
        module_card = (templates / "components" / "cards" / "module_card.html").read_text(encoding="utf-8")

        self.assertIn("page-shell dashboard-page", dashboard)
        self.assertIn('components/ui/headers/page_header.html', dashboard)
        self.assertIn('components/cards/summary_card.html', dashboard)
        self.assertIn('components/cards/module_card.html', dashboard)
        self.assertNotIn("dashboard-login-inspired", dashboard)
        self.assertIn("cv-module-card", module_card)
        self.assertIn('components/ui/buttons/button.html', module_card)

        cadastros = (templates / "cadastros" / "index.html").read_text(encoding="utf-8")
        self.assertIn("page-shell cadastros-hub", cadastros)
        self.assertIn('components/ui/headers/page_header.html', cadastros)
        self.assertIn('components/cards/module_card.html', cadastros)
        self.assertNotIn("app-page-hero", cadastros)

    def test_login_is_a_solid_responsive_dark_surface_without_flow_changes(self):
        login = (
            Path(settings.BASE_DIR) / "templates" / "core" / "login.html"
        ).read_text(encoding="utf-8")
        auth_css = (
            Path(settings.BASE_DIR) / "static" / "css" / "auth.css"
        ).read_text(encoding="utf-8")

        self.assertIn('method="post"', login)
        self.assertIn("{{ form.username }}", login)
        self.assertIn("{{ form.password }}", login)
        self.assertIn("{% csrf_token %}", login)
        self.assertIn("auth-intro", login)
        self.assertIn("auth-panel", login)
        self.assertNotIn("gradient(", auth_css)
        self.assertIn("@media (max-width: 820px)", auth_css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", auth_css)

    def test_dark_primary_actions_stay_in_the_primary_blue_family(self):
        for token in (
            "--action-primary-bg:",
            "--cv-btn-primary-bg:",
            "--route-button-primary-bg:",
        ):
            with self.subTest(token=token):
                declaration = next(
                    line.strip()
                    for line in self.tokens_css.splitlines()
                    if line.strip().startswith(token)
                )
                self.assertIn("var(--color-primary", declaration)
                self.assertNotIn("var(--color-accent", declaration)

    def test_dark_wizard_filete_stays_gold_and_tracks_header_content(self):
        page_shell = (
            Path(settings.BASE_DIR) / "static" / "css" / "page-shell.css"
        ).read_text(encoding="utf-8")

        self.assertIn("--_wizard-filete-inset-block", page_shell)
        self.assertIn("bottom:        var(--_wizard-filete-inset-block);", page_shell)
        self.assertIn("top:           var(--_wizard-filete-inset-block);", page_shell)
        self.assertIn("height:        auto;", page_shell)
        self.assertIn(
            "padding: var(--space-3) var(--space-4) var(--space-3) var(--space-8);",
            page_shell,
        )

        dark_filete_rule = self.css.split(".cv-form-section-header::before", 1)[1]
        dark_filete_rule = dark_filete_rule.split("}", 1)[0]
        self.assertIn("var(--cv-card-family-accent-bg)", dark_filete_rule)
        self.assertNotIn("var(--color-primary-bright)", dark_filete_rule)

    def test_standard_simple_centers_a_tokenized_compact_panel(self):
        page_shell = (
            Path(settings.BASE_DIR) / "static" / "css" / "page-shell.css"
        ).read_text(encoding="utf-8")
        # `H-05`/Fase 9: o seletor ganhou o alias `cv-page--narrow` na mesma regra.
        marker = ".page-shell--standard-simple > .main-form-panel"
        self.assertIn(marker, page_shell)
        standard_simple = page_shell.split(marker, 1)[1]
        # Pula aliases agrupados até o bloco `{ ... }`
        standard_simple = standard_simple.split("{", 1)[1].split("}", 1)[0]

        self.assertIn("max-width: var(--layout-form-panel-max-width);", standard_simple)
        self.assertIn("margin-inline: auto;", standard_simple)
        self.assertIn(
            """{% static 'css/page-shell.css' %}">""",
            self.base,
        )

    def test_list_and_form_cards_share_the_dark_card_family(self):
        for token in (
            "--cv-card-family-bg:",
            "--cv-card-family-header-bg:",
            "--cv-card-family-header-image:",
            "--cv-card-family-border:",
            "--cv-card-family-shadow:",
            "--cv-card-family-accent-bg:",
            "--cv-card-family-accent-width:",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.tokens_css)

        wizard_header = self.css.rsplit(".cv-form-section-header {", 1)[1]
        wizard_header = wizard_header.split("}", 1)[0]
        list_header = self.css.split(".cv-record-card__id-row {", 1)[1]
        list_header = list_header.split("}", 1)[0]

        for shared_token in (
            "var(--cv-card-family-header-bg)",
            "var(--cv-card-family-header-image)",
            "var(--cv-card-family-border-strong)",
        ):
            with self.subTest(shared_token=shared_token):
                self.assertIn(shared_token, wizard_header)
                self.assertIn(shared_token, list_header)

        self.assertEqual(self.css.count(".cv-record-card__id-row::before"), 1)

        simple_form_header = self.css.split(
            ".main-form-panel > .form-section > .section-header {", 1
        )[1].split("}", 1)[0]
        simple_form_filete = self.css.split(
            ".main-form-panel > .form-section > .section-header::before {", 1
        )[1].split("}", 1)[0]

        self.assertIn("var(--cv-card-family-header-bg)", simple_form_header)
        self.assertIn("var(--cv-card-family-header-image)", simple_form_header)
        self.assertIn("var(--cv-card-family-accent-bg)", simple_form_filete)
        self.assertIn("var(--cv-card-family-accent-width)", simple_form_filete)
