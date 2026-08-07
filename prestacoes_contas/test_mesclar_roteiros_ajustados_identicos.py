from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from cadastros.models import Cidade, Estado, Servidor
from oficios.models import Oficio
from prestacoes_contas.diario_services import clonar_roteiro
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro, RoteiroDestino
from core.testing import area_de_teste


class MesclarRoteirosAjustadosIdenticosTests(TestCase):
    def setUp(self):
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado2, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})
        self.cidade_dest, _ = Cidade.objects.get_or_create(nome="FLORIANOPOLIS", estado=self.estado2, defaults={"uf": "SC"})
        self.servidor = Servidor.objects.create(area=area_de_teste(), nome="Servidor Teste")

    def _run(self, *args):
        out = StringIO()
        call_command("mesclar_roteiros_ajustados_identicos", *args, stdout=out)
        return out.getvalue()

    def _roteiro_com_destino(self, observacoes=""):
        roteiro = Roteiro.objects.create(area=area_de_teste(), 
            tipo=Roteiro.TIPO_AVULSO, origem_estado=self.estado, origem_cidade=self.cidade_sede,
            observacoes=observacoes,
        )
        RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado2, cidade=self.cidade_dest, ordem=0)
        return roteiro

    def test_dry_run_nao_altera_nada(self):
        original = self._roteiro_com_destino()
        oficio = Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026, roteiro=original)
        copia = clonar_roteiro(original)
        oficio.servidores.add(self.servidor)
        pc = PrestacaoContas.objects.get(oficio=oficio)
        pc.roteiro_ajustado = copia
        pc.save(update_fields=["roteiro_ajustado"])

        saida = self._run()
        self.assertIn("seriam descartadas", saida)
        pc.refresh_from_db()
        self.assertEqual(pc.roteiro_ajustado_id, copia.pk)
        self.assertTrue(Roteiro.objects.filter(pk=copia.pk).exists())

    def test_confirmar_descarta_copia_identica_e_apaga(self):
        original = self._roteiro_com_destino()
        oficio = Oficio.objects.create(area=area_de_teste(), numero=2, ano=2026, roteiro=original)
        copia = clonar_roteiro(original)
        oficio.servidores.add(self.servidor)
        pc = PrestacaoContas.objects.get(oficio=oficio)
        pc.roteiro_ajustado = copia
        pc.save(update_fields=["roteiro_ajustado"])

        saida = self._run("--confirmar")

        self.assertIn("apagada", saida)
        pc.refresh_from_db()
        self.assertIsNone(pc.roteiro_ajustado_id)
        self.assertFalse(Roteiro.objects.filter(pk=copia.pk).exists())
        self.assertTrue(Roteiro.objects.filter(pk=original.pk).exists())

    def test_nao_mexe_em_copia_divergente(self):
        original = self._roteiro_com_destino(observacoes="ORIGINAL")
        oficio = Oficio.objects.create(area=area_de_teste(), numero=3, ano=2026, roteiro=original)
        copia = clonar_roteiro(original)
        copia.observacoes = "AJUSTADO"
        copia.save(update_fields=["observacoes"])
        oficio.servidores.add(self.servidor)
        pc = PrestacaoContas.objects.get(oficio=oficio)
        pc.roteiro_ajustado = copia
        pc.save(update_fields=["roteiro_ajustado"])

        saida = self._run("--confirmar")

        self.assertIn("Nenhuma copia identica", saida)
        pc.refresh_from_db()
        self.assertEqual(pc.roteiro_ajustado_id, copia.pk)
        self.assertTrue(Roteiro.objects.filter(pk=copia.pk).exists())

    def test_nao_apaga_copia_ainda_referenciada_por_outra_prestacao(self):
        original = self._roteiro_com_destino()
        oficio1 = Oficio.objects.create(area=area_de_teste(), numero=4, ano=2026, roteiro=original)
        oficio2 = Oficio.objects.create(area=area_de_teste(), numero=5, ano=2026)
        copia = clonar_roteiro(original)
        oficio1.servidores.add(self.servidor)
        pc1 = PrestacaoContas.objects.get(oficio=oficio1)
        pc1.roteiro_ajustado = copia
        pc1.save(update_fields=["roteiro_ajustado"])
        servidor2 = Servidor.objects.create(area=area_de_teste(), nome="Servidor 2")
        oficio2.servidores.add(servidor2)
        pc2 = PrestacaoContas.objects.get(oficio=oficio2)
        pc2.roteiro_ajustado = copia
        pc2.save(update_fields=["roteiro_ajustado"])

        self._run("--confirmar")

        pc1.refresh_from_db()
        self.assertIsNone(pc1.roteiro_ajustado_id)
        self.assertTrue(Roteiro.objects.filter(pk=copia.pk).exists())
