"""HT-06/NOVO-74: todo componente Cotton tem consumidor de produção."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
COTTON = ROOT / "templates" / "cotton"
SEARCH_SUFFIXES = {".html", ".py", ".js"}


def _sources() -> list[Path]:
    ignored = {".git", ".venv", "__pycache__"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in SEARCH_SUFFIXES
        and not ignored.intersection(path.parts)
    )


def _is_test(path: Path) -> bool:
    return "tests" in path.parts or path.name.startswith("test_")


class NenhumComponenteOrfaoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sources = {
            path: path.read_text(encoding="utf-8-sig", errors="replace")
            for path in _sources()
        }

    def components(self) -> list[Path]:
        return sorted(COTTON.rglob("*.html"))

    def citations(self, component: Path) -> list[Path]:
        relative = component.relative_to(COTTON)
        template_path = f"cotton/{relative.as_posix()}"
        tag = "<c-" + ".".join(relative.with_suffix("").parts)
        return [
            path
            for path, source in self.sources.items()
            if path != component and (template_path in source or tag in source)
        ]

    def test_todo_componente_tem_quem_o_renderize(self):
        orphaned = [
            str(path.relative_to(COTTON))
            for path in self.components()
            if not self.citations(path)
        ]
        self.assertEqual(orphaned, [], "componente Cotton sem consumidor")

    def test_nenhum_componente_vive_so_de_teste(self):
        test_only = []
        for component in self.components():
            citations = self.citations(component)
            if citations and all(_is_test(path) for path in citations):
                test_only.append(str(component.relative_to(COTTON)))
        self.assertEqual(test_only, [], "componente citado somente por teste")

    def test_namespace_unico_tem_o_inventario_atual(self):
        self.assertEqual(list((ROOT / "templates" / "components").rglob("*.*")), [])
        self.assertEqual(len(self.components()), 83)
