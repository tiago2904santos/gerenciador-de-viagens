from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from scripts import converter_componentes_cotton as converter


ROOT = Path(settings.BASE_DIR)
COTTON = ROOT / "templates" / "cotton"
DECLARATION = re.compile(r"^{%\s+cotton:vars(?P<vars>(?:\s+[A-Za-z_]\w*)*)\s+%}$")
EXTENDS = re.compile(r'^{%\s+extends\s+"(?P<template>[\w/]+\.html)"\s+%}$')


class CottonComponentContractTests(SimpleTestCase):
    def _converted(self):
        return sorted(COTTON.rglob("*.html"))

    def _declaration(self, target: Path):
        lines = target.read_text(encoding="utf-8").splitlines()
        index = 1 if lines and EXTENDS.fullmatch(lines[0]) else 0
        return DECLARATION.fullmatch(lines[index]) if len(lines) > index else None

    def test_todo_cotton_declara_as_variaveis_livres(self):
        memo: dict[str, set[str]] = {}
        failures = []
        for target in self._converted():
            match = self._declaration(target)
            if not match:
                failures.append(f"{target.relative_to(ROOT)}: declaração ausente")
                continue
            declared = match.group("vars").split()
            expected = converter.contrato(target, memo)
            if declared != expected:
                failures.append(
                    f"{target.relative_to(ROOT)}: declarado={declared}, esperado={expected}"
                )

        self.assertTrue(self._converted(), "nenhum componente Cotton convertido")
        self.assertEqual(failures, [])

    def test_namespace_legado_e_pastas_fantasma_nao_existem(self):
        self.assertEqual(list((ROOT / "templates" / "components").rglob("*.*")), [])
        self.assertEqual(list(COTTON.rglob(".gitkeep")), [])

    def test_isolamento_de_contexto_esta_ativo(self):
        self.assertIs(settings.COTTON_ENABLE_CONTEXT_ISOLATION, True)

    def test_auditor_ignora_a_arvore_cotton_como_componente_global(self):
        from scripts import audit_ui_patterns

        self.assertTrue(audit_ui_patterns.ignored(COTTON / "ui" / "buttons" / "button.html"))

    def test_auditor_reprova_include_de_componente(self):
        from scripts import audit_frontend_standards

        rules = {name: pattern for name, pattern, _message in audit_frontend_standards.TEMPLATE_RULES_ERRO}
        pattern = rules["component_include"]
        self.assertRegex('{% include "components/ui/button.html" %}', pattern)
        self.assertRegex('{% include "cotton/ui/button.html" %}', pattern)

    def test_repositorio_nao_inclui_componente_com_tag_django(self):
        from scripts import audit_frontend_standards

        pattern = dict(
            (name, regex)
            for name, regex, _message in audit_frontend_standards.TEMPLATE_RULES_ERRO
        )["component_include"]
        failures = []
        for path in ROOT.rglob("*.html"):
            if ".venv" in path.parts:
                continue
            if pattern.search(path.read_text(encoding="utf-8-sig")):
                failures.append(str(path.relative_to(ROOT)))
        self.assertEqual(failures, [])


class AtributoDinamicoSemFiltroTests(SimpleTestCase):
    """`:attr="..."` do Cotton é BUSCA de variável, não expressão.

    O filtro escrito ali dentro nunca roda: a busca falha e o atributo chega
    VAZIO ao componente — sem erro, sem aviso, e a tela só mostra o buraco.
    Foi assim que o botão de gerenciar modelos virou um "?" (ícone vazio cai no
    símbolo `unknown`), que o chip de status do card de evento perdeu o tom e
    que a cidade do destino deixou de nascer travada (2026-08-18).

    O conserto é sempre o mesmo: resolver o filtro antes, num `{% with %}`, e
    passar a variável já pronta.
    """

    #: `:nome="algo|filtro"` — o `{{` de fora é interpolação, e essa funciona.
    FILTRO_EM_ATRIBUTO = re.compile(r'(?<![\w-]):([a-z_]\w*)="([^"{}]*\|[^"]*)"')

    def test_nenhum_template_passa_filtro_dentro_de_atributo_dinamico(self):
        falhas = []
        for caminho in sorted((ROOT / "templates").rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            for achado in self.FILTRO_EM_ATRIBUTO.finditer(self._sem_comentarios(texto)):
                linha = texto[: achado.start()].count("\n") + 1
                falhas.append(
                    f"{caminho.relative_to(ROOT)}:{linha}: "
                    f':{achado.group(1)}="{achado.group(2)}"'
                )

        self.assertEqual(falhas, [])

    @staticmethod
    def _sem_comentarios(texto: str) -> str:
        """Apaga o corpo dos comentários MANTENDO as quebras de linha.

        O comentário de vários componentes documenta este defeito com o exemplo
        errado escrito por extenso — o teste bateria neles. Trocar o corpo por
        espaços, e não removê-lo, é o que preserva o número da linha no relato.
        """

        def branco(achado: re.Match) -> str:
            return "\n" * achado.group(0).count("\n")

        return re.sub(r"{% comment %}.*?{% endcomment %}", branco, texto, flags=re.S)
