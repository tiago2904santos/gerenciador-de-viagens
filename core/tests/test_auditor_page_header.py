"""A regra `legacy_page_header` tem de mirar a classe crua (NOVO-39).

O QUE ELA ACUSAVA

`class="[^"]*\\bpage-header\\b` — e `\\b` trata o hifen como fronteira. Entao a
regra casava `page-header-band`, `page-header-stack` e `page-header-rail`: a
familia do **componente canonico**, cujo proprio cabecalho se declara "Cabecalho
canonico de pagina". Eram 92 avisos de template e 60 linhas de CSS, todos falso
positivo, mandando migrar para `app-page-hero` — que **nao existe** no
repositorio: nem em CSS, nem em template, nem em JS.

A classe crua `page-header`, alvo real da regra, aparece **zero** vezes.

Seguir o aviso ao pe da letra teria renomeado 106 usos do componente vigente
para um componente inexistente. Por isso a correcao e na regra, nao no template
— e por isso este arquivo existe: para a regra nao voltar a medir a coisa errada
nem ser afrouxada ate calar.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def _auditor():
    caminho = ROOT / "scripts" / "audit_frontend_standards.py"
    spec = importlib.util.spec_from_file_location("audit_frontend_standards", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class RegraDePageHeaderTests(SimpleTestCase):
    def setUp(self):
        self.mod = _auditor()
        self.regra = next(
            p for nome, p, _m in self.mod.TEMPLATE_RULES_AVISO if nome == "legacy_page_header")
        self.regra_css = self.mod._LEGACY_PAGE_HEADER_PAT

    def test_a_familia_canonica_nao_e_acusada(self):
        for classe in ("page-header-stack", "page-header-band", "page-header-rail",
                       "page-header-band__title", "page-header-status-chip"):
            self.assertIsNone(
                self.regra.search(f'<div class="{classe}">'),
                f"a regra voltou a acusar `{classe}`, que e o componente vigente")
            self.assertIsNone(
                self.regra_css.search(f".{classe} {{"),
                f"a regra de CSS voltou a acusar `.{classe}`")

    def test_a_classe_crua_continua_sendo_acusada(self):
        """Afrouxar ate calar seria o outro erro. A regra tem de morder."""
        self.assertIsNotNone(self.regra.search('<div class="page-header">'))
        self.assertIsNotNone(self.regra.search('<div class="algo page-header outro">'))
        self.assertIsNotNone(self.regra_css.search(".page-header {"))
        self.assertIsNotNone(self.regra_css.search("  .page-header:hover {"))

    def test_o_alvo_da_mensagem_existe(self):
        """A mensagem mandava migrar para `app-page-hero`, que nao existe.

        Aviso que aponta para lugar nenhum nao e acionavel: ou some, ou vira
        ruido que ensina a ignorar o auditor.
        """
        _nome, _pat, mensagem = next(
            r for r in self.mod.TEMPLATE_RULES_AVISO if r[0] == "legacy_page_header")
        import re

        caminhos = re.findall(r"[\w./-]+\.html", mensagem)
        self.assertTrue(caminhos, f"a regra nao aponta caminho nenhum: {mensagem!r}")
        for alvo in caminhos:
            self.assertTrue(
                (ROOT / alvo).exists(),
                f"a regra manda usar `{alvo}`, que nao existe no repositorio")

    def test_o_auditor_nao_tem_excecao_de_template(self):
        """A unica que existia sobrevivia ao defeito da regra, nao a um uso."""
        self.assertEqual(
            self.mod.TEMPLATE_EXCEPTIONS, {},
            "excecao de arquivo de volta no auditor de template")
