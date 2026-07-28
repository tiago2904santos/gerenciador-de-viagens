"""Leitura de valores monetários digitados por pessoas (`NOVO-10`).

Este parser é a fronteira entre o que alguém digita e o que vai para um
documento assinado. O que ele aceita por engano vira dinheiro errado; o que
ele recusa por excesso de zelo vira operador travado. Por isso as duas listas
estão explícitas aqui.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from core.utils.dinheiro import ValorMonetarioInvalido
from core.utils.dinheiro import converter_valor_legado
from core.utils.dinheiro import parse_valor_monetario


class ValoresAceitosTests(SimpleTestCase):
    def test_formatos_que_o_operador_realmente_digita(self):
        casos = {
            "R$80,00": Decimal("80.00"),
            "R$ 80,00": Decimal("80.00"),
            "80,00": Decimal("80.00"),
            # Teclado numérico: muita gente digita ponto no lugar da vírgula.
            "80.00": Decimal("80.00"),
            "1500": Decimal("1500.00"),
            "R$ 1.500,00": Decimal("1500.00"),
            "  87,17  ": Decimal("87.17"),
            "R$0,50": Decimal("0.50"),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                valor, anotacao = parse_valor_monetario(texto)
                self.assertEqual(valor, esperado)
                self.assertEqual(anotacao, "")

    def test_ponto_com_tres_digitos_e_milhar_e_nao_centavo(self):
        """`1.500` é mil e quinhentos, não um e meio. Separador brasileiro."""
        valor, _ = parse_valor_monetario("1.500")

        self.assertEqual(valor, Decimal("1500.00"))

    def test_vazio_nao_e_erro_e_sim_ausencia(self):
        for texto in ("", "   ", None):
            with self.subTest(texto=texto):
                self.assertEqual(parse_valor_monetario(texto), (None, ""))

    def test_anotacao_depois_do_valor_e_preservada(self):
        """O "(saque)" explica por que o valor difere — vai ao documento."""
        valor, anotacao = parse_valor_monetario("R$ 87,00 (saque)")

        self.assertEqual(valor, Decimal("87.00"))
        self.assertEqual(anotacao, "(saque)")

    def test_anotacao_sem_parenteses_tambem_vale(self):
        valor, anotacao = parse_valor_monetario("87 devolveu o troco")

        self.assertEqual(valor, Decimal("87.00"))
        self.assertEqual(anotacao, "devolveu o troco")


class ValoresRecusadosTests(SimpleTestCase):
    def test_texto_sem_numero_nenhum(self):
        for texto in ("abc", "R$ mil reais", "(saque)", "R$"):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorMonetarioInvalido):
                    parse_valor_monetario(texto)

    def test_negativo_nao_e_valor_recebido(self):
        """Ninguém recebe menos que nada. O sinal não é aceito na entrada."""
        with self.assertRaises(ValorMonetarioInvalido):
            parse_valor_monetario("-90")

    def test_numero_malformado_nao_vira_anotacao(self):
        """`350,00,00` é erro de digitação, não valor com observação.

        Sem esta regra o parser leria `350,00` e trataria o `,00` restante
        como anotação — gravando um valor que a pessoa não quis digitar.
        """
        for texto in ("350,00,00", "12,345", "80,00 90,00"):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorMonetarioInvalido):
                    parse_valor_monetario(texto)


class ConversaoDeValoresLegadosTests(SimpleTestCase):
    """A decisão que a migração do `NOVO-10` toma linha a linha.

    Testada aqui, e não pelo maquinário de migração, porque é uma função pura:
    o que importa provar é a regra, não o `ALTER TABLE`.
    """

    def test_valor_com_anotacao_vira_numero_mais_texto(self):
        """O documento continua imprimindo "R$80,00 (saque)" depois da migração."""
        self.assertEqual(
            converter_valor_legado("R$80,00 (saque)"),
            (Decimal("80.00"), "(saque)"),
        )

    def test_valor_limpo_vira_numero_sem_observacao(self):
        self.assertEqual(converter_valor_legado("R$80,00"), (Decimal("80.00"), ""))

    def test_texto_que_nao_e_numero_e_preservado_como_observacao(self):
        """Nada é descartado: sem número, o texto original sobrevive.

        O RT volta a mostrar o valor padrão — melhor do que imprimir "abc"
        como se fosse dinheiro — e a anotação fica visível para correção.
        """
        for texto in ("abc", "-90", "350,00,00", "R$ mil reais"):
            with self.subTest(texto=texto):
                valor, observacao = converter_valor_legado(texto)

                self.assertIsNone(valor)
                self.assertEqual(observacao, texto)

    def test_zero_nao_sobrevive_como_valor(self):
        """Zero nunca foi diária recebida válida; vira observação também."""
        valor, observacao = converter_valor_legado("R$ 0,00")

        self.assertIsNone(valor)
        self.assertEqual(observacao, "R$ 0,00")

    def test_vazio_continua_vazio(self):
        self.assertEqual(converter_valor_legado(""), (None, ""))
