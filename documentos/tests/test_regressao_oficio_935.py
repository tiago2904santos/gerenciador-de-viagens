"""
Regressão agregada #935: `build_oficio_docxtpl_context` com roteiro, destino fora do PR,
motorista externo à equipe, valor monetário e assunto documental (sem campo wizard).
"""

from datetime import date
from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from oficios.assunto_oficio import ASSUNTO_AUTORIZACAO
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho


class RegressaoOficio935ContextoTests(TestCase):
    def setUp(self):
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.email = "Setor.PDF@Instituicao.br"
        cfg.logradouro = "AV. TESTE"
        cfg.numero = "935"
        cfg.bairro = "CENTRO"
        cfg.cidade_endereco = "LONDRINA"
        cfg.uf = "PR"
        cfg.save(
            update_fields=[
                "email",
                "logradouro",
                "numero",
                "bairro",
                "cidade_endereco",
                "uf",
            ],
        )

        self.estado_pr, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado_sc, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_curitiba, _ = Cidade.objects.get_or_create(
            nome="CURITIBA", estado=self.estado_pr, defaults={"uf": "PR"}
        )
        self.cidade_floripa, _ = Cidade.objects.get_or_create(
            nome="FLORIANOPOLIS", estado=self.estado_sc, defaults={"uf": "SC"}
        )

        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
        roteiro.saida_dt = timezone.make_aware(
            datetime(2026, 6, 15, 7, 0, 0),
            timezone.get_current_timezone(),
        )
        roteiro.quantidade_diarias = "12"
        roteiro.valor_diarias = Decimal("1935.42")
        roteiro.valor_diarias_extenso = (
            "UM MIL NOVECENTOS E TRINTA E CINCO REAIS E QUARENTA E DOIS CENTAVOS"
        )
        roteiro.save(
            update_fields=[
                "saida_dt",
                "quantidade_diarias",
                "valor_diarias",
                "valor_diarias_extenso",
            ],
        )

        RoteiroDestino.objects.create(
            roteiro=roteiro,
            estado=self.estado_sc,
            cidade=self.cidade_floripa,
            ordem=0,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado_pr,
            origem_cidade=self.cidade_curitiba,
            destino_estado=self.estado_sc,
            destino_cidade=self.cidade_floripa,
            saida_dt=roteiro.saida_dt,
        )

        viajante = Servidor.objects.create(nome="SERVIDOR OFICIO 935")
        motorista = Servidor.objects.create(nome="MOTORISTA EXTERNO 935")

        oficio = Oficio.objects.create(
            data_criacao=date(2026, 5, 1),
            numero=9,
            ano=2026,
            protocolo="123456789",
            roteiro=roteiro,
            motorista=motorista,
            motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
            motorista_oficio_referencia="7/2026",
            motorista_protocolo_ref="123456789",
            assunto="[DEMO OFICIO] não deve aparecer",
        )
        oficio.servidores.add(viajante)
        self.oficio = Oficio.objects.prefetch_related(
            "servidores",
            "roteiro__destinos",
            "roteiro__trechos",
        ).get(pk=oficio.pk)

    def test_contexto_docxtpl_cenario_935(self):
        ctx = build_oficio_docxtpl_context(self.oficio)
        self.assertEqual(ctx["assunto_linha"], ASSUNTO_AUTORIZACAO)
        self.assertEqual(ctx["assunto_oficio"], "(Autorização)")
        self.assertNotIn("DEMO OFICIO", ctx["assunto_linha"])
        self.assertEqual(ctx["email"], "setor.pdf@instituicao.br")
        self.assertIn("Londrina/PR", ctx["endereco"])
        self.assertIn(" - ", ctx["endereco"])
        self.assertTrue(ctx["diaria"].startswith("R$1.935,42"))
        self.assertEqual(ctx["valor_total_oficio"], ctx["diaria"])
        self.assertIn("Um mil novecentos", ctx["diaria"])
        self.assertIn("Motorista Externo 935", ctx["motorista_formatado"])
        self.assertIn("Ofício do Motorista: 7/2026", ctx["motorista_formatado"])
        self.assertIn("Protocolo do Motorista:", ctx["motorista_formatado"])
        self.assertEqual(ctx["orgao_destino"], "SESP")
        self.assertIn("Florianopolis/SC", ctx["destinos_bloco"])
        self.assertIn("Curitiba/PR", ctx["col_ida_saida"])
        self.assertIn("Servidor Oficio 935", ctx["col_servidor"])
