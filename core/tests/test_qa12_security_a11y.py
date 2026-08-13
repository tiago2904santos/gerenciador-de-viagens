"""QA-12 — contratos dos gates de segurança e acessibilidade."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


RAIZ = Path(settings.BASE_DIR)


class DependabotECodeQLTests(SimpleTestCase):
    def test_dependabot_vigia_python_e_github_actions_semanalmente(self):
        texto = (RAIZ / ".github/dependabot.yml").read_text(encoding="utf-8")

        self.assertIn("package-ecosystem: pip", texto)
        self.assertIn("package-ecosystem: github-actions", texto)
        self.assertEqual(texto.count("interval: weekly"), 2)

    def test_codeql_analisa_python_e_javascript_em_pr_push_e_agendamento(self):
        texto = (RAIZ / ".github/workflows/codeql.yml").read_text(encoding="utf-8")

        self.assertIn("pull_request:", texto)
        self.assertIn("push:", texto)
        self.assertIn("schedule:", texto)
        self.assertIn("python", texto)
        self.assertIn("javascript-typescript", texto)
        self.assertIn("github/codeql-action/init@v4", texto)
        self.assertIn("github/codeql-action/analyze@v4", texto)


class GateAcessibilidadeTests(SimpleTestCase):
    def test_axe_core_esta_fixado_no_lockfile(self):
        pacote = json.loads((RAIZ / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((RAIZ / "package-lock.json").read_text(encoding="utf-8"))

        self.assertEqual(pacote["devDependencies"]["axe-core"], "4.12.1")
        self.assertEqual(lock["packages"]["node_modules/axe-core"]["version"], "4.12.1")

    def test_gate_cobre_corpus_canonico_nos_dois_temas(self):
        from scripts import audit_accessibility
        from scripts.rotas_do_sistema import ROTAS

        self.assertEqual(len(ROTAS), 43)
        self.assertEqual(audit_accessibility.THEMES, ("light", "dark"))
        self.assertIn("color-contrast", audit_accessibility.AXE_RULES)

        baseline = audit_accessibility.read_baseline(
            RAIZ / "scripts/accessibility-baseline.json"
        )
        self.assertTrue(baseline)
        self.assertEqual({item[1] for item in baseline}, {"light", "dark"})
        self.assertLessEqual({item[0] for item in baseline}, {route.slug for route in ROTAS})

    def test_ci_executa_axe_no_servidor_real_depois_de_instalar_chromium(self):
        texto = (RAIZ / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        instalacao = texto.index("python -m playwright install --with-deps chromium")
        gate = texto.index("python scripts/audit_accessibility.py")

        self.assertLess(instalacao, gate)
        self.assertIn("--password-env FRONT_METRICS_PASSWORD", texto[gate:])

    def test_resumo_preserva_rota_tema_regra_e_alvo(self):
        from scripts.audit_accessibility import serialize_baseline
        from scripts.audit_accessibility import summarize_violations

        resumo = summarize_violations(
            "login",
            "dark",
            [
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "nodes": [
                        {"target": ["#username"], "html": '<input id="username">'},
                        {"target": ["#password"], "html": '<input id="password">'},
                    ],
                }
            ],
        )

        self.assertEqual(
            resumo,
            [
                {
                    "route": "login",
                    "theme": "dark",
                    "rule": "color-contrast",
                    "impact": "serious",
                    "nodes": 2,
                    "targets": ["#username", "#password"],
                    "details": [
                        {"target": "#username", "html": '<input id="username">', "failure": ""},
                        {"target": "#password", "html": '<input id="password">', "failure": ""},
                    ],
                }
            ],
        )
        self.assertEqual(
            serialize_baseline(resumo)["entries"],
            [
                {
                    "route": "login",
                    "theme": "dark",
                    "rule": "color-contrast",
                    "target": "#password",
                },
                {
                    "route": "login",
                    "theme": "dark",
                    "rule": "color-contrast",
                    "target": "#username",
                },
            ],
        )
