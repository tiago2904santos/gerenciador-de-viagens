from datetime import date
from datetime import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.models import RelatorioTecnico
from prestacoes_contas.services import build_relatorio_tecnico_context
from roteiros.models import Roteiro


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

        self.assertEqual(
            set(PrestacaoContas.objects.filter(oficio=oficio).values_list("servidor_id", flat=True)),
            {self.servidor_a.pk, self.servidor_b.pk},
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
        prestacao = PrestacaoContas.objects.get(oficio=oficio, servidor=self.servidor_a)

        response = self.client.get(reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="R$100,00"')

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

        self.assertEqual(
            set(PrestacaoContas.objects.filter(oficio=oficio).values_list("servidor_id", flat=True)),
            {self.servidor_a.pk, self.servidor_b.pk},
        )


class RelatorioTecnicoDocumentoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_rt_doc", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(nome="Servidor RT", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(numero=7, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio, servidor=self.servidor)
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
        cfg.divisao = "DIVISAO POLICIAL"
        cfg.unidade = "UNIDADE TESTE"
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

    @mock.patch("prestacoes_contas.views.gerar_relatorio_tecnico_pdf", return_value=b"%PDF-1.4\n%%EOF\n")
    def test_download_pdf_do_rt(self, _mock_pdf):
        response = self.client.get(
            reverse("prestacoes_contas:rt_download_formato", args=[self.relatorio.pk, "pdf"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(".pdf", response["Content-Disposition"])

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
