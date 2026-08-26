"""O RT imprime a diária inteira do servidor, não a equipe dividindo o valor.

O roteiro persiste sempre o valor de UM servidor (`roteiro_editor` calcula com
`quantidade_servidores=1`) e quem multiplica pelo efetivo é o ofício, uma vez só,
em `Oficio.diarias_para_servidores()`. `prestacoes_contas.services` dividia esse
valor pela equipe: com 2 servidores, cada RT saía com metade do que a pessoa tem
a sacar — R$ 624,68 impressos como R$ 312,34.
"""

from decimal import Decimal

from django.test import TestCase

from cadastros.models import Cargo
from cadastros.models import Servidor
from core.testing import area_de_teste
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.models import RelatorioTecnico
from prestacoes_contas.services import aplicar_diaria_recebida
from prestacoes_contas.services import diaria_inicial_da_prestacao
from prestacoes_contas.services import diaria_inicial_do_oficio
from prestacoes_contas.services import garantir_campos_padrao_relatorio_tecnico
from prestacoes_contas.services import valor_diaria_liberado
from roteiros.models import Roteiro


class DiariaDoRelatorioTecnicoNaoDivideEntreAEquipeTests(TestCase):
    def setUp(self):
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Agente")
        self.servidor_a = Servidor.objects.create(
            area=area_de_teste(), nome="Servidor A", cargo=cargo, cpf="11122233344"
        )
        self.servidor_b = Servidor.objects.create(
            area=area_de_teste(), nome="Servidor B", cargo=cargo, cpf="55566677788"
        )
        self.roteiro = Roteiro.objects.create(
            area=area_de_teste(), valor_diarias=Decimal("624.68")
        )
        self.oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=77,
            ano=2026,
            protocolo="123456789",
            roteiro=self.roteiro,
        )
        self.oficio.servidores.add(self.servidor_a, self.servidor_b)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.ps_a = self.prestacao.servidores_prestacao.get(servidor=self.servidor_a)

    def test_valor_inicial_do_rt_e_o_valor_cheio_do_roteiro(self):
        self.assertEqual(diaria_inicial_do_oficio(self.prestacao), "R$624,68")
        self.assertEqual(diaria_inicial_da_prestacao(self.prestacao), "R$624,68")

    def test_teto_do_valor_recebido_e_o_valor_cheio(self):
        self.assertEqual(valor_diaria_liberado(self.ps_a), Decimal("624.68"))
        self.assertEqual(aplicar_diaria_recebida(self.ps_a, "R$ 624,68"), [])
        self.assertEqual(self.ps_a.diaria_valor_override, Decimal("624.68"))

    def test_valor_dividido_ja_gravado_e_corrigido_no_proximo_acesso(self):
        relatorio = RelatorioTecnico.objects.create(
            prestacao=self.prestacao, diaria="R$312,34"
        )

        garantir_campos_padrao_relatorio_tecnico(relatorio)

        relatorio.refresh_from_db()
        self.assertEqual(relatorio.diaria, "R$624,68")

    def test_valor_digitado_a_mao_nao_e_reescrito(self):
        relatorio = RelatorioTecnico.objects.create(
            prestacao=self.prestacao, diaria="R$ 500,00 (adiantamento)"
        )

        garantir_campos_padrao_relatorio_tecnico(relatorio)

        relatorio.refresh_from_db()
        self.assertEqual(relatorio.diaria, "R$ 500,00 (adiantamento)")
