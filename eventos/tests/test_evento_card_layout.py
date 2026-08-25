"""Contratos de geometria do card de Evento na lista."""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class EventoCardLayoutTests(SimpleTestCase):
    """NOVO-20260824-234511-dd2eedf33819: linhas mantêm altura natural."""

    def test_stretch_do_bloco_fica_restrito_a_listas_de_fatos(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "record.css"
        ).read_text(encoding="utf-8")
        css_sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        regras = re.findall(r"([^{}]+)\{([^{}]*)\}", css_sem_comentarios)

        seletores_com_stretch = [
            seletor
            for seletor, declaracoes in regras
            if "align-content: stretch;" in declaracoes
        ]

        self.assertTrue(seletores_com_stretch)
        self.assertTrue(
            all(
                "oficio-card__allowance-facts" in seletor
                or ":has(> .fact-list)" in seletor
                for seletor in seletores_com_stretch
            ),
            "align-content: stretch não pode alcançar person-list do card de Evento",
        )

    def test_linha_do_picker_relacionado_usa_padding_compacto(self):
        """NOVO-20260825-000241-dcb332aafe26: item respeita seus 62 px."""
        css = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "picker.css"
        ).read_text(encoding="utf-8")
        css_sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        regras = re.findall(r"([^{}]+)\{([^{}]*)\}", css_sem_comentarios)

        declaracoes = next(
            corpo
            for seletor, corpo in regras
            if seletor.strip()
            == ":is(html[data-theme]) .picker--related .search-picker__selected-card"
        )

        self.assertIn("padding: var(--gap-tight) var(--gap);", declaracoes)
        self.assertNotIn("padding: 32px", declaracoes)
