from django.test import TestCase

from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante
from planos_trabalho.services import aplicar_textos_padrao
from planos_trabalho.services import format_periodo_evento_extenso
from planos_trabalho.services import montar_efetivo_texto
from planos_trabalho.services import montar_texto_coordenacao
from planos_trabalho.services import texto_padrao_contextualizacao

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa
from .helpers import criar_servidor

from datetime import date


class TextosPadraoTests(TestCase):
    def setUp(self):
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)

    def test_contextualizacao_padrao_usa_municipio_e_programa(self):
        plano = criar_plano_maringa(self.maringa)
        plano.programa = ProgramaSolicitante.objects.get(nome="PROGRAMA PARANÁ EM AÇÃO")
        texto = texto_padrao_contextualizacao(plano)
        self.assertIn("município de Maringá/PR", texto)
        self.assertIn("Programa Paraná em Ação", texto)
        self.assertIn("PCPR na Comunidade", texto)

    def test_aplicar_textos_padrao_preenche_somente_vazios(self):
        plano = criar_plano_maringa(self.maringa)
        plano.consideracao_final = "Texto editado pelo usuário."
        alterados = aplicar_textos_padrao(plano)
        self.assertEqual(alterados, ["contextualizacao"])
        self.assertIn("Maringá/PR", plano.contextualizacao)
        self.assertEqual(plano.consideracao_final, "Texto editado pelo usuário.")


class PeriodoExtensoTests(TestCase):
    def test_mesmo_mes(self):
        self.assertEqual(
            format_periodo_evento_extenso(date(2026, 6, 25), date(2026, 6, 27)),
            "25 a 27 de junho de 2026",
        )

    def test_meses_diferentes(self):
        self.assertEqual(
            format_periodo_evento_extenso(date(2026, 6, 30), date(2026, 7, 2)),
            "30 de junho a 02 de julho de 2026",
        )

    def test_dia_unico(self):
        self.assertEqual(
            format_periodo_evento_extenso(date(2026, 6, 25), date(2026, 6, 25)),
            "25 de junho de 2026",
        )


class CoordenacaoTests(TestCase):
    def setUp(self):
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa)

    def test_coordenador_adm_servidor_do_banco(self):
        self.plano.coordenador_adm = criar_servidor()
        texto = montar_texto_coordenacao(self.plano)
        self.assertIn("Coordenador(a) Administrativo(a)", texto)
        self.assertIn("Papiloscopista Juliana Villela de Barros", texto)
        self.assertNotIn("Operacional", texto)

    def test_coordenador_adm_manual(self):
        self.plano.coordenador_adm_modo = PlanoTrabalho.COORDENADOR_MODO_MANUAL
        self.plano.coordenador_adm_nome_manual = "Maria da Silva"
        self.plano.coordenador_adm_cargo_manual = "Investigadora"
        texto = montar_texto_coordenacao(self.plano)
        self.assertIn("Investigadora Maria da Silva", texto)

    def test_coordenador_operacional_opcional(self):
        self.plano.coordenador_adm = criar_servidor()
        self.plano.coordenador_op_modo = PlanoTrabalho.COORDENADOR_MODO_MANUAL
        self.plano.coordenador_op_nome_manual = "José Pereira"
        self.plano.coordenador_op_cargo_manual = "Escrivão"
        texto = montar_texto_coordenacao(self.plano)
        self.assertIn("Coordenador(a) Operacional", texto)
        self.assertIn("Escrivão José Pereira", texto)

    def test_coordenador_operacional_em_branco_nao_gera_texto(self):
        self.plano.coordenador_adm = criar_servidor()
        self.plano.coordenador_op = None
        self.plano.coordenador_op_nome_manual = ""
        texto = montar_texto_coordenacao(self.plano)
        self.assertNotIn("Operacional", texto)
        self.assertFalse(self.plano.tem_coordenador_operacional)


class EfetivoTextoTests(TestCase):
    def setUp(self):
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)

    def test_efetivo_texto_pluraliza_por_cargo(self):
        from cadastros.models import Cargo
        from planos_trabalho.models import EfetivoPlano

        plano = criar_plano_maringa(self.maringa, efetivo=6)
        papiloscopista = Cargo.objects.create(nome="Papiloscopista")
        EfetivoPlano.objects.create(plano=plano, cargo=papiloscopista, quantidade=1)

        texto = montar_efetivo_texto(plano)
        self.assertIn("1 Papiloscopista", texto)
        self.assertIn("6 Policiais Civis", texto)
