"""Quem decide se um destino é capital (`N-06`).

O grupo tarifário vale dinheiro: capital e interior têm valores diferentes. Até
aqui, quem decidia era `CAPITAIS_POR_UF`, um dicionário de 27 linhas dentro do
módulo de cálculo — duplicando a base geográfica, que já marca `Cidade.capital`.

A auditoria alerta que a divergência entre os dois "silencia como cobrança a
menor". Medi antes de mexer: **as 27 capitais convergem**. Não havia erro de
cobrança; havia risco de passar a haver, sem ninguém notar.

Por isso o teste que importa aqui não é o da classificação — é o **anti-deriva**:
ele falha no dia em que alguém editar um dos dois lados e esquecer o outro.

O fallback também é deliberado. Trocar o dicionário por uma consulta seca faria
todo destino virar `INTERIOR` num banco sem a base importada — exatamente a
cobrança a menor que o defeito descreve, introduzida pela correção dele.
"""

from __future__ import annotations

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.services.diarias import CAPITAIS_POR_UF
from roteiros.services.diarias import _normalize_city_name
from roteiros.services.diarias import classify
from roteiros.services.diarias import limpar_cache_capitais


class BaseGeograficaMandaTests(TestCase):
    def setUp(self):
        limpar_cache_capitais()
        self.addCleanup(limpar_cache_capitais)

    def criar_cidade(self, nome, uf, *, capital=False):
        estado, _ = Estado.objects.get_or_create(sigla=uf, defaults={"nome": uf})
        return Cidade.objects.create(nome=nome, estado=estado, uf=uf, capital=capital)

    def test_capital_marcada_na_base_e_classificada_como_capital(self):
        self.criar_cidade("SAO PAULO", "SP", capital=True)

        self.assertEqual(classify("SAO PAULO", "SP"), "CAPITAL")

    def test_cidade_comum_da_base_e_interior(self):
        self.criar_cidade("SAO PAULO", "SP", capital=True)
        self.criar_cidade("ABATIA", "PR")

        self.assertEqual(classify("ABATIA", "PR"), "INTERIOR")

    def test_a_base_manda_quando_diverge_do_mapa_do_modulo(self):
        """Se um dia divergirem, quem vale é a base — ela é a fonte de verdade.

        O mapa do módulo existe só como rede de segurança. Este teste prova que
        ele não sobrepõe a base; o `test_o_mapa_do_modulo_concorda_com_a_base`
        é que garante que a situação não aconteça em silêncio.
        """
        self.criar_cidade("CAMBE", "PR", capital=True)

        self.assertEqual(classify("CAMBE", "PR"), "CAPITAL")
        self.assertEqual(classify("CURITIBA", "PR"), "INTERIOR")
        self.assertEqual(CAPITAIS_POR_UF["PR"], "CURITIBA")

    def test_base_vazia_cai_no_mapa_do_modulo(self):
        """O fallback que impede a correção de virar o defeito.

        Banco sem a base importada: sem esta rede, toda capital viraria interior
        e o sistema pagaria a menor — que é justamente o que o `N-06` descreve.
        """
        self.assertEqual(Cidade.objects.count(), 0)

        self.assertEqual(classify("CURITIBA", "PR"), "CAPITAL")
        self.assertEqual(classify("SAO PAULO", "SP"), "CAPITAL")
        self.assertEqual(classify("ABATIA", "PR"), "INTERIOR")

    def test_uf_ausente_na_base_usa_o_mapa_sem_contaminar_as_presentes(self):
        """Base parcial: a UF que existe vem da base, a que falta vem do mapa."""
        self.criar_cidade("SAO PAULO", "SP", capital=True)

        self.assertEqual(classify("SAO PAULO", "SP"), "CAPITAL")
        self.assertEqual(classify("CURITIBA", "PR"), "CAPITAL")

    def test_brasilia_continua_com_grupo_proprio(self):
        self.criar_cidade("BRASILIA", "DF", capital=True)

        self.assertEqual(classify("BRASILIA", "DF"), "BRASILIA")

    def test_acento_e_caixa_nao_mudam_a_classificacao(self):
        self.criar_cidade("SAO PAULO", "SP", capital=True)

        for escrita in ("são paulo", "São Paulo", "SÃO PAULO", " sao paulo "):
            with self.subTest(escrita=escrita):
                self.assertEqual(classify(escrita, "sp"), "CAPITAL")


class AntiDerivaTests(TestCase):
    """O teste que dá sentido ao `N-06`.

    Enquanto as duas fontes concordarem, a duplicação é inofensiva. O defeito é
    elas divergirem sem ninguém perceber — e é isso que este teste impede.
    """

    def setUp(self):
        limpar_cache_capitais()
        self.addCleanup(limpar_cache_capitais)

    def test_o_mapa_do_modulo_concorda_com_a_base_geografica_real(self):
        """Compara o mapa com a base de verdade, não com uma cópia dele mesmo.

        A fonte é `scripts/fixture_dados.json`, a carga da base geográfica com
        5.571 municípios e as 27 capitais marcadas. Semear o banco a partir do
        próprio `CAPITAIS_POR_UF` faria as duas concordarem por construção — o
        teste passaria sempre e não guardaria nada.
        """
        import json
        from pathlib import Path

        from django.conf import settings

        fixture = Path(settings.BASE_DIR) / "scripts" / "fixture_dados.json"
        registros = json.loads(fixture.read_text(encoding="utf-8"))
        capitais_da_base = {
            item["fields"]["uf"]: _normalize_city_name(item["fields"]["nome"])
            for item in registros
            if item["model"] == "cadastros.cidade" and item["fields"].get("capital")
        }

        self.assertEqual(len(capitais_da_base), 27, "a base deveria ter 27 capitais")
        self.assertEqual(len(CAPITAIS_POR_UF), 27)

        divergentes = {
            uf: (CAPITAIS_POR_UF.get(uf), capitais_da_base.get(uf))
            for uf in set(CAPITAIS_POR_UF) | set(capitais_da_base)
            if CAPITAIS_POR_UF.get(uf) != capitais_da_base.get(uf)
        }

        self.assertEqual(divergentes, {})

    def test_o_mapa_esta_normalizado(self):
        """Sem acento e em caixa alta — senão a comparação nunca casaria."""
        for uf, nome in CAPITAIS_POR_UF.items():
            with self.subTest(uf=uf):
                self.assertEqual(nome, _normalize_city_name(nome))
