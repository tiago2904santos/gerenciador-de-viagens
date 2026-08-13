from pathlib import Path
import subprocess

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


class RepositorioSemConflitosTests(SimpleTestCase):
    def test_arquivos_texto_rastreados_nao_contem_marcadores_de_conflito(self):
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        failures = []

        for relative_path in result.stdout.decode("utf-8").split("\0"):
            if not relative_path:
                continue
            path = ROOT / relative_path
            if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if line.startswith(CONFLICT_MARKERS):
                    failures.append(f"{relative_path}:{line_number}: {line}")

        self.assertEqual(failures, [])
