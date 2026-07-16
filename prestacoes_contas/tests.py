from datetime import date
from datetime import datetime
from decimal import Decimal
import json
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.models import Unidade
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio
from prestacoes_contas.forms import RelatorioTecnicoForm
from prestacoes_contas.models import DiarioBordo
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.models import PrestacaoDocumentoAnexo
from prestacoes_contas.models import RelatorioTecnico
from prestacoes_contas.services import build_relatorio_tecnico_context
from roteiros.models import Roteiro
from roteiros.models import RoteiroTrecho


class PrestacaoContasSignalsTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor_a = Servidor.objects.create(nome="Servidor A", cargo=self.cargo, cpf="11122233344")
        self.servidor_b = Servidor.objects.create(nome="Servidor B", cargo=self.cargo, cpf="55566677788")

    def test_cria_prestacao_para_cada_servidor_adicionado_ao_oficio(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            protocolo="123456789",
            status=Oficio.STATUS_RASCUNHO,
        )

        oficio.servidores.add(self.servidor_a, self.servidor_b)

        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        self.assertEqual(
            set(prestacao.servidores_prestacao.values_list("servidor_id", flat=True)),
            {self.servidor_a.pk, self.servidor_b.pk},
        )

    def test_remover_servidor_do_oficio_remove_da_prestacao(self):
        """Servidor retirado do ofício não deve continuar na prestação.

        Regressão: o wizard semeia a equipe do ofício anterior do evento; se o
        usuário troca os servidores, os semeados não podem sobrar na prestação
        (era o que misturava equipes entre ofícios do mesmo evento).
        """
        oficio = Oficio.objects.create(
            numero=3,
            ano=2026,
            protocolo="111222333",
            status=Oficio.STATUS_RASCUNHO,
        )
        oficio.servidores.add(self.servidor_a, self.servidor_b)

        oficio.servidores.remove(self.servidor_a)

        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        self.assertEqual(
            set(prestacao.servidores_prestacao.values_list("servidor_id", flat=True)),
            {self.servidor_b.pk},
        )

    def test_set_servidores_reconcilia_equipe_da_prestacao(self):
        """``.set()`` (usado pelo ModelForm) deve deixar a prestação idêntica à equipe."""
        oficio = Oficio.objects.create(
            numero=4,
            ano=2026,
            protocolo="444555666",
            status=Oficio.STATUS_RASCUNHO,
        )
        oficio.servidores.add(self.servidor_a, self.servidor_b)

        # Substitui a equipe inteira, como faz o form ao salvar o ofício.
        oficio.servidores.set([self.servidor_b])

        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        self.assertEqual(
            set(prestacao.servidores_prestacao.values_list("servidor_id", flat=True)),
            {self.servidor_b.pk},
        )


class RelatorioTecnicoDiariaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_prestacao", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor_a = Servidor.objects.create(nome="Servidor A", cargo=self.cargo, cpf="11122233344")
        self.servidor_b = Servidor.objects.create(nome="Servidor B", cargo=self.cargo, cpf="55566677788")

    def test_diaria_inicial_e_valor_por_servidor_da_prestacao(self):
        roteiro = Roteiro.objects.create(valor_diarias=Decimal("200.00"))
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            protocolo="123456789",
            roteiro=roteiro,
        )
        oficio.servidores.add(self.servidor_a, self.servidor_b)
        prestacao = PrestacaoContas.objects.get(oficio=oficio)

        response = self.client.get(reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="R$100,00"')
        relatorio = RelatorioTecnico.objects.get(prestacao=prestacao)
        self.assertEqual(relatorio.diaria, "R$100,00")
        self.assertEqual(relatorio.translado, "Não houve")
        self.assertEqual(relatorio.combustivel, "Cartão Prime")
        self.assertEqual(relatorio.passagem, "Não houve")

    def test_salvar_oficio_sincroniza_prestacoes_para_equipe_existente(self):
        oficio = Oficio.objects.create(
            numero=2,
            ano=2026,
            protocolo="987654321",
            status=Oficio.STATUS_RASCUNHO,
        )
        oficio.servidores.add(self.servidor_a, self.servidor_b)
        PrestacaoContas.objects.filter(oficio=oficio).delete()

        oficio.assunto = "Atualizacao"
        oficio.save(update_fields=["assunto", "updated_at"])

        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        self.assertEqual(
            set(prestacao.servidores_prestacao.values_list("servidor_id", flat=True)),
            {self.servidor_a.pk, self.servidor_b.pk},
        )


class PrestacaoServidorDiariaOverrideTests(TestCase):
    """Sobrescrita da diária de um único servidor (ex.: saque em vez de transferência)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_diaria_override", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor_a = Servidor.objects.create(nome="Servidor A", cargo=self.cargo, cpf="11122233344")
        self.servidor_b = Servidor.objects.create(nome="Servidor B", cargo=self.cargo, cpf="55566677788")
        self.oficio = Oficio.objects.create(numero=9, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor_a, self.servidor_b)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.relatorio = RelatorioTecnico.objects.create(
            prestacao=self.prestacao,
            diaria="R$100,00",
            translado="Não houve",
            combustivel="Cartão Prime",
            passagem="Não houve",
        )
        self.ps_a = self.prestacao.servidores_prestacao.get(servidor=self.servidor_a)
        self.ps_b = self.prestacao.servidores_prestacao.get(servidor=self.servidor_b)

    def test_contexto_usa_valor_padrao_quando_nao_ha_override(self):
        contexto = build_relatorio_tecnico_context(self.relatorio, self.ps_a)
        self.assertEqual(contexto["diaria"], "R$100,00")

    def test_contexto_usa_override_apenas_do_servidor_ajustado(self):
        self.ps_b.diaria_valor_override = "R$80,00"
        self.ps_b.save(update_fields=["diaria_valor_override"])

        self.assertEqual(build_relatorio_tecnico_context(self.relatorio, self.ps_a)["diaria"], "R$100,00")
        self.assertEqual(build_relatorio_tecnico_context(self.relatorio, self.ps_b)["diaria"], "R$80,00")

    def test_rt_criar_get_mostra_selo_so_no_servidor_com_override(self):
        self.ps_b.diaria_valor_override = "R$80,00"
        self.ps_b.save(update_fields=["diaria_valor_override"])

        response = self.client.get(reverse("prestacoes_contas:rt_criar", args=[self.prestacao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Diária ajustada")
        self.assertContains(response, f'id_ps-{self.ps_b.pk}-diaria_valor_override')
        self.assertContains(response, 'value="R$80,00"')

    def test_rt_autosave_salva_override_de_um_servidor_sem_afetar_o_outro(self):
        field_name = f"ps-{self.ps_b.pk}-diaria_valor_override"
        payload = {
            "object_id": str(self.relatorio.pk),
            "form_id": "",
            "model": "relatorio_tecnico",
            "dirty_fields": [field_name],
            "fields": {field_name: "R$80,00 (saque)"},
            "snapshots": {},
        }

        response = self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[self.relatorio.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.ps_a.refresh_from_db()
        self.ps_b.refresh_from_db()
        self.relatorio.refresh_from_db()
        self.assertEqual(self.ps_b.diaria_valor_override, "R$80,00 (saque)")
        self.assertEqual(self.ps_a.diaria_valor_override, "")
        self.assertEqual(self.relatorio.diaria, "R$100,00")

    def test_rt_criar_post_salva_override_sem_js(self):
        data = {
            "diaria": "R$100,00",
            "translado": "Não houve",
            "combustivel": "Cartão Prime",
            "passagem": "Não houve",
            "motivo": "",
            "atividade": "",
            "conclusao": "",
            "medidas": "",
            "info_complementares": "",
            f"ps-{self.ps_b.pk}-diaria_valor_override": "R$80,00",
        }

        response = self.client.post(
            reverse("prestacoes_contas:rt_criar", args=[self.prestacao.pk]),
            data=data,
        )

        self.assertEqual(response.status_code, 302)
        self.ps_a.refresh_from_db()
        self.ps_b.refresh_from_db()
        self.assertEqual(self.ps_b.diaria_valor_override, "R$80,00")
        self.assertEqual(self.ps_a.diaria_valor_override, "")

    def test_autosave_salva_periodo_de_liberacao_e_saque(self):
        liberacao_name = f"ps-{self.ps_a.pk}-data_liberacao_diarias"
        prazo_name = f"ps-{self.ps_a.pk}-prazo_limite_saque"
        payload = {
            "object_id": str(self.ps_a.pk),
            "form_id": "",
            "model": "prestacao_servidor",
            "dirty_fields": [liberacao_name, prazo_name],
            "fields": {
                liberacao_name: "2026-07-16",
                prazo_name: "2026-07-23",
            },
            "snapshots": {},
        }

        response = self.client.post(
            reverse(
                "prestacoes_contas:prestacao_servidor_solicitacao_autosave",
                args=[self.ps_a.pk],
            ),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.ps_a.refresh_from_db()
        self.assertEqual(self.ps_a.data_liberacao_diarias, date(2026, 7, 16))
        self.assertEqual(self.ps_a.prazo_limite_saque, date(2026, 7, 23))

    def test_post_sem_js_salva_periodo_de_liberacao_e_saque(self):
        response = self.client.post(
            reverse("prestacoes_contas:index"),
            data={
                "action": "save_solicitacoes",
                f"ps-{self.ps_a.pk}-data_liberacao_diarias": "2026-07-16",
                f"ps-{self.ps_a.pk}-prazo_limite_saque": "2026-07-23",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.ps_a.refresh_from_db()
        self.assertEqual(self.ps_a.data_liberacao_diarias, date(2026, 7, 16))
        self.assertEqual(self.ps_a.prazo_limite_saque, date(2026, 7, 23))


class RelatorioTecnicoDocumentoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_rt_doc", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(nome="Servidor RT", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(numero=7, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.relatorio = RelatorioTecnico.objects.create(
            prestacao=self.prestacao,
            diaria="R$100,00",
            translado="Não houve",
            combustivel="Cartão Prime",
            passagem="Não houve",
            atividade="Atividade",
        )

    def test_contexto_preenche_cabecalho_e_rodape_do_template(self):
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.divisao = Unidade.objects.create(nome="DIVISAO POLICIAL")
        cfg.unidade = Unidade.objects.create(nome="UNIDADE TESTE")
        cfg.logradouro = "RUA CENTRAL"
        cfg.numero = "123"
        cfg.bairro = "CENTRO"
        cfg.cidade_endereco = "CURITIBA"
        cfg.uf = "PR"
        cfg.cep = "80000000"
        cfg.telefone = "4133334444"
        cfg.email = "TESTE@PC.PR.GOV.BR"
        cfg.save()

        contexto = build_relatorio_tecnico_context(self.relatorio)

        self.assertEqual(contexto["divisao"], "DIVISAO POLICIAL")
        self.assertEqual(contexto["unidade_cabecalho"], "UNIDADE TESTE")
        self.assertEqual(contexto["assunto_oficio"], "Autorização")
        self.assertEqual(contexto["unidade_rodape"], "Divisao Policial")
        self.assertIn("Rua Central", contexto["endereco"])
        self.assertIn("Curitiba/PR", contexto["endereco"])
        self.assertEqual(contexto["email"], "teste@pc.pr.gov.br")

    def test_data_rt_nao_fica_antes_do_retorno(self):
        roteiro = Roteiro.objects.create(
            retorno_chegada_dt=timezone.make_aware(datetime(2026, 6, 19, 18, 0)),
        )
        self.oficio.roteiro = roteiro
        self.oficio.save(update_fields=["roteiro", "updated_at"])

        with mock.patch("prestacoes_contas.services.timezone.localdate", return_value=date(2026, 6, 18)):
            contexto = build_relatorio_tecnico_context(self.relatorio)

        self.assertEqual(contexto["data_atual_extenso"], "19 de junho de 2026")

    def test_data_rt_usa_hoje_dentro_de_tres_dias_uteis_apos_retorno(self):
        roteiro = Roteiro.objects.create(
            retorno_chegada_dt=timezone.make_aware(datetime(2026, 6, 19, 18, 0)),
        )
        self.oficio.roteiro = roteiro
        self.oficio.save(update_fields=["roteiro", "updated_at"])

        with mock.patch("prestacoes_contas.services.timezone.localdate", return_value=date(2026, 6, 23)):
            contexto = build_relatorio_tecnico_context(self.relatorio)

        self.assertEqual(contexto["data_atual_extenso"], "23 de junho de 2026")

    def test_data_rt_limita_ao_terceiro_dia_util_apos_retorno(self):
        roteiro = Roteiro.objects.create(
            retorno_chegada_dt=timezone.make_aware(datetime(2026, 6, 19, 18, 0)),
        )
        self.oficio.roteiro = roteiro
        self.oficio.save(update_fields=["roteiro", "updated_at"])

        with mock.patch("prestacoes_contas.services.timezone.localdate", return_value=date(2026, 6, 30)):
            contexto = build_relatorio_tecnico_context(self.relatorio)

        self.assertEqual(contexto["data_atual_extenso"], "24 de junho de 2026")

    def test_contexto_rt_usa_padrao_quando_campos_custeio_estao_em_branco(self):
        roteiro = Roteiro.objects.create(valor_diarias=Decimal("210.00"))
        self.oficio.roteiro = roteiro
        self.oficio.save(update_fields=["roteiro", "updated_at"])
        RelatorioTecnico.objects.filter(pk=self.relatorio.pk).update(
            diaria="",
            translado="",
            combustivel="",
            passagem="",
        )
        self.relatorio.refresh_from_db()

        contexto = build_relatorio_tecnico_context(self.relatorio)

        self.assertEqual(contexto["diaria"], "R$210,00")
        self.assertEqual(contexto["translado"], "Não houve")
        self.assertEqual(contexto["combustivel"], "Cartão Prime")
        self.assertEqual(contexto["passagem"], "Não houve")

    @mock.patch("prestacoes_contas.services.gerar_relatorio_tecnico_pdf", return_value=b"%PDF-1.4\n%%EOF\n")
    def test_download_pdf_do_rt(self, _mock_pdf):
        response = self.client.get(
            reverse("prestacoes_contas:rt_download_formato", args=[self.relatorio.pk, "pdf"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(".pdf", response["Content-Disposition"])

    @mock.patch("prestacoes_contas.views.gerar_relatorio_tecnico_docx", return_value=b"docx")
    def test_download_rt_materializa_campos_padrao_antes_de_gerar(self, _mock_docx):
        roteiro = Roteiro.objects.create(valor_diarias=Decimal("210.00"))
        self.oficio.roteiro = roteiro
        self.oficio.save(update_fields=["roteiro", "updated_at"])
        RelatorioTecnico.objects.filter(pk=self.relatorio.pk).update(
            diaria="",
            translado="",
            combustivel="",
            passagem="",
        )

        response = self.client.get(
            reverse("prestacoes_contas:rt_download_formato", args=[self.relatorio.pk, "docx"]),
        )

        self.assertEqual(response.status_code, 200)
        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.diaria, "R$210,00")
        self.assertEqual(self.relatorio.translado, "Não houve")
        self.assertEqual(self.relatorio.combustivel, "Cartão Prime")
        self.assertEqual(self.relatorio.passagem, "Não houve")

    def test_post_do_formulario_pode_solicitar_pdf(self):
        data = {
            "diaria": "R$100,00",
            "translado": "Não houve",
            "combustivel": "Cartão Prime",
            "passagem": "Não houve",
            "motivo": "Motivo",
            "atividade": "Atividade",
            "conclusao": "Conclusão",
            "medidas": "Medidas",
            "info_complementares": "Info",
            "action": "download_pdf",
        }

        response = self.client.post(reverse("prestacoes_contas:rt_criar", args=[self.prestacao.pk]), data=data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("prestacoes_contas:rt_download_formato", args=[self.relatorio.pk, "pdf"]),
        )

    def test_formulario_rt_exibe_opcoes_especificas_para_campos_de_custeio(self):
        form = RelatorioTecnicoForm(instance=self.relatorio)

        self.assertEqual(
            list(form.fields["translado"].choices),
            [("Não houve", "Não houve"), ("__outro__", "Outro")],
        )
        self.assertEqual(
            list(form.fields["combustivel"].choices),
            [("Cartão Prime", "Cartão Prime"), ("__outro__", "Outro")],
        )
        self.assertEqual(
            list(form.fields["passagem"].choices),
            [("Não houve", "Não houve"), ("__outro__", "Outro")],
        )

    def test_index_salva_numero_solicitacao_da_prestacao(self):
        prefix = f"prestacao-{self.prestacao.pk}"
        response = self.client.post(
            reverse("prestacoes_contas:index"),
            data={
                "action": "save_solicitacao",
                "prestacao_id": str(self.prestacao.pk),
                f"{prefix}-numero_solicitacao": "SOL-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.numero_solicitacao, "SOL-123")

    def test_autosave_salva_numero_solicitacao_prefixado_da_lista(self):
        prefix = f"prestacao-{self.prestacao.pk}"
        field_name = f"{prefix}-numero_solicitacao"
        payload = {
            "object_id": str(self.prestacao.pk),
            "form_id": "",
            "model": "prestacao_contas",
            "dirty_fields": [field_name],
            "fields": {field_name: "SOL-AUTO"},
            "snapshots": {},
        }

        response = self.client.post(
            reverse("prestacoes_contas:prestacao_autosave", args=[self.prestacao.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.numero_solicitacao, "SOL-AUTO")

    def test_documentos_salva_numero_e_anexos(self):
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            response = self.client.post(
                reverse("prestacoes_contas:documentos", args=[self.prestacao.pk]),
                data={
                    "numero_solicitacao": "SOL-456",
                    "despacho_arquivos": [
                        SimpleUploadedFile(
                            "despacho.pdf",
                            b"%PDF-1.4\n%%EOF\n",
                            content_type="application/pdf",
                        ),
                        SimpleUploadedFile(
                            "despacho-extra.pdf",
                            b"%PDF-1.4\n%%EOF\n",
                            content_type="application/pdf",
                        ),
                    ],
                    "comprovante_arquivos": [
                        SimpleUploadedFile(
                            "comprovante.png",
                            (
                                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                                b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
                                b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
                                b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA"
                                b"\xe2!\xbc\x00\x00\x00\x00IEND\xaeB`\x82"
                            ),
                            content_type="image/png",
                        ),
                    ],
                    "action": "save_continue",
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("prestacoes_contas:rt_criar", args=[self.prestacao.pk]))
            self.prestacao.refresh_from_db()
            self.assertEqual(self.prestacao.numero_solicitacao, "SOL-456")
            self.assertEqual(
                PrestacaoDocumentoAnexo.objects.filter(
                    prestacao=self.prestacao,
                    tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
                ).count(),
                2,
            )
            self.assertEqual(
                PrestacaoDocumentoAnexo.objects.filter(
                    prestacao=self.prestacao,
                    tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
                ).count(),
                1,
            )

    def test_autosave_documentos_salva_numero_solicitacao(self):
        payload = {
            "object_id": str(self.prestacao.pk),
            "form_id": "",
            "model": "prestacao_contas",
            "dirty_fields": ["numero_solicitacao"],
            "fields": {"numero_solicitacao": "SOL-DOCS"},
            "snapshots": {},
        }

        response = self.client.post(
            reverse("prestacoes_contas:prestacao_autosave", args=[self.prestacao.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.numero_solicitacao, "SOL-DOCS")

    def test_autosave_arquivo_documentos_salva_anexo(self):
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            response = self.client.post(
                reverse("prestacoes_contas:prestacao_arquivo_autosave", args=[self.prestacao.pk]),
                data={
                    "numero_solicitacao": "SOL-FILE",
                    "despacho_arquivos": [
                        SimpleUploadedFile(
                            "despacho.pdf",
                            b"%PDF-1.4\n%%EOF\n",
                            content_type="application/pdf",
                        ),
                        SimpleUploadedFile(
                            "despacho-extra.pdf",
                            b"%PDF-1.4\n%%EOF\n",
                            content_type="application/pdf",
                        ),
                    ],
                },
            )

            self.assertEqual(response.status_code, 200)
            self.prestacao.refresh_from_db()
            self.assertEqual(self.prestacao.numero_solicitacao, "SOL-FILE")
            self.assertEqual(
                PrestacaoDocumentoAnexo.objects.filter(
                    prestacao=self.prestacao,
                    tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
                ).count(),
                2,
            )

    def test_excluir_anexo_documentos(self):
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            anexo = PrestacaoDocumentoAnexo.objects.create(
                prestacao=self.prestacao,
                tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
                arquivo=SimpleUploadedFile(
                    "despacho.pdf",
                    b"%PDF-1.4\n%%EOF\n",
                    content_type="application/pdf",
                ),
                nome_original="despacho.pdf",
            )

            response = self.client.post(
                reverse("prestacoes_contas:prestacao_documento_excluir", args=[self.prestacao.pk, anexo.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

            self.assertEqual(response.status_code, 200)
            self.assertFalse(PrestacaoDocumentoAnexo.objects.filter(pk=anexo.pk).exists())

    def test_autosave_rt_salva_campos_do_relatorio(self):
        payload = {
            "object_id": str(self.relatorio.pk),
            "form_id": "",
            "model": "relatorio_tecnico",
            "dirty_fields": ["atividade", "combustivel_outro"],
            "fields": {
                "atividade": "Atividade autosave",
                "combustivel_outro": "Combustível próprio",
            },
            "snapshots": {},
        }

        response = self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[self.relatorio.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.atividade, "Atividade autosave")
        self.assertEqual(self.relatorio.combustivel, "Combustível próprio")

    def test_autosave_rt_nao_apaga_custeio_com_valor_vazio_de_tela_antiga(self):
        payload = {
            "object_id": str(self.relatorio.pk),
            "form_id": "",
            "model": "relatorio_tecnico",
            "dirty_fields": ["translado", "combustivel", "passagem"],
            "fields": {
                "translado": "",
                "combustivel": "",
                "passagem": "",
            },
            "snapshots": {},
        }

        response = self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[self.relatorio.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.translado, "Não houve")
        self.assertEqual(self.relatorio.combustivel, "Cartão Prime")
        self.assertEqual(self.relatorio.passagem, "Não houve")

    def test_autosave_diario_salva_km_e_abastecimento(self):
        roteiro = Roteiro.objects.create()
        self.oficio.roteiro = roteiro
        self.oficio.save(update_fields=["roteiro", "updated_at"])
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            tipo=RoteiroTrecho.TIPO_IDA,
            ordem=0,
        )
        diario = DiarioBordo.objects.create(prestacao=self.prestacao)
        payload = {
            "object_id": str(diario.pk),
            "form_id": "",
            "model": "diario_bordo",
            "dirty_fields": ["form-0-km_inicial", "form-0-abastecimento"],
            "fields": {
                "form-0-km_inicial": "12.345",
                "form-0-abastecimento": "nao",
            },
            "snapshots": {},
        }

        response = self.client.post(
            reverse("prestacoes_contas:diario_autosave", args=[diario.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        linha = diario.trechos.get()
        self.assertEqual(linha.km_inicial, 12345)
        self.assertFalse(linha.abastecimento)

    def test_numero_solicitacao_preenche_coluna_do_oficio(self):
        self.prestacao.numero_solicitacao = "SOL-789"
        self.prestacao.save(update_fields=["numero_solicitacao", "atualizado_em"])

        contexto = build_oficio_docxtpl_context(self.oficio)

        self.assertEqual(contexto["col_solicitacao"], "SOL-789")

    def test_coluna_solicitacao_preserva_linha_vazia_para_outro_servidor(self):
        servidor_b = Servidor.objects.create(nome="Servidor ZZ", cargo=self.cargo, cpf="22233344455")
        self.oficio.servidores.add(servidor_b)
        self.prestacao.numero_solicitacao = "SOL-789"
        self.prestacao.save(update_fields=["numero_solicitacao", "atualizado_em"])

        contexto = build_oficio_docxtpl_context(self.oficio)

        self.assertEqual(contexto["col_solicitacao"], "SOL-789\n\n\n")

    def test_consolidado_mostra_anexos_documentos_como_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            PrestacaoDocumentoAnexo.objects.create(
                prestacao=self.prestacao,
                tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
                arquivo=SimpleUploadedFile(
                    "despacho.pdf",
                    b"%PDF-1.4\n%%EOF\n",
                    content_type="application/pdf",
                ),
                nome_original="despacho.pdf",
            )
            PrestacaoDocumentoAnexo.objects.create(
                prestacao=self.prestacao,
                tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
                arquivo=SimpleUploadedFile(
                    "comprovante-a.pdf",
                    b"%PDF-1.4\n%%EOF\n",
                    content_type="application/pdf",
                ),
                nome_original="comprovante-a.pdf",
            )
            PrestacaoDocumentoAnexo.objects.create(
                prestacao=self.prestacao,
                tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
                arquivo=SimpleUploadedFile(
                    "comprovante-b.pdf",
                    b"%PDF-1.4\n%%EOF\n",
                    content_type="application/pdf",
                ),
                nome_original="comprovante-b.pdf",
            )

            response = self.client.get(reverse("prestacoes_contas:consolidado", args=[self.prestacao.pk]))

        self.assertEqual(response.status_code, 200)
        itens = response.context["itens_consolidado"]
        self.assertTrue(itens[1]["status"])
        self.assertEqual(itens[1]["value"], "despacho.pdf")
        self.assertTrue(itens[4]["status"])
        self.assertEqual(itens[4]["value"], "2 arquivos anexados")

    @mock.patch("prestacoes_contas.views.gerar_prestacao_consolidado_pdf", return_value=b"%PDF-1.4\n%%EOF\n")
    def test_download_pdf_consolidado(self, _mock_pdf):
        response = self.client.get(reverse("prestacoes_contas:consolidado_download", args=[self.prestacao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(".pdf", response["Content-Disposition"])


class PrestacaoAbasTests(TestCase):
    """Abas (não liberadas/liberadas/arquivados/finalizados) + ações arquivar/finalizar."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_abas", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(nome="Servidor Abas", cargo=self.cargo, cpf="11122233344")

    def _criar_prestacao(self, *, numero=1):
        """Cria um ofício (e, via signal, a prestação) com um servidor vinculado."""
        roteiro = Roteiro.objects.create(saida_dt=timezone.now())
        oficio = Oficio.objects.create(numero=numero, ano=2026, protocolo=f"1000000{numero}", roteiro=roteiro)
        oficio.servidores.add(self.servidor)
        return PrestacaoContas.objects.get(oficio=oficio)

    def _pks(self, aba):
        from prestacoes_contas import selectors

        return set(selectors.listar_prestacoes(aba=aba).values_list("pk", flat=True))

    def _liberar(self, prestacao):
        """Marca a data de liberação das diárias do (único) servidor da prestação."""
        ps = prestacao.servidores_prestacao.get()
        ps.data_liberacao_diarias = timezone.localdate()
        ps.save(update_fields=["data_liberacao_diarias"])

    def test_prestacao_sem_data_liberacao_fica_em_nao_liberadas(self):
        from prestacoes_contas import selectors

        prestacao = self._criar_prestacao(numero=1)

        self.assertIn(prestacao.pk, self._pks(selectors.ABA_NAO_LIBERADAS))
        self.assertNotIn(prestacao.pk, self._pks(selectors.ABA_LIBERADAS))

    def test_prestacao_com_servidor_liberado_move_para_liberadas(self):
        from prestacoes_contas import selectors

        prestacao = self._criar_prestacao(numero=1)
        self._liberar(prestacao)

        self.assertIn(prestacao.pk, self._pks(selectors.ABA_LIBERADAS))
        self.assertNotIn(prestacao.pk, self._pks(selectors.ABA_NAO_LIBERADAS))

    def test_arquivar_move_para_aba_arquivados(self):
        from prestacoes_contas import selectors

        prestacao = self._criar_prestacao()

        response = self.client.post(
            reverse("prestacoes_contas:prestacao_arquivar", args=[prestacao.pk]),
            data={"next": "/prestacoes-contas/?aba=nao_liberadas"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/prestacoes-contas/?aba=nao_liberadas")
        prestacao.refresh_from_db()
        self.assertTrue(prestacao.arquivada)
        self.assertIsNotNone(prestacao.arquivada_em)
        self.assertNotIn(prestacao.pk, self._pks(selectors.ABA_NAO_LIBERADAS))
        self.assertIn(prestacao.pk, self._pks(selectors.ABA_ARQUIVADOS))

        # Segundo POST desarquiva (toggle).
        self.client.post(reverse("prestacoes_contas:prestacao_arquivar", args=[prestacao.pk]))
        prestacao.refresh_from_db()
        self.assertFalse(prestacao.arquivada)
        self.assertIsNone(prestacao.arquivada_em)
        self.assertIn(prestacao.pk, self._pks(selectors.ABA_NAO_LIBERADAS))

    def test_finalizar_tem_precedencia_sobre_arquivada(self):
        from prestacoes_contas import selectors

        prestacao = self._criar_prestacao()
        prestacao.definir_arquivada(True)

        self.client.post(reverse("prestacoes_contas:prestacao_finalizar", args=[prestacao.pk]))

        prestacao.refresh_from_db()
        self.assertTrue(prestacao.finalizada)
        # Finalizada aparece só em "Finalizados", mesmo estando arquivada.
        self.assertIn(prestacao.pk, self._pks(selectors.ABA_FINALIZADOS))
        self.assertNotIn(prestacao.pk, self._pks(selectors.ABA_ARQUIVADOS))
        self.assertNotIn(prestacao.pk, self._pks(selectors.ABA_NAO_LIBERADAS))

    def test_contagem_por_aba(self):
        from prestacoes_contas import selectors

        p_nao_lib = self._criar_prestacao(numero=1)
        p_lib = self._criar_prestacao(numero=2)
        self._liberar(p_lib)
        p_arq = self._criar_prestacao(numero=3)
        p_arq.definir_arquivada(True)
        p_fin = self._criar_prestacao(numero=4)
        p_fin.definir_finalizada(True)

        contagem = selectors.contar_por_aba()
        self.assertEqual(contagem[selectors.ABA_NAO_LIBERADAS], 1)
        self.assertEqual(contagem[selectors.ABA_LIBERADAS], 1)
        self.assertEqual(contagem[selectors.ABA_ARQUIVADOS], 1)
        self.assertEqual(contagem[selectors.ABA_FINALIZADOS], 1)
        self.assertIn(p_nao_lib.pk, self._pks(selectors.ABA_NAO_LIBERADAS))
