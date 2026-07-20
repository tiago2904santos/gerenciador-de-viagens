from __future__ import annotations

from datetime import date

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor

from ..docxtpl_context import build_os_docxtpl_context
from ..models import OrdemServico


class OrdemServicoDocxtplContextTests(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(nome="PARANA", sigla="PR")
        self.cidade = Cidade.objects.create(nome="CURITIBA", estado=self.estado, uf="PR")
        self.motorista = Servidor.objects.create(nome="MOTORISTA TESTE")
        self.tecnico = Servidor.objects.create(nome="TECNICO TESTE")
        self.montagem = Servidor.objects.create(nome="APOIO MONTAGEM")
        self.escolta = Servidor.objects.create(nome="APOIO ESCOLTA")
        self.coordenador = Servidor.objects.create(nome="COORDENADOR CERIMONIAL")
        self.apoio = Servidor.objects.create(nome="APOIO CERIMONIAL")
        self.preparacao = Servidor.objects.create(nome="APOIO PREPARACAO")

    def _ordem(self, tipo):
        ordem = OrdemServico.objects.create(
            tipo_necessidade=tipo,
            data_evento_inicio=date(2026, 8, 10),
            data_evento_fim=date(2026, 8, 12),
            motivo="evento institucional",
            motorista_equipe=self.motorista,
            tecnico_equipe=self.tecnico,
            apoio_montagem=self.montagem,
            apoio_escolta=self.escolta,
            coordenador_cerimonial=self.coordenador,
            apoio_cerimonial=self.apoio,
            apoio_preparacao=self.preparacao,
        )
        ordem.destinos.set([self.cidade])
        return ordem

    def test_caminhao_descreve_competencias_e_dois_dias(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_CAMINHAO))

        self.assertEqual(ctx["referencia"], "Deslocamento - Caminhão de apoio")
        self.assertEqual(len(ctx["competencias_equipe"]), 4)
        self.assertIn("Motorista Teste", ctx["competencias_equipe"][0])
        self.assertIn("dois dias de antecedência", " ".join(ctx["justificativas"]))
        self.assertIn("dois dias posteriores", " ".join(ctx["justificativas"]))

    def test_microonibus_nao_aplica_regra_de_dois_dias(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_MICROONIBUS))

        self.assertEqual(ctx["referencia"], "Deslocamento - Micro-ônibus")
        self.assertEqual(len(ctx["competencias_equipe"]), 4)
        self.assertIn("sem necessidade de deslocamento com dois dias de antecedência", " ".join(ctx["justificativas"]))

    def test_cerimonial_descreve_ida_antecipada_e_competencias(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_CERIMONIAL_ANTECIPADO))

        self.assertEqual(ctx["referencia"], "Deslocamento - Equipe de Cerimonial")
        self.assertEqual(len(ctx["competencias_equipe"]), 3)
        self.assertIn("Coordenador Cerimonial", ctx["competencias_equipe"][0])
        self.assertIn("visita técnica prévia", " ".join(ctx["justificativas"]))

    def test_operacao_retorno_posterior_justifica_um_dia(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_OPERACAO_RETORNO_POSTERIOR))

        self.assertEqual(ctx["referencia"], "Deslocamento - Operação policial com retorno posterior")
        self.assertIn("retorno um dia posterior", " ".join(ctx["justificativas"]))
