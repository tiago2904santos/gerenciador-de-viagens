from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Servidor
from core.testing import area_de_teste
from core.testing import com_request
from oficios.models import Oficio
from oficios.presenters import apresentar_oficio_card
from oficios.services import DocumentoFormato
from oficios.services import avaliar_oficio_dados_viajantes
from oficios.services import gerar_resposta_documento_oficio
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.selectors import listar_prestacoes
from roteiros.models import Roteiro


class ProtocoloObrigatorioOficioTests(TestCase):
    """Regressões do NOVO-20260824-171506-f3e537697e71."""

    def setUp(self):
        self.enterContext(com_request(area_de_teste()))
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Agente")
        self.servidor = Servidor.objects.create(
            area=area_de_teste(),
            nome="Servidor sem protocolo",
            cargo=self.cargo,
            cpf="12345678901",
        )

    def test_sem_protocolo_forca_status_rascunho(self):
        oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=158,
            ano=2026,
            status=Oficio.STATUS_GERADO,
        )

        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)

    def test_sem_protocolo_nao_cria_prestacao_ao_adicionar_equipe(self):
        oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=158,
            ano=2026,
        )

        oficio.servidores.add(self.servidor)

        self.assertFalse(PrestacaoContas.all_objects.filter(oficio=oficio).exists())

    def test_protocolo_ausente_mantem_pendencia_documental(self):
        oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=158,
            ano=2026,
            motivo="Motivo informado",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)

        avaliacao = avaliar_oficio_dados_viajantes(oficio=oficio)

        self.assertIn("Informe o protocolo.", avaliacao["pendencias"])

    def test_lista_prioriza_rascunho_e_omite_documentos_sem_protocolo(self):
        roteiro = Roteiro.objects.create(
            area=area_de_teste(),
            saida_dt=timezone.now() - timezone.timedelta(hours=1),
            chegada_dt=timezone.now() + timezone.timedelta(hours=1),
        )
        oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=158,
            ano=2026,
            roteiro=roteiro,
            status=Oficio.STATUS_GERADO,
        )

        card = apresentar_oficio_card(oficio, menus_sob_demanda=False)

        self.assertEqual(card["chip_label"], "Rascunho")
        self.assertEqual(card["status_variant"], "rascunho")
        self.assertEqual(card["footer"]["menus"], [])

    def test_geracao_direta_do_documento_e_bloqueada_sem_protocolo(self):
        oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=158,
            ano=2026,
        )

        with self.assertRaisesMessage(ValidationError, "O ofício não pode ser gerado"):
            gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF)

    def test_prestacao_legada_some_da_lista_quando_protocolo_e_removido(self):
        oficio = Oficio.objects.create(
            area=area_de_teste(),
            numero=158,
            ano=2026,
            protocolo="123456789",
        )
        oficio.servidores.add(self.servidor)
        prestacao = PrestacaoContas.all_objects.get(oficio=oficio)

        oficio.protocolo = ""
        oficio.save(update_fields=["protocolo"])

        self.assertTrue(PrestacaoContas.all_objects.filter(pk=prestacao.pk).exists())
        self.assertFalse(listar_prestacoes().filter(prestacao=prestacao).exists())
