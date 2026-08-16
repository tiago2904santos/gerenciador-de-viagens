"""O termo não é UM documento — e a tela passou a dizer isso (2026-08-16).

Um termo se desdobra em três coisas diferentes: o genérico (sem servidor), o da
viatura e um por servidor. O botão de baixar entregava sempre o pacote inteiro
fundido num arquivo só, e a prévia do formulário mostrava um conjunto ainda
outro — só os servidores.

Aqui se fixam as duas metades da correção:

1. o COMPILADO tem genérico → viatura → um por servidor, nessa ordem;
2. o endpoint que alimenta o modal descreve exatamente o que existe, e marca
   `unico` quando não há o que escolher — é por esse campo que a tela decide
   baixar direto, sem abrir diálogo.

Os testes de ordem trocam os geradores por dublês: o que está em jogo é QUAIS
documentos entram e em que ordem, não o conteúdo do PDF. Gerar de verdade aqui
custaria uma conversão DOCX→PDF por caso, para provar a mesma coisa.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.testing import area_de_teste
from core.testing import com_request
from core.testing import vincular_area
from documentos.services.types import DocumentoFormato
from termos import async_documents
from termos.card_builder import montar_downloads_do_termo
from termos.models import TermoAutorizacao


class DownloadsDoTermoTests(TestCase):
    def setUp(self):
        self.enterContext(com_request(area_de_teste()))
        self.user = get_user_model().objects.create_user(username="tester_downloads", password="123456")
        vincular_area(self.user)
        self.client.force_login(self.user)

        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Londrina", estado=self.estado, uf="PR")
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Investigador")
        unidade = Unidade.objects.create(area=area_de_teste(), nome="Unidade", sigla="UN")
        self.servidor_1 = Servidor.objects.create(
            area=area_de_teste(), nome="Servidor Um", cargo=cargo, cpf="11111111111",
            rg="1234567", unidade=unidade,
        )
        self.servidor_2 = Servidor.objects.create(
            area=area_de_teste(), nome="Servidor Dois", cargo=cargo, cpf="22222222222",
            rg="7654321", unidade=unidade,
        )
        combustivel = Combustivel.objects.create(area=area_de_teste(), nome="Gasolina")
        self.viatura = Viatura.objects.create(
            area=area_de_teste(), placa="ABC1234", modelo="Duster",
            combustivel=combustivel, tipo=Viatura.TIPO_CARACTERIZADA,
        )
        self.termo = TermoAutorizacao.objects.create(
            area=area_de_teste(),
            destino_estado=self.estado,
            destino_cidade=self.cidade,
        )

    def _com_equipe_e_viatura(self):
        self.termo.viatura = self.viatura
        self.termo.save()
        self.termo.servidores.add(self.servidor_1, self.servidor_2)
        return self.termo

    def _pks_da_equipe(self, termo):
        """A ordem de `servidores_efetivos()` — por nome, e não a de inserção.

        O compilado tem de sair na MESMA ordem em que o cartão lista a equipe;
        fixar a ordem de inserção aqui faria o teste passar com o documento
        saindo embaralhado em relação à tela.
        """
        return [servidor.pk for servidor in termo.servidores_efetivos()]

    # ---- a ordem do compilado ------------------------------------------------

    def _chamadas_do_compilado(self, termo):
        """Quem foi pedido, na ordem, para montar o PDF compilado."""
        chamadas = []

        def assinado_ou_gerado(_termo, servidor):
            chamadas.append(("assinado-ou-gerado", getattr(servidor, "pk", None)))
            return b"%PDF-fake"

        def gerar(_termo, servidor, _formato, forcar_viatura=False):
            chamadas.append(("gerado", "viatura" if forcar_viatura else getattr(servidor, "pk", None)))
            return mock.Mock(conteudo=b"%PDF-fake", content_type="application/pdf")

        with mock.patch.object(async_documents, "pdf_termo_cadastro_assinado_ou_gerado", assinado_ou_gerado), \
             mock.patch.object(async_documents, "gerar_termo_cadastro_um", gerar):
            async_documents._conteudos_compilados_pdf(termo)
        return chamadas

    def test_o_compilado_tem_generico_viatura_e_um_por_servidor_nessa_ordem(self):
        termo = self._com_equipe_e_viatura()

        self.assertEqual(
            self._chamadas_do_compilado(termo),
            [
                ("assinado-ou-gerado", None),   # o genérico
                ("gerado", "viatura"),          # a viatura
                *[("assinado-ou-gerado", pk) for pk in self._pks_da_equipe(termo)],
            ],
        )

    def test_sem_viatura_o_compilado_nao_tem_a_pagina_dela(self):
        self.termo.servidores.add(self.servidor_1)

        self.assertEqual(
            self._chamadas_do_compilado(self.termo),
            [("assinado-ou-gerado", None), ("assinado-ou-gerado", self.servidor_1.pk)],
        )

    def test_a_viatura_sai_do_gerador_e_nao_do_assinado(self):
        """Não existe termo de viatura assinado — pedi-lo por ali geraria um
        documento de servidor vazio no lugar do da viatura."""
        termo = self._com_equipe_e_viatura()

        chamadas = self._chamadas_do_compilado(termo)

        self.assertIn(("gerado", "viatura"), chamadas)
        self.assertNotIn(("assinado-ou-gerado", "viatura"), chamadas)

    def test_o_docx_compilado_segue_a_mesma_ordem(self):
        termo = self._com_equipe_e_viatura()
        pedidos = []

        def gerar(_termo, servidor, _formato, forcar_viatura=False):
            pedidos.append("viatura" if forcar_viatura else getattr(servidor, "pk", None))
            return mock.Mock(conteudo=b"docx", content_type="application/vnd.openxmlformats")

        with mock.patch.object(async_documents, "gerar_termo_cadastro_um", gerar):
            async_documents._documentos_compilados(termo, DocumentoFormato.DOCX)

        self.assertEqual(pedidos, [None, "viatura", *self._pks_da_equipe(termo)])

    # ---- o que o modal recebe ------------------------------------------------

    def test_o_endpoint_lista_o_generico_a_viatura_e_cada_servidor(self):
        termo = self._com_equipe_e_viatura()

        resposta = self.client.get(reverse("termos:termo_cadastro_downloads", args=[termo.pk]))

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(
            [item["id"] for item in dados["itens"]],
            ["generico", "viatura", *[f"servidor-{pk}" for pk in self._pks_da_equipe(termo)]],
        )
        self.assertFalse(dados["unico"])

    def test_cada_item_traz_as_duas_rotas_de_formato(self):
        dados = montar_downloads_do_termo(self._com_equipe_e_viatura())

        for item in dados["itens"]:
            with self.subTest(item=item["id"]):
                self.assertTrue(item["urls"]["pdf"], "sem rota de PDF")
                self.assertTrue(item["urls"]["docx"], "sem rota de DOCX")
        self.assertTrue(dados["compilado"]["pdf"])
        self.assertTrue(dados["compilado"]["docx"])

    def test_unico_e_verdadeiro_quando_so_existe_o_generico(self):
        """É este campo que faz a tela baixar direto, sem abrir o modal."""
        dados = montar_downloads_do_termo(self.termo)

        self.assertEqual([item["id"] for item in dados["itens"]], ["generico"])
        self.assertTrue(dados["unico"])

    def test_um_servidor_ja_desliga_o_atalho(self):
        self.termo.servidores.add(self.servidor_1)

        self.assertFalse(montar_downloads_do_termo(self.termo)["unico"])

    def test_os_rotulos_sao_os_mesmos_do_card(self):
        """O modal e o cartão não podem divergir: os dois saem da mesma montagem."""
        from termos.card_builder import montar_card_de_termo

        termo = self._com_equipe_e_viatura()
        card = montar_card_de_termo(termo, menus_sob_demanda=False)
        dados = montar_downloads_do_termo(termo)

        titulos = [item["titulo"] for item in dados["itens"]]
        self.assertIn(card["viatura_row"]["name"], titulos)
        for servidor in card["servidores"]:
            self.assertIn(servidor["name"], titulos)
