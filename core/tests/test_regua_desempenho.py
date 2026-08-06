"""PF-07 — a lógica de decisão da régua de desempenho.

`scripts/medir_desempenho.py` leva mais de dois minutos e exige PostgreSQL com
volume: não cabe na suíte. O que cabe, e é o que erra calado, são as três funções
que decidem **o que reprova**:

- `_fatiar_por_area`, que distribui o volume entre as áreas — se ela puser tudo na
  área ativa, a régua mede uma tabela pequena achando que mede uma grande;
- `_teto_de_kb`, a margem do teto de bytes;
- `conferir_tetos`, que compara medida com teto.

Um erro em qualquer uma delas deixa o gate verde durante uma regressão, que é o
único jeito de uma catraca ser pior que catraca nenhuma.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


def _carregar_modulo():
    """Importa o script pelo caminho — `scripts/` não é pacote.

    O módulo chama `django.setup()` no topo; aqui já está configurado, e chamar de
    novo é idempotente.
    """
    caminho = Path(settings.BASE_DIR) / "scripts" / "medir_desempenho.py"
    spec = importlib.util.spec_from_file_location("medir_desempenho", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["medir_desempenho"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


regua = _carregar_modulo()


class FatiarPorAreaTests(SimpleTestCase):
    AREAS = ("ativa", "outra-1", "outra-2")

    def test_devolve_uma_area_por_registro(self):
        self.assertEqual(len(regua._fatiar_por_area(200, self.AREAS)), 200)

    def test_um_terco_fica_na_area_ativa(self):
        fatias = regua._fatiar_por_area(20_000, self.AREAS)

        self.assertEqual(fatias.count("ativa"), 20_000 // 3)

    def test_o_resto_nao_vai_para_a_area_ativa(self):
        """O ponto da medição: as outras áreas precisam pesar na mesma tabela.

        A linha de base mostrou que o custo cresce com a tabela inteira, não com a
        fatia do usuário. Semear tudo na área ativa esconderia exatamente isso.
        """
        fatias = regua._fatiar_por_area(20_000, self.AREAS)

        self.assertEqual(set(fatias[20_000 // 3 :]), {"outra-1", "outra-2"})

    def test_volume_minusculo_ainda_povoa_a_area_ativa(self):
        """Com volume 1 o `//3` daria zero e a página mediria uma lista vazia."""
        self.assertEqual(regua._fatiar_por_area(1, self.AREAS), ["ativa"])

    def test_com_area_unica_nao_estoura(self):
        self.assertEqual(regua._fatiar_por_area(3, ("so-uma",)), ["so-uma"] * 3)


class TetoDeKbTests(SimpleTestCase):
    def test_pagina_pequena_ganha_o_piso_de_2kb(self):
        """5% de 23,8 KB seria 1,2 KB — menos que uma frase a mais no template."""
        self.assertEqual(regua._teto_de_kb(23.8), 25.8)

    def test_pagina_grande_ganha_os_5_por_cento(self):
        self.assertEqual(regua._teto_de_kb(451.5), 474.1)

    def test_a_margem_nao_esconde_um_icone_por_cartao(self):
        """O `PF-01` é ~11 KB de SVG por cartão; 5% de uma página de 88 KB é 4,4 KB."""
        medido = 87.9
        self.assertLess(regua._teto_de_kb(medido), medido + 11)


class ConferirTetosTests(SimpleTestCase):
    TETOS = {"oficios:index": {"200": {"consultas": 17, "kb_html": 474.1}}}

    def _medida(self, **ajustes):
        base = {"consultas": 17, "kb_html": 451.5, "linhas": 20, "ms": 1.0}
        return {200: {"oficios:index": {**base, **ajustes}}}

    def test_dentro_do_teto_nao_reprova(self):
        self.assertEqual(regua.conferir_tetos(self._medida(), self.TETOS), [])

    def test_no_teto_exato_nao_reprova(self):
        """A comparação é `>`, não `>=` — reprovar no valor declarado seria armadilha."""
        self.assertEqual(regua.conferir_tetos(self._medida(consultas=17), self.TETOS), [])

    def test_uma_consulta_a_mais_reprova(self):
        violacoes = regua.conferir_tetos(self._medida(consultas=18), self.TETOS)

        self.assertEqual(len(violacoes), 1)
        self.assertIn("consultas", violacoes[0])

    def test_html_acima_do_teto_reprova(self):
        violacoes = regua.conferir_tetos(self._medida(kb_html=500.0), self.TETOS)

        self.assertEqual(len(violacoes), 1)
        self.assertIn("kb_html", violacoes[0])

    def test_rota_sem_teto_declarado_reprova(self):
        """Rota nova entra com teto medido, não passa despercebida por omissão."""
        violacoes = regua.conferir_tetos(self._medida(), {})

        self.assertEqual(len(violacoes), 1)
        self.assertIn("sem teto declarado", violacoes[0])

    def test_volume_sem_teto_declarado_reprova(self):
        """Ter teto para 200 não vale para 20.000 — o segundo volume é o que escala."""
        medidas = {20000: {"oficios:index": {"consultas": 17, "kb_html": 451.5}}}

        violacoes = regua.conferir_tetos(medidas, self.TETOS)

        self.assertEqual(len(violacoes), 1)
        self.assertIn("sem teto declarado", violacoes[0])


class ArquivoDeTetosTests(SimpleTestCase):
    def test_todas_as_rotas_medidas_tem_teto_nos_dois_volumes(self):
        """Se alguém adicionar rota em `ROTAS` sem regravar os tetos, o CI só
        descobre depois de dois minutos de medição. Aqui descobre em milissegundos."""
        tetos = regua.carregar_tetos()
        faltando = [
            f"{nome} @ {volume}"
            for nome, _ in regua.ROTAS
            for volume in ("200", "20000")
            if volume not in tetos.get(nome, {})
        ]

        self.assertEqual(faltando, [], msg=f"sem teto declarado: {faltando}")
