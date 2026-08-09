from __future__ import annotations

from django.test import SimpleTestCase

from scripts import medir_css_por_rota as css_metric
from scripts import medir_divergencia_tema as theme_metric


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


class DivergenciaTemaMetricTests(SimpleTestCase):
    def test_propriedades_de_cor_e_tokens_nao_entram(self):
        for prop in ("color", "background-color", "border-top-color", "fill", "stroke", "--color-card"):
            with self.subTest(prop=prop):
                self.assertTrue(theme_metric.is_color_property(prop))
        self.assertFalse(theme_metric.is_color_property("border-top-width"))
        self.assertFalse(theme_metric.is_color_property("font-family"))

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
        self.assertEqual(result["distinct_pairs"], 2)

    def test_ordem_de_captura_e_estavel_quando_os_diffs_sao_os_mesmos(self):
        first = {("0", "font-family", "Arial", "Inter")}
        reverse = {("0", "font-family", "Arial", "Inter")}
        self.assertEqual(theme_metric.order_exclusives(first, reverse), (set(), set()))
