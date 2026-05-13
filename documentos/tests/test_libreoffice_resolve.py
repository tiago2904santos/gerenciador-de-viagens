import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase
from django.test import override_settings

from documentos.services import libreoffice_resolve as lo_mod
from documentos.services.libreoffice_resolve import resolve_libreoffice_binary


class LibreOfficeResolveTests(SimpleTestCase):
    @override_settings(DOCUMENTOS_LIBREOFFICE_BINARY="")
    def test_explicit_setting_empty_uses_discovery(self):
        _ = resolve_libreoffice_binary()
        self.assertTrue(_ is None or Path(_).is_file())

    def test_explicit_path_wins(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            path = tmp.name
        try:
            with override_settings(DOCUMENTOS_LIBREOFFICE_BINARY=path):
                self.assertEqual(resolve_libreoffice_binary(), path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_env_documentos_libreoffice_binary_priority_over_settings(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as env_exe:
            env_path = env_exe.name
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as set_exe:
            set_path = set_exe.name
        try:
            with mock.patch.dict(os.environ, {"DOCUMENTOS_LIBREOFFICE_BINARY": env_path}, clear=False):
                with override_settings(DOCUMENTOS_LIBREOFFICE_BINARY=set_path):
                    self.assertEqual(resolve_libreoffice_binary(), env_path)
        finally:
            Path(env_path).unlink(missing_ok=True)
            Path(set_path).unlink(missing_ok=True)

    def test_verify_version_false_accepts_file_without_subprocess(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            path = tmp.name
        try:
            with override_settings(DOCUMENTOS_LIBREOFFICE_BINARY=path):
                self.assertEqual(resolve_libreoffice_binary(verify_version=False), path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_verify_version_uses_subprocess(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            path = tmp.name
        try:
            with override_settings(DOCUMENTOS_LIBREOFFICE_BINARY=path):
                with mock.patch.object(lo_mod, "verify_libreoffice_binary", return_value=False):
                    self.assertIsNone(resolve_libreoffice_binary(verify_version=True))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_shutil_which_used_when_no_explicit(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            which_path = tmp.name
        try:
            with override_settings(DOCUMENTOS_LIBREOFFICE_BINARY=""):
                with mock.patch.dict(os.environ, {}, clear=False):
                    for key in ("DOCUMENTOS_LIBREOFFICE_BINARY", "SOFFICE_PATH", "LIBREOFFICE_SOFFICE"):
                        os.environ.pop(key, None)
                side_effect = {"soffice": which_path, "libreoffice": None, "lowriter": None}

                def _which(name):
                    return side_effect.get(name)

                with mock.patch.object(lo_mod.shutil, "which", side_effect=_which):
                    out = resolve_libreoffice_binary()
            self.assertEqual(out, which_path)
        finally:
            Path(which_path).unlink(missing_ok=True)
