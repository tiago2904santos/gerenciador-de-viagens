from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from cadastros.models import Cidade, Estado
from oficios.models import Oficio
from roteiros.models import Roteiro, RoteiroDestino
from core.testing import area_de_teste


class DesvincularRoteiroVazioTests(TestCase):
    def setUp(self):
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})

    def _run(self, pk, *args):
        out = StringIO()
        call_command("desvincular_roteiro_vazio", pk, *args, stdout=out)
        return out.getvalue()

    def test_recusa_se_roteiro_tem_destino(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado, cidade=self.cidade_sede, ordem=0)
        with self.assertRaises(CommandError):
            self._run(roteiro.pk, "--confirmar")
        self.assertTrue(Roteiro.objects.filter(pk=roteiro.pk).exists())

    def test_pk_inexistente_gera_erro(self):
        with self.assertRaises(CommandError):
            self._run(999999)

    def test_dry_run_nao_altera_nada(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        oficio = Oficio.objects.create(area=area_de_teste(), numero=89, ano=2026, roteiro=roteiro)
        saida = self._run(roteiro.pk)
        self.assertIn("Nada foi alterado", saida)
        oficio.refresh_from_db()
        self.assertEqual(oficio.roteiro_id, roteiro.pk)
        self.assertTrue(Roteiro.objects.filter(pk=roteiro.pk).exists())

    def test_confirmar_desvincula_e_apaga(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), tipo=Roteiro.TIPO_AVULSO, origem_cidade=self.cidade_sede)
        oficio = Oficio.objects.create(area=area_de_teste(), numero=89, ano=2026, roteiro=roteiro)
        saida = self._run(roteiro.pk, "--confirmar")
        self.assertIn("desvinculado e apagado", saida)
        oficio.refresh_from_db()
        self.assertIsNone(oficio.roteiro_id)
        self.assertFalse(Roteiro.objects.filter(pk=roteiro.pk).exists())
