"""`NOVO-08` — o custo de banco da lista de Prestações não pode crescer com a página.

`eventos`, `termos`, `ordens_servico` e `planos_trabalho` já tinham cada um o seu
`test_orcamento_de_queries.py`. `prestacoes_contas` não tinha **nenhum**
`assertNumQueries` no app inteiro — e foi a lista que a régua do `PF-07` pegou com
**138 consultas para 20 linhas**, o pior número das nove rotas medidas.

Duas asserções, e a segunda é a que importa:

1. **O número exato**, no molde dos apps irmãos. Igualdade e não `assertLessEqual`:
   teto com folga passa igual se alguém enfiar um N+1 dentro dela.
2. **A invariância**: dobrar as linhas da página não muda a contagem. É a
   propriedade que define "não é N+1", e ela pega o defeito mesmo que a constante
   acima seja atualizada sem pensar — que é o jeito mais comum de uma catraca
   dessas ser desarmada.
"""

from __future__ import annotations

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from cadastros.models import Cidade
from cadastros.models import Estado
from prestacoes_contas.models import PrestacaoServidor
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino


class OrcamentoDeQueriesPrestacaoTests(PrestacaoFixturesMixin, TestCase):
    # Medido em 06/08/2026, depois do `NOVO-08`. Antes eram 138 para 20 linhas na
    # régua do `PF-07`; as causas eram `_destino_display_oficio` sem prefetch dos
    # destinos (100 consultas) e `get_configuracao_sistema()` chamado por card
    # (19). Bate com o número da régua porque as duas medem o regime estável —
    # ver o aquecimento em `setUp`.
    QUERIES_LISTA = 20

    def setUp(self):
        self.setUpPrestacaoFixtures()
        # `Estado` e `Cidade` são catálogo global, sem campo `area`.
        self.estado = Estado.objects.create(nome="Paraná", sigla="PR")
        self.cidades = [
            Cidade.objects.create(nome=f"Cidade {i}", estado=self.estado, uf="PR")
            for i in range(3)
        ]
        # Uma requisição descartada antes de medir. `get_configuracao_sistema()`
        # é um `get_or_create` (`cadastros/models.py:571`): na primeira chamada da
        # área ele **escreve**, e o INSERT mais os savepoints custam 3 consultas
        # que não se repetem. Sem o aquecimento, o teste de invariância via o
        # custo CAIR de 23 para 20 ao dobrar as linhas — medindo efeito de
        # primeira chamada, não N+1.
        self.get_listagem()

    def _criar_com_roteiro(self, numero):
        """Prestação cujo ofício tem roteiro com dois destinos.

        Os destinos não são enfeite: `_destino_display_oficio`
        (`oficios/presenters.py:51-54`) percorre `roteiro.destinos.all()` e toca
        `d.cidade` e `d.estado` de cada um. Sem destino, o N+1 que este teste
        vigia simplesmente não acontece e o teste passaria vazio.
        """
        fixture = self.criar_prestacao(numero=numero)
        roteiro = Roteiro.objects.create(
            area=self.area, origem_estado=self.estado, origem_cidade=self.cidades[0]
        )
        RoteiroDestino.objects.bulk_create(
            [
                RoteiroDestino(
                    roteiro=roteiro,
                    estado=self.estado,
                    cidade=self.cidades[(numero + d) % len(self.cidades)],
                    ordem=d,
                )
                for d in range(2)
            ]
        )
        fixture.oficio.roteiro = roteiro
        fixture.oficio.save(update_fields=["roteiro"])
        return fixture

    def _semear(self, quantas):
        """Cria `quantas` prestações a mais, com numeração que não colide."""
        ja_existem = PrestacaoServidor.objects.count()
        for offset in range(quantas):
            self._criar_com_roteiro(ja_existem + offset + 1)

    def _contar(self):
        with CaptureQueriesContext(connection) as queries:
            resposta = self.get_listagem()
        self.assertEqual(resposta.status_code, 200)
        linhas = len(resposta.context["page_obj"].object_list)
        self.assertGreater(linhas, 0, msg="página vazia — a contagem não diria nada")
        return len(queries), linhas, queries

    def test_a_lista_custa_o_mesmo_numero_de_queries(self):
        self._semear(3)

        total, _, queries = self._contar()

        self.assertEqual(
            total,
            self.QUERIES_LISTA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_dobrar_as_linhas_nao_muda_o_numero_de_queries(self):
        """A asserção que define "não é N+1", e que sobrevive a alguém atualizar
        a constante acima sem pensar."""
        self._semear(3)
        com_poucas, linhas_poucas, _ = self._contar()

        self._semear(3)
        com_dobro, linhas_dobro, queries = self._contar()

        self.assertEqual(linhas_dobro, linhas_poucas * 2, msg="o fixture não dobrou as linhas")
        self.assertEqual(
            com_dobro,
            com_poucas,
            msg=f"o custo cresceu de {com_poucas} para {com_dobro} ao dobrar as linhas "
            "— voltou um N+1:\n" + "\n".join(q["sql"] for q in queries.captured_queries),
        )
