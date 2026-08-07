from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from cadastros.models import Cidade, Estado
from oficios.models import Oficio
from roteiros.models import Roteiro, RoteiroDestino
from core.testing import area_de_teste


class DiagnosticarRoteirosTests(TestCase):
    def setUp(self):
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado2, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})
        self.cidade_dest, _ = Cidade.objects.get_or_create(nome="FLORIANOPOLIS", estado=self.estado2, defaults={"uf": "SC"})

    def _run(self, *args):
        out = StringIO()
        call_command("diagnosticar_roteiros", *args, stdout=out)
        return out.getvalue()

    def test_marca_roteiro_vazio_como_vazio_e_orfao(self):
        Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_estado=self.estado, origem_cidade=self.cidade_sede)
        saida = self._run()
        self.assertIn("VAZIO", saida)
        self.assertIn("ORFAO", saida)
        self.assertIn("1 orfaos", saida)
        self.assertIn("1 vazios", saida)

    def test_roteiro_referenciado_por_oficio_nao_e_orfao(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_estado=self.estado, origem_cidade=self.cidade_sede)
        RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado2, cidade=self.cidade_dest, ordem=0)
        Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026, roteiro=roteiro)
        saida = self._run()
        self.assertNotIn("ORFAO", saida)
        self.assertIn("oficios=#1/2026", saida)
        self.assertIn("0 orfaos", saida)

    def test_detecta_grupo_duplicado_pela_assinatura(self):
        for _ in range(2):
            roteiro = Roteiro.objects.create(area=area_de_teste(), 
                tipo=Roteiro.TIPO_AVULSO,
                origem_estado=self.estado,
                origem_cidade=self.cidade_sede,
                saida_dt="2026-07-01T08:00:00Z",
            )
            RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado2, cidade=self.cidade_dest, ordem=0)
        saida = self._run()
        self.assertIn("DUPLICADO", saida)
        self.assertIn("2 em grupos duplicados", saida)

    def test_apenas_problemas_omite_roteiros_saudaveis(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_estado=self.estado, origem_cidade=self.cidade_sede)
        RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado2, cidade=self.cidade_dest, ordem=0)
        Oficio.objects.create(area=area_de_teste(), numero=2, ano=2026, roteiro=roteiro)
        saida = self._run("--apenas-problemas")
        self.assertNotIn(f"#{roteiro.pk} ", saida)
