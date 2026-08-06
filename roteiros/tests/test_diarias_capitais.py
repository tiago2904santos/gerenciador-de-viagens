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

from datetime import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.services.diarias import CAPITAIS_POR_UF
from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import _normalize_city_name
from roteiros.services.diarias import calculate_periodized_diarias
from roteiros.services.diarias import classify


class BaseGeograficaMandaTests(TestCase):
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


class BaseEditadaValeNaHoraTests(TestCase):
    """`NOVO-26` — a resposta não pode vir de um mapa memorizado no processo.

    `classify` decide `CAPITAL` vs `INTERIOR`, e isso é o valor da diária. Se o
    mapa de capitais é lido uma vez e guardado no módulo, ele fica velho: no
    admin, marcar uma cidade como capital não muda nada até alguém reiniciar o
    worker; na suíte, o mapa atravessa o rollback da transação e contamina o
    teste seguinte.

    Este teste roda os dois estados dentro de **uma** execução, sem depender de
    ordem de testes: classifica, edita a base, classifica de novo.
    """

    def criar_cidade(self, nome, uf, *, capital=False):
        estado, _ = Estado.objects.get_or_create(sigla=uf, defaults={"nome": uf})
        return Cidade.objects.create(nome=nome, estado=estado, uf=uf, capital=capital)

    def test_a_base_editada_passa_a_valer_na_mesma_execucao(self):
        cambe = self.criar_cidade("CAMBE", "PR", capital=True)
        curitiba = self.criar_cidade("CURITIBA", "PR")

        # A primeira chamada é o que aquecia o mapa memorizado.
        self.assertEqual(classify("CAMBE", "PR"), "CAPITAL")

        cambe.capital = False
        cambe.save(update_fields=["capital"])
        curitiba.capital = True
        curitiba.save(update_fields=["capital"])

        self.assertEqual(
            classify("CURITIBA", "PR"),
            "CAPITAL",
            "a base foi editada e a classificação continuou respondendo pelo "
            "mapa velho — é o caminho do admin, e vale dinheiro",
        )
        self.assertEqual(classify("CAMBE", "PR"), "INTERIOR")


class CustoDeConsultaDaClassificacaoTests(TestCase):
    """A rede que substitui o mapa memorizado (`NOVO-26`).

    O mapa existia para não consultar o banco uma vez por marcador. Tirá-lo sem
    rede devolveria esse N+1; estes dois testes fixam o custo, contando só as
    consultas à tabela de cidades.
    """

    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(sigla="PR", nome="Parana")
        Cidade.objects.create(nome="CURITIBA", estado=estado, uf="PR", capital=True)
        Cidade.objects.create(nome="ABATIA", estado=estado, uf="PR")

    def _marcadores(self, quantidade):
        return [
            PeriodMarker(
                saida=datetime(2026, 8, 10 + dia, 8, 0),
                chegada=datetime(2026, 8, 10 + dia, 18, 0),
                destino_cidade="ABATIA" if dia % 2 else "CURITIBA",
                destino_uf="PR",
            )
            for dia in range(quantidade)
        ]

    def _consultas_de_cidade(self, marcadores):
        with CaptureQueriesContext(connection) as capturadas:
            calculate_periodized_diarias(
                marcadores,
                marcadores[-1].chegada,
                quantidade_servidores=1,
                sede_cidade="CURITIBA",
                sede_uf="PR",
            )
        return sum(
            1
            for consulta in capturadas.captured_queries
            if "cadastros_cidade" in consulta["sql"] and "capital" in consulta["sql"]
        )

    def test_cada_calculo_paga_o_mesmo_custo(self):
        """Dois cálculos idênticos custam o mesmo.

        Com o mapa memorizado, o segundo saía de graça — e é justamente essa
        memória que ficava velha. Custo estável é o outro lado da correção.
        """
        marcadores = self._marcadores(3)

        primeiro = self._consultas_de_cidade(marcadores)
        segundo = self._consultas_de_cidade(marcadores)

        self.assertEqual(
            primeiro,
            segundo,
            "o segundo cálculo respondeu por um mapa guardado do primeiro",
        )
        self.assertEqual(primeiro, 1, "uma resolução por cálculo, não por marcador")

    def test_o_custo_nao_cresce_com_o_numero_de_destinos(self):
        """A rede anti-N+1. Passa antes e depois de propósito.

        Ela não prova o defeito — prova que a correção não trouxe de volta o
        problema que o mapa memorizado existia para evitar.
        """
        self.assertEqual(
            self._consultas_de_cidade(self._marcadores(1)),
            self._consultas_de_cidade(self._marcadores(5)),
        )


class AntiDerivaTests(TestCase):
    """O teste que dá sentido ao `N-06`.

    Enquanto as duas fontes concordarem, a duplicação é inofensiva. O defeito é
    elas divergirem sem ninguém perceber — e é isso que este teste impede.
    """

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
