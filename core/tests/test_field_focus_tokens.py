"""NOVO-51: foco de campo usa tokens semânticos com tipo estável."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


CSS = Path(settings.BASE_DIR) / "static" / "css"
TOKENS = CSS / "base" / "tokens.css"
DARK_TOKENS = CSS / "base" / "03-theme-dark.css"


class FieldFocusTokenTests(SimpleTestCase):
    def test_os_dois_ultimos_tokens_cv_de_campo_nao_existem(self):
        infratores = []
        for arquivo in CSS.rglob("*.css"):
            if arquivo.name in {
                "shell.bundle.css",
                "shell.form-components.bundle.css",
            }:
                continue
            texto = arquivo.read_text(encoding="utf-8")
            for token in ("--cv-field-border-focus", "--cv-field-focus-ring"):
                if token in texto:
                    infratores.append(f"{arquivo.relative_to(CSS).as_posix()}: {token}")
        self.assertEqual(infratores, [], "NOVO-51 ainda tem token de origem cv")

    def test_anel_semantico_tem_cor_visivel_nos_dois_temas(self):
        claro = TOKENS.read_text(encoding="utf-8")
        escuro = DARK_TOKENS.read_text(encoding="utf-8")
        self.assertIn("--input-border-focus: #0b3a66;", claro)
        self.assertIn("--input-focus-ring: rgba(21, 91, 154, 0.18);", claro)
        self.assertIn("--input-border-focus: #286fa4;", escuro)
        self.assertIn("--input-focus-ring: rgba(116, 170, 224, 0.24);", escuro)
        self.assertNotIn("--input-focus-ring: none", escuro)
        self.assertIn(
            "--field-shadow-focus: 0 0 0 var(--space-1) var(--input-focus-ring), var(--shadow-xs);",
            escuro,
        )
        self.assertNotIn("--field-shadow-focus: none", escuro)

    def test_consumidores_de_sombra_compoem_a_cor_do_anel(self):
        select = (CSS / "v2" / "select.css").read_text(encoding="utf-8")
        file_picker = (CSS / "v2" / "file-picker.css").read_text(encoding="utf-8")
        self.assertIn(
            "0 0 0 var(--space-1) var(--input-focus-ring), var(--shadow-xs)",
            select,
        )
        self.assertIn("0 0 0 var(--space-1) var(--input-focus-ring)", file_picker)

    def test_wizard_de_roteiro_nao_desliga_mais_o_anel_de_campo(self):
        """`pages/roteiros.css` foi APAGADA em 2026-08-20 — a tela migrou para o
        v2 em 17/08 e nenhuma página a carregava desde então. As quatro supressões
        continuam proibidas, agora onde o editor mora: `v2/route-editor.css`."""
        roteiro = (CSS / "v2" / "route-editor.css").read_text(encoding="utf-8")
        for supressao in (
            "--input-focus-ring: transparent",
            "--field-shadow-focus: none",
            "--select-focus-shadow: none",
            "--route-focus-ring: none",
        ):
            self.assertNotIn(supressao, roteiro)
