"""`BE-15` — a numeração da Ordem de Serviço: escolha, retry e recorte por área.

Rede escrita **antes** de qualquer mudança. A concorrência de verdade está em
`test_numbering_concurrency.py`, que precisa de PostgreSQL; aqui ficam as garantias que
valem nos dois bancos.

O cenário que importa é o do **retry**. O enunciado original do `BE-15` dizia que a OS era
"sem reuso de lacuna e sem retry", e a parte do retry é falsa: `OrdemServico.save()` tem um
laço de três tentativas que recaptura a violação da `UniqueConstraint` e escolhe outro
número. Este teste trava isso.

**A colisão aqui é real, não sintética.** Até o `BE-15`, o teste equivalente do ofício
levantava um `IntegrityError` **fabricado** com a mensagem esperada: provava o laço, nunca
que a exceção do banco é reconhecida. Aqui a primeira tentativa escolhe um número **de fato
ocupado** e quem levanta é o banco — se o reconhecimento quebrar, este teste reprova.

O reconhecimento tem duas fontes (`core/numeracao.colisao_de_numero`): o metadado
estruturado da exceção, quando o driver oferece, e a ocupação atual do número quando não
há metadado. `test_colisao_ainda_e_reconhecida_se_a_linha_rival_sumir_antes_da_conferencia`
cobre a diferença entre as duas — é a janela que a revisão do PR #339 apontou.
"""

from __future__ import annotations

from unittest import mock
from unittest import skipUnless

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from core.testing import area_de_teste
from ordens_servico.models import OrdemServico


class NumeracaoDaOrdemServicoTests(TestCase):
    def setUp(self):
        self.ano = timezone.localdate().year
        self.area = area_de_teste()

    def criar(self, **campos):
        return OrdemServico.objects.create(
            area=self.area,
            data_evento_inicio=timezone.localdate(),
            data_evento_fim=timezone.localdate(),
            **campos,
        )

    def test_a_primeira_os_do_ano_recebe_o_numero_1(self):
        ordem = self.criar()

        self.assertEqual(ordem.numero, 1)
        self.assertEqual(ordem.ano, self.ano)

    def test_a_numeracao_segue_o_maior_usado_mais_um(self):
        self.criar()
        self.criar()

        self.assertEqual(self.criar().numero, 3)

    def test_numero_ja_definido_e_respeitado(self):
        """Numeração manual continua ganhando de qualquer sugestão automática."""
        ordem = self.criar(numero=42, ano=self.ano)

        self.assertEqual(ordem.numero, 42)

    def test_colisao_real_e_superada_na_tentativa_seguinte(self):
        """O retry, contra uma violação vinda do banco de verdade.

        A primeira tentativa escolhe um número já ocupado; quem levanta o `IntegrityError`
        é o próprio banco, com a mensagem real da constraint. Se o nome que o código
        procura deixar de casar com o que o banco emite, este teste reprova.
        """
        self.criar(numero=77, ano=self.ano)
        original = OrdemServico._assign_numero
        chamadas = []

        def escolher_colidindo(self_os):
            chamadas.append(1)
            if len(chamadas) == 1:
                self_os.numero = 77
                self_os.ano = self.ano
                return
            original(self_os)

        with mock.patch.object(OrdemServico, "_assign_numero", escolher_colidindo):
            nova = self.criar()

        self.assertEqual(len(chamadas), 2, "o laço não repetiu depois da colisão")
        self.assertNotEqual(nova.numero, 77)
        self.assertEqual(
            OrdemServico.objects.filter(area=self.area, ano=self.ano).count(), 2
        )

    @skipUnless(
        connection.vendor == "postgresql",
        "Só o PostgreSQL oferece o metadado estruturado da exceção.",
    )
    def test_colisao_ainda_e_reconhecida_se_a_linha_rival_sumir_antes_da_conferencia(self):
        """A janela que a revisão do PR #339 apontou, fechada.

        A ocupação atual é prova **indireta** da colisão: se a linha que causou a violação
        for apagada entre o `INSERT` que falhou e a consulta de conferência — e as rotas de
        exclusão não tomam o lock de numeração, então com `READ COMMITTED` a consulta
        enxerga a exclusão —, a resposta vira "não está ocupado" e um `IntegrityError` que
        merecia nova tentativa subiria cru.

        Aqui a exclusão é simulada zerando a conferência de ocupação. Com a identificação
        vindo do metadado da exceção (`diag.constraint_name`), o retry acontece do mesmo
        jeito; se ela dependesse só da ocupação, este cenário reprovaria.
        """
        self.criar(numero=88, ano=self.ano)
        original = OrdemServico._assign_numero
        chamadas = []

        def escolher_colidindo(self_os):
            chamadas.append(1)
            if len(chamadas) == 1:
                self_os.numero = 88
                self_os.ano = self.ano
                return
            original(self_os)

        with mock.patch.object(OrdemServico, "_assign_numero", escolher_colidindo):
            # A rival "sumiu": a conferência de ocupação responde que ninguém tem o número.
            with mock.patch.object(OrdemServico, "_numero_ocupado", return_value=False):
                nova = self.criar()

        self.assertEqual(len(chamadas), 2, "o retry não aconteceu sem a prova de ocupação")
        self.assertNotEqual(nova.numero, 88)

    def test_a_numeracao_nao_enxerga_os_de_outra_area(self):
        """`BE-09`: o escopo é a área da OS, não a ativa — cada área conta do 1."""
        outra = area_de_teste(sigla="OUT", nome="Outra área")
        OrdemServico.all_objects.create(
            area=outra,
            numero=9,
            ano=self.ano,
            data_evento_inicio=timezone.localdate(),
            data_evento_fim=timezone.localdate(),
        )

        self.assertEqual(self.criar().numero, 1)
