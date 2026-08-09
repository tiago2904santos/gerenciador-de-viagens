from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase

from scripts import audit_ui_patterns as auditor


class AuditUiPatternsTests(SimpleTestCase):
    def test_literal_de_token_nao_e_divida_visual(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            css = root / "static" / "css" / "base" / "tokens.css"
            css.parent.mkdir(parents=True)
            css.write_text(
                ":root {\n"
                "  --color-primary: #12507f;\n"
                "}\n"
                ".card { background: #ffffff; }\n",
                encoding="utf-8",
            )

            findings = auditor.scan_file(css, root=root)

        self.assertNotIn((2, "hex_or_rgba"), {(item.line, item.kind) for item in findings})
        self.assertIn((4, "hex_or_rgba"), {(item.line, item.kind) for item in findings})
        self.assertIn((4, "hardcoded_visual"), {(item.line, item.kind) for item in findings})

    def test_entidade_html_nao_e_confundida_com_cor_hexadecimal(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "templates" / "row.html"
            template.parent.mkdir(parents=True)
            template.write_text('<span aria-hidden="true">&#215;</span>\n', encoding="utf-8")

            findings = auditor.scan_file(template, root=root)

        self.assertNotIn("hex_or_rgba", {item.kind for item in findings})

    def test_bundle_gerado_nao_duplica_a_divida_das_fontes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "static" / "css" / "shell.bundle.css"
            bundle.parent.mkdir(parents=True)
            bundle.write_text(".card { background: #ffffff; }\n", encoding="utf-8")

            findings = auditor.scan_file(bundle, root=root)

        self.assertEqual(findings, [])

    def test_teto_reprova_so_quando_a_contagem_cresce(self):
        self.assertFalse(auditor.exceeds_limit(total=12, maximum=12))
        self.assertFalse(auditor.exceeds_limit(total=11, maximum=12))
        self.assertTrue(auditor.exceeds_limit(total=13, maximum=12))

    def test_sem_teto_o_comando_e_relatorio_e_sai_zero(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            css = root / "static" / "css" / "screen.css"
            css.parent.mkdir(parents=True)
            css.write_text(".card { background: #ffffff; }\n", encoding="utf-8")

            with mock.patch.object(auditor, "ROOT", root), mock.patch.object(
                auditor,
                "TARGETS",
                [root / "static" / "css"],
            ):
                exit_code = auditor.main(["--quiet"])

        self.assertEqual(exit_code, 0)

    def test_com_teto_o_comando_vira_catraca(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            css = root / "static" / "css" / "screen.css"
            css.parent.mkdir(parents=True)
            css.write_text(".card { background: #ffffff; }\n", encoding="utf-8")

            with mock.patch.object(auditor, "ROOT", root), mock.patch.object(
                auditor,
                "TARGETS",
                [root / "static" / "css"],
            ):
                exit_code = auditor.main(["--max", "0", "--quiet"])

        self.assertEqual(exit_code, 1)
