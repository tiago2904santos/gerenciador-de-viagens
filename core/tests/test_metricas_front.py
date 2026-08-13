from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from scripts import medir_css_por_rota as css_metric
from scripts import medir_divergencia_tema as theme_metric
from scripts import sonda_mesmo_tema as same_theme_metric
from scripts.rotas_do_sistema import ROTAS


class CssPorRotaMetricTests(SimpleTestCase):
    def test_intervalos_usados_sao_unidos_sem_contar_sobreposicao(self):
        self.assertEqual(
            css_metric.merge_ranges([(0, 10), (5, 15), (20, 25), (25, 30)]),
            [(0, 15), (20, 30)],
        )

    def test_medicao_conta_bytes_entregues_e_casados(self):
        text = ".a { color: red; }\n.b { color: blue; }"
        first_rule_end = text.index("\n")
        result = css_metric.summarize_rule_usage(
            {"sheet-1": text},
            [
                {
                    "styleSheetId": "sheet-1",
                    "startOffset": 0,
                    "endOffset": first_rule_end,
                    "used": True,
                },
                {
                    "styleSheetId": "sheet-1",
                    "startOffset": first_rule_end + 1,
                    "endOffset": len(text),
                    "used": False,
                },
            ],
        )
        self.assertEqual(result["bytes_delivered"], len(text.encode("utf-8")))
        self.assertEqual(result["bytes_matched"], len(text[:first_rule_end].encode("utf-8")))
        self.assertAlmostEqual(
            result["usage_percent"],
            100 * result["bytes_matched"] / result["bytes_delivered"],
            places=4,
        )

    def test_diagnostico_atribui_bytes_e_fragmentos_por_folha(self):
        first = ".a { color: red; }"
        second = ".b { color: blue; }"
        result = css_metric.summarize_stylesheet_usage(
            {"sheet-a": first, "sheet-b": second},
            [
                {
                    "styleSheetId": "sheet-a",
                    "startOffset": 0,
                    "endOffset": len(first),
                    "used": True,
                },
                {
                    "styleSheetId": "sheet-b",
                    "startOffset": 0,
                    "endOffset": len(second),
                    "used": False,
                },
            ],
            {"sheet-a": "http://test/static/a.css", "sheet-b": "http://test/static/b.css"},
            include_fragments=True,
        )

        self.assertEqual(result[0]["bytes_matched"], len(first.encode("utf-8")))
        self.assertEqual(result[0]["matched_fragments"], [first])
        self.assertEqual(result[1]["bytes_matched"], 0)
        self.assertEqual(result[1]["matched_fragments"], [])

    def test_folha_externa_sem_regra_casada_entra_no_denominador(self):
        self.assertEqual(
            css_metric.stylesheet_ids(
                [
                    {
                        "styleSheetId": "sheet-used",
                        "startOffset": 0,
                        "endOffset": 10,
                        "used": True,
                    }
                ],
                {
                    "sheet-used": "http://test/static/used.css",
                    "sheet-zero": "http://test/static/zero.css",
                    "browser-sheet": "",
                },
            ),
            {"sheet-used", "sheet-zero"},
        )

    def test_fragmento_respeita_offsets_utf16_do_cdp(self):
        text = "/* 🚀 */ .a { color: red; }"
        utf16_length = len(text.encode("utf-16-le")) // 2

        self.assertEqual(
            css_metric._text_for_utf16_offsets(text, 0, utf16_length),
            text,
        )

    def test_piso_de_uso_so_pode_subir(self):
        old = {"oficios-lista": {"usage_percent_min": 11.5}}
        measured_better = {"oficios-lista": {"usage_percent": 14.0}}
        measured_worse = {"oficios-lista": {"usage_percent": 9.0}}

        self.assertEqual(
            css_metric.updated_floors(old, measured_better)["oficios-lista"]["usage_percent_min"],
            14.0,
        )
        self.assertEqual(
            css_metric.updated_floors(old, measured_worse)["oficios-lista"]["usage_percent_min"],
            11.5,
        )

    def test_redirecionamento_interno_autenticado_e_aceito(self):
        self.assertTrue(
            css_metric.is_valid_final_url(
                "http://127.0.0.1:8000/oficios/1/dados-viajantes/",
                "/oficios/1/",
                "http://127.0.0.1:8000/",
                requires_auth=True,
            )
        )

    def test_redirecionamento_para_login_ou_outro_host_e_rejeitado(self):
        for final_url in (
            "http://127.0.0.1:8000/login/",
            "https://example.invalid/oficios/1/",
        ):
            with self.subTest(final_url=final_url):
                self.assertFalse(
                    css_metric.is_valid_final_url(
                        final_url,
                        "/oficios/1/",
                        "http://127.0.0.1:8000/",
                        requires_auth=True,
                    )
                )

    def test_pisos_versionados_cobrem_as_43_rotas(self):
        thresholds = json.loads(css_metric.DEFAULT_THRESHOLDS.read_text(encoding="utf-8"))
        css_gate = thresholds["css_by_route"]

        self.assertEqual(css_gate["direction"], "up")
        self.assertEqual(set(css_gate["routes"]), {route.slug for route in ROTAS})
        self.assertTrue(
            all(item["usage_percent_min"] > 0 for item in css_gate["routes"].values())
        )

    def test_todas_as_rotas_cumprem_o_aceite_pf02_de_35_por_cento(self):
        thresholds = json.loads(css_metric.DEFAULT_THRESHOLDS.read_text(encoding="utf-8"))
        abaixo = {
            slug: item["usage_percent_min"]
            for slug, item in thresholds["css_by_route"]["routes"].items()
            if item["usage_percent_min"] < 35.0
        }

        self.assertEqual(abaixo, {}, msg=f"PF-02 ainda aberto: {abaixo}")

    def test_ci_migra_o_banco_descartavel_antes_de_semear(self):
        workflow = (css_metric.ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
        frontend_step = workflow.split("Enforce frontend route baselines (NOVO-70)", 1)[1]

        self.assertLess(
            frontend_step.index("manage.py migrate --noinput"),
            frontend_step.index("manage.py resetar_banco_demo"),
        )


class DivergenciaTemaMetricTests(SimpleTestCase):
    def test_propriedades_de_cor_e_tokens_nao_entram(self):
        for prop in ("color", "background-color", "border-top-color", "fill", "stroke", "--color-card"):
            with self.subTest(prop=prop):
                self.assertTrue(theme_metric.is_color_property(prop))
        self.assertFalse(theme_metric.is_color_property("border-top-width"))
        self.assertFalse(theme_metric.is_color_property("font-family"))

    def test_propriedades_computadas_sem_pintura_sao_classificadas_a_parte(self):
        for prop in (
            "-webkit-font-smoothing",
            "-moz-osx-font-smoothing",
            "text-rendering",
            "transition-duration",
        ):
            with self.subTest(prop=prop):
                self.assertTrue(theme_metric.is_non_paint_property(prop))
        self.assertFalse(theme_metric.is_non_paint_property("border-top-width"))

    def test_compara_o_mesmo_elemento_e_conta_pares_distintos(self):
        light = [
            {"key": "0", "label": "html", "styles": {"font-family": "Arial", "border-radius": "0px"}},
            {"key": "1", "label": "body", "styles": {"font-family": "Arial", "border-radius": "0px"}},
        ]
        dark = [
            {"key": "0", "label": "html", "styles": {"font-family": "Inter", "border-radius": "0px"}},
            {"key": "1", "label": "body", "styles": {"font-family": "Inter", "border-radius": "10px"}},
        ]

        result = theme_metric.compare_snapshots(light, dark)

        self.assertEqual(result["elements_compared"], 2)
        self.assertEqual(result["elements_divergent"], 2)
        self.assertEqual(result["differences"], 3)
        self.assertEqual(result["paint_relevant_differences"], 3)
        self.assertEqual(result["non_paint_differences"], 0)
        self.assertEqual(result["distinct_pairs"], 2)

    def test_divergencia_sem_pintura_nao_infla_a_coluna_visual(self):
        light = [{"key": "0", "styles": {"-webkit-font-smoothing": "auto", "width": "10px"}}]
        dark = [
            {
                "key": "0",
                "styles": {"-webkit-font-smoothing": "antialiased", "width": "12px"},
            }
        ]

        result = theme_metric.compare_snapshots(light, dark)

        self.assertEqual(result["differences"], 2)
        self.assertEqual(result["paint_relevant_differences"], 1)
        self.assertEqual(result["non_paint_differences"], 1)

    def test_ordem_de_captura_e_estavel_quando_os_diffs_sao_os_mesmos(self):
        first = {("0", "font-family", "Arial", "Inter")}
        reverse = {("0", "font-family", "Arial", "Inter")}
        self.assertEqual(theme_metric.order_exclusives(first, reverse), (set(), set()))

    def test_tetos_versionados_cobrem_tres_larguras_e_43_rotas(self):
        thresholds = json.loads(theme_metric.DEFAULT_THRESHOLDS.read_text(encoding="utf-8"))
        theme_gate = thresholds["theme_divergence"]
        expected = {
            f"{route.slug}@{width}"
            for route in ROTAS
            for width in theme_metric.DEFAULT_VIEWPORTS
        }

        self.assertEqual(theme_gate["direction"], "down")
        self.assertEqual(set(theme_gate["routes"]), expected)

    def test_ci_publica_medidas_e_tetos_recalibrados(self):
        workflow = (theme_metric.ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("atualizar_tetos_front:", workflow)
        self.assertIn("metric_args+=(--atualizar-tetos)", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("divergencia-tema.json", workflow)
        self.assertIn("scripts/tetos_front.json", workflow)


class MesmoTemaMetricTests(SimpleTestCase):
    def _item(self, *, text="estavel", width="100px"):
        return {
            "label": "div.card",
            "text_hash": same_theme_metric.text_hash(text),
            "styles": {"width": width, "color": "rgb(0, 0, 0)"},
            "pseudos": {},
        }

    def test_snapshot_identico_tem_zero_diferencas(self):
        snapshot = {"html:nth-of-type(1)>body:nth-of-type(1)": self._item()}

        result = same_theme_metric.compare_snapshots(snapshot, snapshot)

        self.assertEqual(result["style_differences"], 0)
        self.assertEqual(result["structural_differences"], 0)
        self.assertEqual(result["text_changes"], 0)

    def test_diferenca_de_cascata_nomeia_propriedade(self):
        key = "html:nth-of-type(1)>body:nth-of-type(1)>div:nth-of-type(1)"

        result = same_theme_metric.compare_snapshots(
            {key: self._item(width="100px")},
            {key: self._item(width="120px")},
        )

        self.assertEqual(result["style_differences"], 1)
        self.assertEqual(result["text_correlated_style_differences"], 0)
        self.assertEqual(result["top_properties"], [("width", 1)])

    def test_texto_dinamico_nao_esconde_regressao_de_cascata(self):
        key = "html:nth-of-type(1)>body:nth-of-type(1)>span:nth-of-type(1)"

        result = same_theme_metric.compare_snapshots(
            {key: self._item(text="12:59", width="40px")},
            {key: self._item(text="13:00", width="42px")},
        )

        self.assertEqual(result["style_differences"], 1)
        self.assertEqual(result["text_correlated_style_differences"], 1)
        self.assertEqual(result["text_changes"], 1)

    def test_dom_diferente_reprova_com_chaves_estruturais(self):
        before = {"html:nth-of-type(1)": self._item()}
        after = {
            "html:nth-of-type(1)": self._item(),
            "html:nth-of-type(1)>body:nth-of-type(1)": self._item(),
        }

        result = same_theme_metric.compare_snapshots(before, after)

        self.assertEqual(result["structural_differences"], 1)
        self.assertEqual(
            result["missing_before"],
            ["html:nth-of-type(1)>body:nth-of-type(1)"],
        )

    def test_ordem_invertida_expoe_captura_irreprodutivel(self):
        first = {("node", "element", "width", "1px", "2px")}
        reverse = {("node", "element", "height", "1px", "2px")}

        only_first, only_reverse = same_theme_metric.order_exclusives(first, reverse)

        self.assertEqual(only_first, first)
        self.assertEqual(only_reverse, reverse)

    def test_assinatura_de_reprodutibilidade_inclui_estrutura_e_texto(self):
        snapshot = same_theme_metric.compare_snapshots(
            {"html": self._item(text="antes")},
            {"html": self._item(text="depois"), "html>body": self._item()},
        )

        keys = same_theme_metric.reproducibility_keys(snapshot)

        self.assertIn(("missing-before", "html>body"), keys)
        self.assertIn(("text-change", "html"), keys)

    def test_rotas_publicas_ficam_em_contexto_separado_das_protegidas(self):
        public = same_theme_metric.Route("login", "/login/", False)
        protected = same_theme_metric.Route("oficios", "/oficios/", True)

        groups = same_theme_metric.route_groups([protected, public])

        self.assertEqual(groups, ([public], [protected]))

    def test_rotas_json_aceitam_caminho_e_contrato_explicito(self):
        with TemporaryDirectory() as directory:
            routes_path = Path(directory) / "routes.json"
            routes_path.write_text(
                json.dumps(
                    [
                        "/oficios/1/",
                        {"slug": "publica", "path": "/login/", "requires_auth": False},
                    ]
                ),
                encoding="utf-8",
            )
            routes = same_theme_metric.load_routes(routes_path)

        self.assertEqual(routes[0], same_theme_metric.Route("/oficios/1/", "/oficios/1/", True))
        self.assertEqual(routes[1], same_theme_metric.Route("publica", "/login/", False))

    def test_corpus_vazio_e_rejeitado(self):
        with TemporaryDirectory() as directory:
            routes_path = Path(directory) / "routes.json"
            routes_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesMessage(SystemExit, "corpus de rotas nao pode ser vazio"):
                same_theme_metric.load_routes(routes_path)

    def test_gate_nao_perdoa_estilo_correlacionado_a_texto(self):
        report = {
            "route_count": 1,
            "viewports": [500],
            "themes": ["light"],
            "summary": {
                "measurements": 1,
                "structural_differences": 0,
                "style_differences": 1,
                "text_correlated_style_differences": 1,
            },
        }

        failures = same_theme_metric.report_failures(report, max_style_differences=0)

        self.assertEqual(failures, ["1 diferencas de estilo > teto 0"])
