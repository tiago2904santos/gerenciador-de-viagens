from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from cadastros.models import Cidade, Estado
from eventos.models import Evento
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro
from core.testing import area_de_teste


class LimparRoteirosOrfaosTests(TestCase):
    def setUp(self):
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})

    def _run(self, *args):
        out = StringIO()
        call_command("limpar_roteiros_orfaos", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_nao_apaga_nada(self):
        orfao = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        saida = self._run()
        self.assertIn(f"#{orfao.pk}", saida)
        self.assertIn("seriam apagados", saida)
        self.assertTrue(Roteiro.objects.filter(pk=orfao.pk).exists())

    def test_confirmar_apaga_apenas_orfaos(self):
        orfao = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        referenciado_por_oficio = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026, roteiro=referenciado_por_oficio)
        referenciado_por_prestacao = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        oficio_da_prestacao = Oficio.objects.create(
            area=area_de_teste(), numero=99, ano=2026, protocolo="123456789"
        )
        prestacao = PrestacaoContas.objects.get(oficio=oficio_da_prestacao)
        prestacao.roteiro_ajustado = referenciado_por_prestacao
        prestacao.save(update_fields=["roteiro_ajustado", "atualizado_em"])
        referenciado_por_evento = Roteiro.objects.create(area=area_de_teste(), 
            tipo=Roteiro.TIPO_EVENTO,
            origem_cidade=self.cidade_sede,
            evento=Evento.objects.create(area=area_de_teste(), titulo="Evento teste"),
        )

        saida = self._run("--confirmar")

        self.assertIn("apagado", saida)
        self.assertFalse(Roteiro.objects.filter(pk=orfao.pk).exists())
        self.assertTrue(Roteiro.objects.filter(pk=referenciado_por_oficio.pk).exists())
        self.assertTrue(Roteiro.objects.filter(pk=referenciado_por_prestacao.pk).exists())
        self.assertTrue(Roteiro.objects.filter(pk=referenciado_por_evento.pk).exists())

    def test_sem_orfaos_nao_apaga_nada(self):
        referenciado = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        Oficio.objects.create(area=area_de_teste(), numero=2, ano=2026, roteiro=referenciado)
        saida = self._run("--confirmar")
        self.assertIn("Nenhum roteiro orfao", saida)
        self.assertTrue(Roteiro.objects.filter(pk=referenciado.pk).exists())
