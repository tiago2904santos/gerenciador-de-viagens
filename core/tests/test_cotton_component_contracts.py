from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from scripts import converter_componentes_cotton as converter


ROOT = Path(settings.BASE_DIR)
COMPONENTS = ROOT / "templates" / "components"
COTTON = ROOT / "templates" / "cotton"
DECLARATION = re.compile(r"^{%\s+cotton:vars(?P<vars>(?:\s+[A-Za-z_]\w*)*)\s+%}$")
WRAPPER = re.compile(r"^<c-(?P<name>[\w.]+)(?P<attrs>(?:\s+:[A-Za-z_]\w*=\"[A-Za-z_]\w*\")*)\s*/>$")
ATTR = re.compile(r':(?P<name>[A-Za-z_]\w*)="(?P<value>[A-Za-z_]\w*)"')


class CottonComponentContractTests(SimpleTestCase):
    def _converted(self):
        return sorted(COTTON.rglob("*.html"))

    def test_todo_cotton_declara_as_variaveis_livres(self):
        memo: dict[str, set[str]] = {}
        failures = []
        for target in self._converted():
            relative = target.relative_to(COTTON)
            source = COMPONENTS / relative
            first_line = target.read_text(encoding="utf-8").splitlines()[0]
            match = DECLARATION.fullmatch(first_line)
            if not match:
                failures.append(f"{target.relative_to(ROOT)}: declaração ausente")
                continue
            declared = match.group("vars").split()
            expected = converter.contrato(source, memo)
            if declared != expected:
                failures.append(
                    f"{target.relative_to(ROOT)}: declarado={declared}, esperado={expected}"
                )

        self.assertTrue(self._converted(), "nenhum componente Cotton convertido")
        self.assertEqual(failures, [])

    def test_casca_e_uma_linha_e_repassa_exatamente_o_contrato(self):
        failures = []
        for target in self._converted():
            relative = target.relative_to(COTTON)
            source = COMPONENTS / relative
            source_lines = source.read_text(encoding="utf-8").splitlines()
            if len(source_lines) != 1:
                failures.append(f"{source.relative_to(ROOT)}: não é casca de uma linha")
                continue
            wrapper = WRAPPER.fullmatch(source_lines[0])
            if not wrapper:
                failures.append(f"{source.relative_to(ROOT)}: casca inválida")
                continue

            expected_name = ".".join(relative.with_suffix("").parts)
            attrs = ATTR.findall(wrapper.group("attrs"))
            declaration = DECLARATION.fullmatch(
                target.read_text(encoding="utf-8").splitlines()[0]
            )
            declared = declaration.group("vars").split() if declaration else []
            if wrapper.group("name") != expected_name:
                failures.append(
                    f"{source.relative_to(ROOT)}: tag={wrapper.group('name')}, esperado={expected_name}"
                )
            if attrs != [(name, name) for name in declared]:
                failures.append(
                    f"{source.relative_to(ROOT)}: attrs={attrs}, declarado={declared}"
                )

        self.assertEqual(failures, [])

    def test_auditor_ignora_a_arvore_cotton_como_ignorava_componentes_ui(self):
        from scripts import audit_ui_patterns

        self.assertTrue(audit_ui_patterns.ignored(COTTON / "ui" / "buttons" / "button.html"))
