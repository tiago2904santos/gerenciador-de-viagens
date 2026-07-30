from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DocumentDownloadLoadingContractTests(SimpleTestCase):
    def setUp(self):
        root = Path(settings.BASE_DIR)
        self.base = (root / "templates" / "base.html").read_text(encoding="utf-8")
        self.javascript = (
            root / "static" / "js" / "components" / "document-download.js"
        ).read_text(encoding="utf-8")
        self.styles = (
            root / "static" / "css" / "components" / "document-download-loading.css"
        ).read_text(encoding="utf-8")

    def test_shell_expoe_status_acessivel_e_assets_globais(self):
        root = Path(settings.BASE_DIR)
        css_bundle = (root / "static" / "css" / "shell.bundle.css").read_text(
            encoding="utf-8"
        )
        js_bundle = (root / "static" / "js" / "shell.bundle.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-document-loading", self.base)
        self.assertIn('role="status"', self.base)
        self.assertIn("css/shell.bundle.css", self.base)
        self.assertIn("js/shell.bundle.js", self.base)
        self.assertIn(">>> css/components/document-download-loading.css >>>", css_bundle)
        self.assertIn(">>> js/components/document-download.js >>>", js_bundle)

    def test_download_usa_resposta_real_e_preserva_nome_do_servidor(self):
        self.assertIn('a[download]:not([data-document-download-bypass])', self.javascript)
        self.assertIn("await response.blob()", self.javascript)
        self.assertIn("filenameFromDisposition", self.javascript)
        self.assertIn("URL.createObjectURL", self.javascript)

    def test_formularios_de_geracao_tambem_sao_interceptados(self):
        self.assertIn('submitter.name !== "action"', self.javascript)
        self.assertIn("/^download_/", self.javascript)
        self.assertIn("new FormData(form, submitter)", self.javascript)

    def test_redirecionamento_html_atualiza_a_url_real(self):
        self.assertIn("response.redirected && response.url", self.javascript)
        self.assertIn("window.location.assign(response.url)", self.javascript)

    def test_animacao_respeita_preferencia_de_movimento(self):
        self.assertIn("@keyframes cv-document-loading-spin", self.styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.styles)

    def test_indicador_nao_bloqueia_a_pagina(self):
        self.assertIn("pointer-events: none", self.styles)
        self.assertNotIn(
            'document.body.setAttribute("aria-busy"',
            self.javascript,
        )
        self.assertIn("error: fail", self.javascript)
