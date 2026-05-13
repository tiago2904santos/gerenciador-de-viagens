from django.test import TestCase

from cadastros.models import ConfiguracaoSistema
from oficios.docxtpl_context import build_justificativa_docxtpl_context
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio


class BuildOficioCapitalizacaoTests(TestCase):
    def setUp(self):
        ConfiguracaoSistema.get_singleton()

    def test_sem_roteiro_orgao_destino_legivel(self):
        oficio = Oficio.objects.create()
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["orgao_destino"], "Gabinete do Delegado Geral Adjunto")
        self.assertIn(" do ", f" {ctx['orgao_destino']} ")

    def test_cabecalho_institucional_maiusculo_corpo_legivel(self):
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.nome_orgao = "DEPARTAMENTO DE POLÍCIA"
        cfg.unidade = "DELEGACIA REGIONAL DE POLÍCIA DE LONDRINA"
        cfg.save(update_fields=["nome_orgao", "unidade"])
        oficio = Oficio.objects.create()
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["nome_orgao_cabecalho"], "DEPARTAMENTO DE POLÍCIA")
        self.assertEqual(ctx["unidade_cabecalho"], "DELEGACIA REGIONAL DE POLÍCIA DE LONDRINA")
        self.assertIn(" de ", f" {ctx['unidade']} ")
        self.assertIn(" de ", f" {ctx['nome_orgao']} ")

    def test_cabecalho_orgao_maiusculo_com_entrada_title_case(self):
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.nome_orgao = "Departamento de Polícia"
        cfg.unidade = "Delegacia Regional de Londrina"
        cfg.save(update_fields=["nome_orgao", "unidade"])
        oficio = Oficio.objects.create()
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["nome_orgao_cabecalho"], "DEPARTAMENTO DE POLÍCIA")
        self.assertEqual(ctx["unidade_cabecalho"], "DELEGACIA REGIONAL DE LONDRINA")

    def test_justificativa_rodape_nao_todo_maiusculo(self):
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.divisao = "ASSESSORIA DE COMUNICAÇÃO SOCIAL"
        cfg.unidade = "UNIDADE TESTE"
        cfg.logradouro = "RUA EXEMPLO"
        cfg.numero = "1"
        cfg.bairro = "BAIRRO"
        cfg.cidade_endereco = "CURITIBA"
        cfg.uf = "PR"
        cfg.cep = "80000000"
        cfg.telefone = "4133334444"
        cfg.email = "TESTE@EX.COM"
        cfg.save()
        oficio = Oficio.objects.create()
        ctx = build_justificativa_docxtpl_context(oficio)
        self.assertIn("Assessoria de Comunicação Social", ctx["unidade_rodape"])
        self.assertNotEqual(ctx["unidade_rodape"].strip(), ctx["unidade_rodape"].upper())
