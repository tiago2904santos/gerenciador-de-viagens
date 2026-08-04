import re

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

    def test_referencias_de_sourcemap_apontam_para_arquivo_existente(self):
        """Um `sourceMappingURL` pendurado reprova o `collectstatic` inteiro.

        Aconteceu em `d845ef8`: o dist do Leaflet foi vendorizado sem o
        `leaflet.js.map`, e a `VersionedStaticFilesStorage` levanta
        `MissingFileError` ao pos-processar. Como o `collectstatic` roda ANTES da
        suite no CI, o efeito e pior do que parece — nenhum teste chega a rodar,
        e a falha se disfarca de "CI vermelho" sem dizer por que.

        Este teste custa milissegundos e da a mensagem certa; o `collectstatic`
        do CI continua sendo a prova final.
        """
        padrao = re.compile(r"sourceMappingURL=([^\s*'\"]+)")
        pendurados = []
        static_root = Path(settings.BASE_DIR) / "static"
        for path in static_root.rglob("*"):
            if not path.is_file() or path.suffix not in {".js", ".css"}:
                continue
            try:
                source = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            for referencia in padrao.findall(source):
                if referencia.startswith(("data:", "http://", "https://")):
                    continue
                if not (path.parent / referencia).is_file():
                    pendurados.append(
                        f"{path.relative_to(settings.BASE_DIR).as_posix()} -> {referencia}"
                    )
        self.assertEqual(pendurados, [])
