import builtins
import sys
from unittest import mock

from django.test import SimpleTestCase
from django.test import override_settings

from documentos.services import pdf_engine as pe
from documentos.services.pdf_engine import PdfEngineResolution
from documentos.services.pdf_engine import build_pdf_unavailable_message
from documentos.services.pdf_engine import resolve_pdf_engine


class WeasyImportProbeTests(SimpleTestCase):
    def test_weasy_import_ok_trata_oserror_como_indisponivel(self):
        real_import = builtins.__import__

        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "weasyprint":
                raise OSError("cannot load library 'libgobject-2.0-0'")
            return real_import(name, globals, locals, fromlist, level)

        saved = sys.modules.pop("weasyprint", None)
        try:
            with mock.patch.object(builtins, "__import__", guarded):
                self.assertFalse(pe._weasy_import_ok())
        finally:
            if saved is not None:
                sys.modules["weasyprint"] = saved


class ResolvePdfEngineTests(SimpleTestCase):
    @mock.patch.object(pe, "resolve_libreoffice_binary", return_value="/x/soffice")
    def test_libreoffice_disponivel_exige_verificacao_do_executavel(self, m_resolve):
        self.assertTrue(pe._libreoffice_ok())
        m_resolve.assert_called_once_with(verify_version=True)

    @mock.patch.object(pe, "_word_ok", return_value=True)
    @mock.patch.object(pe, "_libreoffice_ok", return_value=False)
    @mock.patch.object(pe, "_weasy_import_ok", return_value=True)
    @mock.patch.object(pe, "_simple_fallback_allowed", return_value=False)
    @mock.patch.object(pe.platform, "system", return_value="Windows")
    def test_auto_windows_prefere_word(self, *_m):
        r = resolve_pdf_engine(explicit_setting="auto", prefer_docx_pipeline=True)
        self.assertEqual(r.attempt_chain[0], "word_com")

    @mock.patch.object(pe, "_word_ok", return_value=False)
    @mock.patch.object(pe, "_libreoffice_ok", return_value=True)
    @mock.patch.object(pe, "_weasy_import_ok", return_value=True)
    @mock.patch.object(pe, "_simple_fallback_allowed", return_value=False)
    @mock.patch.object(pe, "sys_platform_is_linux", return_value=True)
    @mock.patch.object(pe.platform, "system", return_value="Linux")
    def test_auto_linux_prefere_libreoffice(self, *_m):
        r = resolve_pdf_engine(explicit_setting="auto", prefer_docx_pipeline=True)
        self.assertEqual(r.attempt_chain[0], "libreoffice")

    @override_settings(DOCUMENTOS_PDF_AUTO_FALLBACK=True)
    @mock.patch.object(pe, "_word_ok", return_value=False)
    @mock.patch.object(pe, "_libreoffice_ok", return_value=False)
    @mock.patch.object(pe, "_weasy_import_ok", return_value=True)
    @mock.patch.object(pe, "_simple_fallback_allowed", return_value=False)
    def test_explicit_libreoffice_indisponivel_cai_para_weasy(self, *_m):
        r = resolve_pdf_engine(explicit_setting="libreoffice", prefer_docx_pipeline=True)
        self.assertIn("weasyprint", r.attempt_chain)

    def test_build_pdf_unavailable_message_contem_diagnostico(self):
        r = PdfEngineResolution(
            attempt_chain=(),
            reason="x",
            missing_engines=("libreoffice",),
            install_hints=("hint1",),
        )
        msg = build_pdf_unavailable_message(r)
        self.assertIn("documentos_check", msg)
