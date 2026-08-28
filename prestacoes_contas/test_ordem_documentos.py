"""A ordem canônica dos cinco documentos da prestação.

`NOVO-20260828-185303-995fcc0f4b5c`. A ordem é **ofício, despacho, RT, DB,
comprovante** — a mesma em que a etapa Documentos já desenha os cartões
(`_docs_despacho_body.html` e `_docs_anexos_servidor_body.html`). Quatro outros
lugares tinham cada um a sua, e um quinto herdava a ordem que o navegador
mandasse na query string.

Estes testes travam a ordem em todos eles ao mesmo tempo, porque o defeito não
era nenhuma das listas isoladamente: era não haver uma só.
"""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Servidor
from core.testing import area_de_teste
from core.testing import vincular_area
from oficios.models import Oficio

from .download_services import ORDEM_DOCUMENTOS
from .download_services import compilar_download
from .download_services import payload_downloads
from .models import DiarioBordo
from .models import PrestacaoContas
from .models import PrestacaoDocumentoAnexo


def _pdf(nome):
    return SimpleUploadedFile(nome, b"%PDF-1.4\n%%EOF", content_type="application/pdf")


class OrdemDosDocumentosTests(TestCase):
    """A ordem que o dono do sistema pediu, nos cinco pontos que a decidem."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_ordem_docs", password="123456"
        )
        self.client.force_login(self.user)
        vincular_area(self.user)
        area = area_de_teste()
        self.servidor = Servidor.objects.create(area=area, nome="Servidor Um")
        self.oficio = Oficio.objects.create(area=area, numero=1, ano=2026)
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.ps = self.prestacao.servidores_prestacao.get(servidor=self.servidor)
        DiarioBordo.objects.create(prestacao=self.prestacao)
        # Os cinco tipos anexados, para que nenhum item seja omitido por falta de
        # arquivo — é a ordem que está sob teste, não a disponibilidade.
        for tipo, individual in (
            (PrestacaoDocumentoAnexo.TIPO_OFICIO_ASSINADO, False),
            (PrestacaoDocumentoAnexo.TIPO_DESPACHO, False),
            (PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO, True),
            (PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO, False),
            (PrestacaoDocumentoAnexo.TIPO_COMPROVANTE, True),
        ):
            PrestacaoDocumentoAnexo.objects.create(
                prestacao=self.prestacao,
                servidor_prestacao=self.ps if individual else None,
                tipo=tipo,
                arquivo=_pdf(f"{tipo}.pdf"),
                nome_original=f"{tipo}.pdf",
            )

    def test_a_ordem_canonica_e_oficio_despacho_rt_db_comprovante(self):
        self.assertEqual(
            list(ORDEM_DOCUMENTOS),
            ["oficio", "despacho", "rt", "diario", "comprovante"],
        )

    def test_o_seletor_de_download_lista_na_ordem_canonica(self):
        payload = payload_downloads(self.ps)

        self.assertEqual(
            [item["id"] for item in payload["itens"]],
            ["oficio", "despacho", "rt", "diario", "comprovante"],
        )

    def test_o_pdf_juntado_dos_assinados_ignora_a_ordem_da_query_string(self):
        """Quem escolhe a ordem é o sistema, não a ordem de clique no modal.

        O parâmetro `itens` chega na ordem em que o JS montou as caixas; antes
        ela ia direto para o `_merge_pdf_parts` e o PDF saía embaralhado.
        """
        with mock.patch(
            "prestacoes_contas.download_services._merge_pdf_parts",
            side_effect=lambda partes: partes,
        ) as merge:
            compilar_download(
                self.ps,
                origem="assinado",
                formato="pdf",
                escolhidos=["comprovante", "diario", "oficio", "rt", "despacho"],
            )

        self.assertEqual(
            [item_id for item_id, _ in merge.call_args.args[0]],
            ["oficio", "despacho", "rt", "diario", "comprovante"],
        )

    def test_o_pdf_juntado_dos_originais_poe_o_rt_antes_do_diario(self):
        """Despacho e comprovante não têm original — a ordem relativa é a mesma."""
        with mock.patch(
            "prestacoes_contas.download_services._merge_pdf_parts",
            side_effect=lambda partes: partes,
        ) as merge, mock.patch(
            "prestacoes_contas.download_services.gerar_oficio_prestacao_documento",
            return_value=b"oficio",
        ), mock.patch(
            "prestacoes_contas.download_services.gerar_diario_bordo_pdf",
            return_value=b"diario",
        ), mock.patch(
            "prestacoes_contas.download_services.gerar_relatorio_tecnico_pdf",
            return_value=b"rt",
        ):
            compilar_download(
                self.ps,
                origem="original",
                formato="pdf",
                escolhidos=["diario", "rt", "oficio"],
            )

        self.assertEqual(
            [rotulo for rotulo, _ in merge.call_args.args[0]],
            ["ofício", "relatório técnico", "diário de bordo"],
        )

    def test_os_botoes_do_modal_de_anexo_seguem_a_ordem_nas_duas_telas(self):
        """Etapa Documentos e cartão da lista abrem o MESMO modal.

        Cada uma montava a lista por conta própria e as duas discordavam entre
        si e da tela: a etapa abria pelo despacho, o cartão punha o DB antes do
        RT. Como o modal é um só, a pessoa via a ordem mudar conforme o lugar de
        onde abriu.
        """
        from .presenters import apresentar_prestacao_servidor_card

        card = apresentar_prestacao_servidor_card(self.ps)
        self.assertEqual(
            [kind["key"] for kind in json.loads(card["attach_kinds_json"])],
            ["oficio", "despacho", "rt", "diario", "comprovante"],
        )

        response = self.client.get(
            reverse("prestacoes_contas:documentos_servidor", args=[self.ps.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [kind["key"] for kind in response.context["attach_kinds"]],
            ["oficio", "despacho", "rt", "diario", "comprovante"],
        )

    def test_o_wizard_preenche_na_mesma_ordem_em_que_o_pacote_entrega(self):
        """RT (Etapa 1) antes do Diário (Etapa 2), como os documentos saem.

        Em 28/08/2026 as etapas foram invertidas para diário → RT
        (`90ccdee`, `NOVO-20260828-101500-3c7a5d19e4b2`) pelo argumento de que o
        pacote final já montava assim e o wizard era o único fora de linha. A
        observação sobre o código estava certa e a conclusão invertida: com a
        ordem canônica definida, quem estava errado era o pacote. Este teste
        prende os dois lados juntos para não haver uma terceira rodada.
        """
        from .view_common import _build_prestacao_steps

        etapas = _build_prestacao_steps(self.ps, "rt")

        self.assertEqual(
            [(etapa["step_label"], etapa["title"]) for etapa in etapas],
            [
                ("Etapa 1", "Relatório Técnico"),
                ("Etapa 2", "Diário de Bordo"),
                ("Etapa 3", "Documentos"),
                ("Etapa 4", "PDF Final"),
            ],
        )
        # O par RT/DB do wizard é o MESMO par da ordem canônica dos documentos.
        canonica = [item for item in ORDEM_DOCUMENTOS if item in {"rt", "diario"}]
        self.assertEqual(canonica, ["rt", "diario"])

    def test_o_modal_reordena_sozinho_o_que_a_tela_passar_fora_de_ordem(self):
        """A constante só é fonte única se quem monta a lista não decidir a ordem.

        Antes, cada tela montava a sequência à mão e as duas discordavam entre
        si — contra o MESMO modal. Agora `kinds_de_anexo_assinado` ordena, então
        mudar `ORDEM_DOCUMENTOS` move os botões junto com o pacote e o seletor.
        """
        from .presenters import kinds_de_anexo_assinado

        info = {
            "anexar_url": "/anexar/",
            "nome_original": "",
            "view_url": "",
            "remover_url": "",
        }
        embaralhado = [
            ("comprovante", "Comprovante", "o comprovante", info),
            ("diario", "DB", "o diário", info),
            ("oficio", "Ofício", "o ofício", info),
            ("rt", "RT", "o relatório", info),
            ("despacho", "Despacho", "o despacho", info),
        ]

        self.assertEqual(
            [kind["key"] for kind in kinds_de_anexo_assinado(embaralhado)],
            list(ORDEM_DOCUMENTOS),
        )

    def test_documento_fora_da_constante_e_erro_de_programacao(self):
        """Um sexto documento entra na constante primeiro, não no fim da lista."""
        from .presenters import kinds_de_anexo_assinado

        with self.assertRaises(ValueError) as erro:
            kinds_de_anexo_assinado([("parecer", "Parecer", "o parecer", {})])

        self.assertIn("parecer", str(erro.exception))
