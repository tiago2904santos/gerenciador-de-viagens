import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Viatura
from oficios.forms import OficioDadosViajantesForm
from oficios.forms import ModeloMotivoOficioForm
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from oficios.services import atualizar_oficio_dados_viajantes
from oficios.services import atualizar_modelo_motivo
from oficios.services import avaliar_oficio_dados_viajantes
from oficios.services import build_oficio_document_payload
from oficios.services import criar_modelo_motivo
from oficios.services import criar_oficio_dados_viajantes
from oficios.services import excluir_modelo_motivo
from oficios.services import get_next_available_numero_oficio
from oficios.services import redirect_para_corrigir_documento_oficio
from oficios.services import validar_oficio_para_documento
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino


class OficioServicesTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="Analista")
        self.servidor = Servidor.objects.create(nome="Servidor Um", cargo=self.cargo, cpf="12345678901")
        self.viatura = Viatura.objects.create(placa="ABC1234", modelo="Viatura 1")
        self.modelo = ModeloMotivoOficio.objects.create(nome="PADRAO SERVICO", texto="Texto padrão")

    def test_criar_oficio_dados_viajantes_salva_m2m_e_status(self):
        form = OficioDadosViajantesForm(
            data={
                "protocolo": "12.345.678-9",
                "modelo_motivo": str(self.modelo.pk),
                "motivo": "Motivo",
                "servidores": [str(self.servidor.pk)],
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        oficio = criar_oficio_dados_viajantes(form, action="save_draft")
        self.assertEqual(oficio.protocolo, "123456789")
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, timezone.localdate().year)
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)
        self.assertEqual(list(oficio.servidores.all()), [self.servidor])

    def test_get_next_available_numero_reaproveita_menor_lacuna(self):
        ano = timezone.localdate().year
        primeiro = Oficio.objects.create(numero=1, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        Oficio.objects.create(numero=2, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        primeiro.delete()
        self.assertEqual(get_next_available_numero_oficio(ano), 1)

    def test_atualizar_oficio_dados_viajantes_preserva_transporte_data_e_numero(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            status=Oficio.STATUS_RASCUNHO,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
            viatura=self.viatura,
            motorista=self.servidor,
        )
        data_original = oficio.data_criacao
        oficio.servidores.add(self.servidor)
        form = OficioDadosViajantesForm(
            data={
                "protocolo": "12.345.678-4",
                "motivo": "Motivo novo",
                "servidores": [str(self.servidor.pk)],
                "custeio": Oficio.CUSTEIO_ONUS_LIMITADO,
                "custeio_observacao": "",
            },
            instance=oficio,
        )
        self.assertTrue(form.is_valid(), form.errors)
        atualizado = atualizar_oficio_dados_viajantes(oficio, form, action="save_continue")
        atualizado.refresh_from_db()
        self.assertEqual(atualizado.numero, 1)
        self.assertEqual(atualizado.ano, 2026)
        self.assertEqual(atualizado.data_criacao, data_original)
        self.assertEqual(atualizado.viatura, self.viatura)
        self.assertEqual(atualizado.motorista, self.servidor)
        self.assertEqual(list(atualizado.servidores.all()), [self.servidor])
        self.assertEqual(atualizado.status, Oficio.STATUS_GERADO)

    def test_avaliar_oficio_dados_viajantes_incomplete_e_complete(self):
        incompleto = Oficio.objects.create(custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        avaliacao_incompleta = avaliar_oficio_dados_viajantes(incompleto)
        self.assertEqual(avaliacao_incompleta["status"], "incomplete")
        self.assertIn("Informe o motivo.", avaliacao_incompleta["pendencias"])
        self.assertIn("Selecione ao menos um viajante.", avaliacao_incompleta["pendencias"])

        completo = Oficio.objects.create(motivo="Motivo", custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        completo.servidores.add(self.servidor)
        avaliacao_completa = avaliar_oficio_dados_viajantes(completo)
        self.assertEqual(avaliacao_completa["status"], "complete")
        self.assertEqual(avaliacao_completa["pendencias"], [])

    def test_build_oficio_document_payload_formata_protocolo(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            protocolo="123456789",
            motivo="Motivo",
            status=Oficio.STATUS_RASCUNHO,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        payload = build_oficio_document_payload(oficio)
        self.assertEqual(payload["protocolo"], "12.345.678-9")

    def test_services_modelo_motivo_mantem_padrao_unico(self):
        form_1 = ModeloMotivoOficioForm(data={"nome": "Modelo A", "texto": "A", "ativo": True, "ordem": 1, "is_padrao": True})
        self.assertTrue(form_1.is_valid(), form_1.errors)
        modelo_1 = criar_modelo_motivo(form_1)
        self.assertTrue(modelo_1.is_padrao)

        form_2 = ModeloMotivoOficioForm(data={"nome": "Modelo B", "texto": "B", "ativo": True, "ordem": 2, "is_padrao": True})
        self.assertTrue(form_2.is_valid(), form_2.errors)
        modelo_2 = criar_modelo_motivo(form_2)
        self.assertTrue(modelo_2.is_padrao)
        modelo_1.refresh_from_db()
        self.assertFalse(modelo_1.is_padrao)

        edit_form = ModeloMotivoOficioForm(
            data={"nome": "Modelo A", "texto": "A", "ativo": True, "ordem": 1, "is_padrao": True},
            instance=modelo_1,
        )
        self.assertTrue(edit_form.is_valid(), edit_form.errors)
        atualizar_modelo_motivo(modelo_1, edit_form)
        modelo_1.refresh_from_db()
        modelo_2.refresh_from_db()
        self.assertTrue(modelo_1.is_padrao)
        self.assertFalse(modelo_2.is_padrao)

        excluir_modelo_motivo(modelo_2)
        self.assertFalse(ModeloMotivoOficio.objects.filter(pk=modelo_2.pk).exists())

    def test_validar_bloqueia_sem_roteiro(self):
        ConfiguracaoSistema.get_singleton()
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="M",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
            protocolo="123456789",
            viatura=self.viatura,
            motorista=self.servidor,
            motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
        )
        oficio.servidores.add(self.servidor)
        out = validar_oficio_para_documento(oficio)
        self.assertEqual(out["status"], "incomplete")
        self.assertTrue(any("roteiro" in p.lower() for p in out["pendencias"]))

    def test_redirect_falta_justificativa_vai_etapa_4(self):
        ConfiguracaoSistema.get_singleton()
        est, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "Paraná"})
        cid, _ = Cidade.objects.get_or_create(
            nome="CuritibaDocTest",
            estado=est,
            defaults={"uf": "PR"},
        )
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
            origem_estado=est,
            origem_cidade=cid,
        )
        roteiro.saida_dt = timezone.make_aware(
            datetime.datetime(2026, 5, 12, 8, 0, 0),
            timezone.get_current_timezone(),
        )
        roteiro.save(update_fields=["saida_dt"])
        RoteiroDestino.objects.create(roteiro=roteiro, estado=est, cidade=cid, ordem=0)
        base = datetime.date(2026, 5, 10)
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            data_criacao=base,
            motivo="M",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
            protocolo="123456789",
            roteiro=roteiro,
            viatura=self.viatura,
            motorista=self.servidor,
            motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
        )
        oficio.servidores.add(self.servidor)
        url = redirect_para_corrigir_documento_oficio(oficio)
        self.assertEqual(url, reverse("oficios:wizard_justificativa", args=[oficio.pk]))
