from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from cadastros.models import Cidade, Estado, Servidor
from oficios.models import Oficio
from prestacoes_contas.diario_services import clonar_roteiro
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro, RoteiroDestino


class DiagnosticarRoteirosAjustadosTests(TestCase):
    def setUp(self):
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado2, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})
        self.cidade_dest, _ = Cidade.objects.get_or_create(nome="FLORIANOPOLIS", estado=self.estado2, defaults={"uf": "SC"})
        self.servidor = Servidor.objects.create(nome="Servidor Teste")

    def _run(self):
        out = StringIO()
        call_command("diagnosticar_roteiros_ajustados", stdout=out)
        return out.getvalue()

    def _roteiro_com_destino(self, observacoes=""):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO, origem_estado=self.estado, origem_cidade=self.cidade_sede,
            observacoes=observacoes,
        )
        RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado2, cidade=self.cidade_dest, ordem=0)
        return roteiro

    def test_copia_identica_e_marcada_como_segura(self):
        original = self._roteiro_com_destino()
        oficio = Oficio.objects.create(numero=1, ano=2026, roteiro=original)
        copia = clonar_roteiro(original)
        PrestacaoContas.objects.create(oficio=oficio, servidor=self.servidor, roteiro_ajustado=copia)

        saida = self._run()
        self.assertIn("IDENTICA", saida)
        self.assertIn("1 identicas", saida)
        self.assertIn("0 divergentes", saida)

    def test_copia_alterada_e_marcada_como_divergente(self):
        original = self._roteiro_com_destino(observacoes="ORIGINAL")
        oficio = Oficio.objects.create(numero=2, ano=2026, roteiro=original)
        copia = clonar_roteiro(original)
        copia.observacoes = "AJUSTADO"
        copia.save(update_fields=["observacoes"])
        PrestacaoContas.objects.create(oficio=oficio, servidor=self.servidor, roteiro_ajustado=copia)

        saida = self._run()
        self.assertIn("DIVERGENTE", saida)
        self.assertIn("observacoes", saida)
        self.assertIn("0 identicas", saida)
        self.assertIn("1 divergentes", saida)
