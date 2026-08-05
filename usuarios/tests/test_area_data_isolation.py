from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from ordens_servico.models import OrdemServico
from oficios.models import Oficio
from planos_trabalho.models import PlanoTrabalho
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro
from termos.models import TermoAutorizacao
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class AreaDataIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.ascom = AreaTrabalho.objects.create(nome="Assessoria de Comunicacao Social", sigla="ASCOM")
        self.dpcap = AreaTrabalho.objects.create(nome="DPCAP", sigla="DPCAP")
        self.user_ascom = User.objects.create_user(username="ascom", password="x")
        VinculoUsuarioArea.objects.create(usuario=self.user_ascom, area=self.ascom, area_padrao=True)
        self.client.force_login(self.user_ascom)

    def test_eventos_index_filtra_area_do_usuario(self):
        # A lista abre na aba "atuais", que e relativa a hoje. Com data fixa o
        # teste passava ate a data virar passado e entao acusava vazamento de
        # area onde so havia calendario andando — foi o que aconteceu com
        # 2026-08-01. Ancorar no presente mantem a afirmacao sobre area.
        proximo = timezone.localdate() + timedelta(days=7)
        Evento.objects.create(area=self.ascom, titulo="Evento ASCOM", data_inicio=proximo)
        Evento.objects.create(area=self.dpcap, titulo="Evento DPCAP", data_inicio=proximo)

        response = self.client.get(reverse("eventos:index"))

        self.assertContains(response, "Evento ASCOM")
        self.assertNotContains(response, "Evento DPCAP")

    def test_evento_de_outra_area_retorna_404(self):
        evento = Evento.objects.create(area=self.dpcap, titulo="Evento DPCAP")

        response = self.client.get(reverse("eventos:detalhe", args=[evento.pk]))

        self.assertEqual(response.status_code, 404)

    def test_oficios_index_filtra_area_do_usuario(self):
        Oficio.objects.create(area=self.ascom, numero=7, ano=2026, assunto="Oficio ASCOM")
        Oficio.objects.create(area=self.dpcap, numero=8, ano=2026, assunto="Oficio DPCAP")

        response = self.client.get(f"{reverse('oficios:index')}?aba=atuais")

        self.assertContains(response, "07/2026")
        self.assertNotContains(response, "08/2026")

    def test_oficio_de_outra_area_retorna_404(self):
        oficio = Oficio.objects.create(area=self.dpcap, numero=1, ano=2026, assunto="Oficio DPCAP")

        response = self.client.get(reverse("oficios:detalhe", args=[oficio.pk]))

        self.assertEqual(response.status_code, 404)

    def test_servidores_index_filtra_area_do_usuario(self):
        Servidor.objects.create(area=self.ascom, nome="Servidor ASCOM")
        Servidor.objects.create(area=self.dpcap, nome="Servidor DPCAP")

        response = self.client.get(reverse("cadastros:servidores_index"))

        self.assertContains(response, "SERVIDOR ASCOM")
        self.assertNotContains(response, "SERVIDOR DPCAP")

    def test_servidor_de_outra_area_retorna_404(self):
        servidor = Servidor.objects.create(area=self.dpcap, nome="Servidor DPCAP")

        response = self.client.get(reverse("cadastros:servidor_update", args=[servidor.pk]))

        self.assertEqual(response.status_code, 404)

    def test_servidor_criado_recebe_area_do_usuario(self):
        response = self.client.post(reverse("cadastros:servidor_create"), {"nome": "Servidor Novo"})

        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor = Servidor.objects.get(nome="SERVIDOR NOVO")
        self.assertEqual(servidor.area, self.ascom)

    def test_servidor_pode_repetir_nome_em_areas_diferentes(self):
        Servidor.objects.create(area=self.ascom, nome="Servidor Compartilhado")
        Servidor.objects.create(area=self.dpcap, nome="Servidor Compartilhado")

        self.assertEqual(Servidor.objects.filter(nome="SERVIDOR COMPARTILHADO").count(), 2)

    def test_unidades_index_filtra_area_do_usuario(self):
        Unidade.objects.create(area=self.ascom, nome="Unidade ASCOM", sigla="AS")
        Unidade.objects.create(area=self.dpcap, nome="Unidade DPCAP", sigla="DP")

        response = self.client.get(reverse("cadastros:unidades_index"))

        self.assertContains(response, "UNIDADE ASCOM")
        self.assertNotContains(response, "UNIDADE DPCAP")

    def test_unidade_de_outra_area_retorna_404(self):
        unidade = Unidade.objects.create(area=self.dpcap, nome="Unidade DPCAP", sigla="DP")

        response = self.client.get(reverse("cadastros:unidade_update", args=[unidade.pk]))

        self.assertEqual(response.status_code, 404)

    def test_unidade_criada_recebe_area_do_usuario(self):
        response = self.client.post(
            reverse("cadastros:unidade_create"),
            {"nome": "Unidade Nova", "sigla": "UN"},
        )

        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        unidade = Unidade.objects.get(nome="UNIDADE NOVA")
        self.assertEqual(unidade.area, self.ascom)

    def test_cargos_index_filtra_area_do_usuario(self):
        Cargo.objects.create(area=self.ascom, nome="Cargo ASCOM")
        Cargo.objects.create(area=self.dpcap, nome="Cargo DPCAP")

        response = self.client.get(reverse("cadastros:cargos_index"))

        self.assertContains(response, "CARGO ASCOM")
        self.assertNotContains(response, "CARGO DPCAP")

    def test_cargo_de_outra_area_retorna_404(self):
        cargo = Cargo.objects.create(area=self.dpcap, nome="Cargo DPCAP")

        response = self.client.get(reverse("cadastros:cargo_update", args=[cargo.pk]))

        self.assertEqual(response.status_code, 404)

    def test_cargo_criado_recebe_area_do_usuario(self):
        response = self.client.post(reverse("cadastros:cargo_create"), {"nome": "Cargo Novo"})

        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        cargo = Cargo.objects.get(nome="CARGO NOVO")
        self.assertEqual(cargo.area, self.ascom)

    def test_combustiveis_index_filtra_area_do_usuario(self):
        Combustivel.objects.create(area=self.ascom, nome="Gasolina ASCOM")
        Combustivel.objects.create(area=self.dpcap, nome="Gasolina DPCAP")

        response = self.client.get(reverse("cadastros:combustiveis_index"))

        self.assertContains(response, "GASOLINA ASCOM")
        self.assertNotContains(response, "GASOLINA DPCAP")

    def test_combustivel_de_outra_area_retorna_404(self):
        combustivel = Combustivel.objects.create(area=self.dpcap, nome="Gasolina DPCAP")

        response = self.client.get(reverse("cadastros:combustivel_update", args=[combustivel.pk]))

        self.assertEqual(response.status_code, 404)

    def test_combustivel_criado_recebe_area_do_usuario(self):
        response = self.client.post(reverse("cadastros:combustivel_create"), {"nome": "Gasolina Nova"})

        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        combustivel = Combustivel.objects.get(nome="GASOLINA NOVA")
        self.assertEqual(combustivel.area, self.ascom)

    def test_viaturas_index_filtra_area_do_usuario(self):
        Viatura.objects.create(area=self.ascom, placa="ABC1234")
        Viatura.objects.create(area=self.dpcap, placa="DEF1234")

        response = self.client.get(reverse("cadastros:viaturas_index"))

        self.assertContains(response, "ABC-1234")
        self.assertNotContains(response, "DEF-1234")

    def test_viatura_de_outra_area_retorna_404(self):
        viatura = Viatura.objects.create(area=self.dpcap, placa="DEF1234")

        response = self.client.get(reverse("cadastros:viatura_update", args=[viatura.pk]))

        self.assertEqual(response.status_code, 404)

    def test_viatura_criada_recebe_area_do_usuario(self):
        response = self.client.post(reverse("cadastros:viatura_create"), {"placa": "GHI1234"})

        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura = Viatura.objects.get(placa="GHI1234")
        self.assertEqual(viatura.area, self.ascom)

    def test_artefato_documento_de_outra_area_retorna_404(self):
        artefato = DocumentoArtefato.objects.create(
            area=self.dpcap,
            tipo="teste",
            formato="pdf",
            hash_sha256="a" * 64,
            arquivo=ContentFile(b"%PDF-1.4\n", name="dpcap.pdf"),
        )

        response = self.client.get(reverse("documentos:artefato_pdf_visualizar", args=[artefato.pk]))

        self.assertEqual(response.status_code, 404)

    def test_roteiro_de_outra_area_retorna_404(self):
        roteiro = Roteiro.objects.create(area=self.dpcap, tipo=Roteiro.TIPO_AVULSO)

        response = self.client.get(reverse("roteiros:editar", args=[roteiro.pk]))

        self.assertEqual(response.status_code, 404)

    def test_termo_de_outra_area_retorna_404(self):
        termo = TermoAutorizacao.objects.create(area=self.dpcap)

        response = self.client.get(reverse("termos:editar", args=[termo.pk]))

        self.assertEqual(response.status_code, 404)

    def test_ordem_servico_de_outra_area_retorna_404(self):
        ordem = OrdemServico.objects.create(area=self.dpcap)

        response = self.client.get(reverse("ordens_servico:editar", args=[ordem.pk]))

        self.assertEqual(response.status_code, 404)

    def test_plano_trabalho_de_outra_area_retorna_404(self):
        plano = PlanoTrabalho.objects.create(area=self.dpcap)

        response = self.client.get(reverse("planos_trabalho:editar", args=[plano.pk]))

        self.assertEqual(response.status_code, 404)

    def test_plano_trabalho_criado_recebe_area_do_usuario(self):
        response = self.client.post(reverse("planos_trabalho:novo"))

        plano = PlanoTrabalho.objects.get()
        self.assertRedirects(response, reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]))
        self.assertEqual(plano.area, self.ascom)

    def test_prestacao_contas_de_outra_area_retorna_404(self):
        oficio = Oficio.objects.create(area=self.dpcap, numero=21, ano=2026, assunto="Oficio DPCAP")
        prestacao = PrestacaoContas.objects.get(oficio=oficio)

        response = self.client.get(reverse("prestacoes_contas:documentos", args=[prestacao.pk]))

        self.assertEqual(response.status_code, 404)

    def test_prestacao_contas_herda_area_do_oficio(self):
        oficio = Oficio.objects.create(area=self.ascom, numero=22, ano=2026, assunto="Oficio ASCOM")

        prestacao = PrestacaoContas.objects.get(oficio=oficio)

        self.assertEqual(prestacao.area, self.ascom)
