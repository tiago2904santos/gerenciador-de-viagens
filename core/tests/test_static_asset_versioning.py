from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from config.staticfiles import VersionedStaticFilesStorage


class StaticAssetVersioningContractTests(SimpleTestCase):
    def test_production_storage_hashes_javascript_module_imports(self):
        self.assertTrue(
            VersionedStaticFilesStorage.support_js_module_import_aggregation
        )
        prod_settings = (Path(settings.BASE_DIR) / "config" / "settings" / "prod.py")
        self.assertIn(
            "config.staticfiles.VersionedStaticFilesStorage",
            prod_settings.read_text(encoding="utf-8-sig"),
        )

    def test_whitenoise_e_dependencia_base_e_nao_prod_only(self):
        """O import do topo deste arquivo é o motivo de `whitenoise` ser base.

        Enquanto ele morava só em `prod.txt`, `import config.staticfiles` fazia a
        coleta da suíte inteira estourar com ModuleNotFoundError em qualquer
        ambiente que instala `dev.txt` (inclusive o hook de sessão do projeto).
        O CI não pegava: ele instala `lock.txt`, compilado de `prod.txt`.
        """
        requirements = Path(settings.BASE_DIR) / "requirements"
        base = requirements.joinpath("base.txt").read_text(encoding="utf-8-sig")
        prod = requirements.joinpath("prod.txt").read_text(encoding="utf-8-sig")
        self.assertIn("whitenoise", base)
        self.assertNotIn("whitenoise", prod)

    def test_manual_static_version_tokens_do_not_return(self):
        violations = []
        for root_name in ("templates", "static"):
            root = Path(settings.BASE_DIR) / root_name
            for path in root.rglob("*"):
                if not path.is_file() or "vendor" in path.parts:
                    continue
                try:
                    source = path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    continue
                if "?v=" in source:
                    violations.append(path.relative_to(settings.BASE_DIR).as_posix())
        self.assertEqual(violations, [])
