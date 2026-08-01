import datetime
from types import SimpleNamespace
from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Viatura
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from oficios.forms import OficioDadosViajantesForm
from oficios.forms import ModeloMotivoOficioForm
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from oficios.models import OficioNumeroLacuna
from oficios.services import atualizar_oficio_dados_viajantes
from oficios.services import atualizar_modelo_motivo
from oficios.services import avaliar_oficio_dados_viajantes
from oficios.services import build_oficio_document_payload
from oficios.document_generation import get_document_generation_status
from oficios.services import criar_modelo_motivo
from oficios.services import criar_oficio_dados_viajantes
from oficios.services import excluir_modelo_motivo
from oficios.services import excluir_oficio
from oficios.services import get_next_available_numero_oficio
from oficios.services import criar_oficio_rascunho
from oficios.services import OficioNumeroConflitoError
from oficios.services import reservar_numero_oficio
from oficios.services import _preencher_roteiro_oficio_com_evento
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

    @mock.patch("oficios.services._bloquear_escopo_numeracao_oficio")
    @mock.patch(
        "oficios.services.get_next_available_numero_oficio",
        side_effect=[77, 78],
    )
    def test_reserva_repete_apos_colisao_de_worker_antigo(
        self,
        _proximo_numero,
        _bloqueio,
    ):
        ano = timezone.localdate().year
        Oficio.objects.create(
            numero=77,
            ano=ano,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        rascunho = Oficio.objects.create(
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        original_save = rascunho.save
        chamadas = 0

        def save_com_primeira_colisao(*args, **kwargs):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 1:
                raise IntegrityError(
                    'duplicate key violates "oficios_oficio_area_ano_numero_unique"',
                )
            return original_save(*args, **kwargs)

        with mock.patch.object(rascunho, "save", side_effect=save_com_primeira_colisao):
            reservado = reservar_numero_oficio(rascunho, ano=ano)

        self.assertEqual(reservado.numero, 78)
        self.assertEqual(chamadas, 2)

    def test_get_next_available_numero_reaproveita_lacuna_apos_exclusao(self):
        ano = timezone.localdate().year
        primeiro = Oficio.objects.create(numero=1, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        Oficio.objects.create(numero=2, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        excluir_oficio(primeiro)
        self.assertEqual(get_next_available_numero_oficio(ano), 1)

    def test_get_next_available_numero_ignora_numeros_apenas_pulados_manualmente(self):
        # Cria 1..10 e depois "pula" para o 15 manualmente: 11-14 não devem ser
        # sugeridos automaticamente, só o 16 (maior + 1).
        ano = timezone.localdate().year
        for numero in range(1, 11):
            Oficio.objects.create(numero=numero, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        Oficio.objects.create(numero=15, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        self.assertEqual(get_next_available_numero_oficio(ano), 16)

    def test_excluir_oficio_libera_numero_para_reaproveitamento(self):
        ano = timezone.localdate().year
        oficios = [
            Oficio.objects.create(numero=numero, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
            for numero in range(1, 11)
        ]
        excluir_oficio(oficios[6])  # exclui o ofício número 7
        self.assertTrue(OficioNumeroLacuna.objects.filter(ano=ano, numero=7).exists())
        self.assertEqual(get_next_available_numero_oficio(ano), 7)

    def test_editar_numero_nao_libera_numero_antigo_mas_consome_lacuna_do_novo(self):
        # Editar (corrigir) o número de um ofício existente não deve reintroduzir
        # o número antigo como sugestão automática — só a exclusão faz isso.
        ano = timezone.localdate().year
        oficio = Oficio.objects.create(numero=5, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        outro = Oficio.objects.create(numero=8, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        excluir_oficio(outro)  # libera o número 8 como lacuna

        form = OficioDadosViajantesForm(
            data={
                "numero": "8",
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
            instance=oficio,
        )
        self.assertTrue(form.is_valid(), form.errors)
        atualizado = atualizar_oficio_dados_viajantes(oficio, form, action="save_draft")

        self.assertEqual(atualizado.numero, 8)
        self.assertFalse(OficioNumeroLacuna.objects.filter(ano=ano, numero=5).exists())
        self.assertFalse(OficioNumeroLacuna.objects.filter(ano=ano, numero=8).exists())
        # próxima sugestão vai direto para o maior usado + 1, não reaproveita o 5
        self.assertEqual(get_next_available_numero_oficio(ano), 9)

    def test_clean_numero_rejeita_numero_ja_usado_no_ano(self):
        ano = timezone.localdate().year
        Oficio.objects.create(numero=3, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        oficio = Oficio.objects.create(numero=9, ano=ano, custeio=Oficio.CUSTEIO_UNIDADE_DPC)

        form = OficioDadosViajantesForm(
            data={
                "numero": "3",
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
            instance=oficio,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("numero", form.errors)

    def test_servico_rejeita_numero_ocupado_depois_da_validacao(self):
        ano = timezone.localdate().year
        oficio = Oficio.objects.create(
            numero=77,
            ano=ano,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        form = OficioDadosViajantesForm(
            data={
                "numero": "78",
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
            instance=oficio,
        )
        self.assertTrue(form.is_valid(), form.errors)
        Oficio.objects.create(
            numero=78,
            ano=ano,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )

        with self.assertRaises(OficioNumeroConflitoError):
            atualizar_oficio_dados_viajantes(
                oficio,
                form,
                action="save_draft",
            )

    def test_preencher_roteiro_oficio_com_evento_so_preenche_sede_e_destino(self):
        estado = Estado.objects.create(nome="Parana", sigla="PR")
        cidade_sede = Cidade.objects.create(nome="Curitiba", estado=estado, uf="PR")
        cidade_destino = Cidade.objects.create(nome="Londrina", estado=estado, uf="PR")
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = cidade_sede
        config.save()
        evento = Evento.objects.create(
            destino_uf="PR",
            destino_cidade="Londrina",
            data_inicio=datetime.date(2026, 7, 10),
            data_fim=datetime.date(2026, 7, 12),
            horario_inicio=datetime.time(9, 30),
            horario_fim=datetime.time(18, 45),
        )
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)

        _preencher_roteiro_oficio_com_evento(roteiro, evento)
        roteiro.refresh_from_db()

        self.assertEqual(roteiro.origem_cidade_id, cidade_sede.pk)
        self.assertEqual(roteiro.origem_estado_id, estado.pk)
        self.assertTrue(
            roteiro.destinos.filter(estado=estado, cidade=cidade_destino).exists()
        )
        self.assertIsNone(roteiro.saida_dt)
        self.assertIsNone(roteiro.retorno_saida_dt)

    def test_criar_oficio_rascunho_herda_motivo_mas_nao_servidores_ou_viatura(self):
        evento = Evento.objects.create(
            destino_uf="PR",
            destino_cidade="Londrina",
            motivo="Motivo do evento",
        )
        anterior = Oficio.objects.create(evento=evento, custeio=Oficio.CUSTEIO_UNIDADE_DPC, viatura=self.viatura)
        anterior.servidores.add(self.servidor)

        novo = criar_oficio_rascunho(evento=evento)

        self.assertEqual(novo.motivo, "Motivo do evento")
        self.assertIsNone(novo.viatura_id)
        self.assertIsNone(novo.motorista_id)
        self.assertEqual(list(novo.servidores.all()), [])
        self.assertEqual(list(novo.servidores_termo_autorizacao.all()), [])


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

    def test_atualizar_oficio_dados_viajantes_preenche_ano_quando_ausente(self):
        oficio = Oficio.objects.create(
            numero=150,
            ano=None,
            status=Oficio.STATUS_RASCUNHO,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)
        form = OficioDadosViajantesForm(
            data={
                "numero": "150",
                "protocolo": "44.444.444-4",
                "motivo": "Motivo sem ano prévio",
                "servidores": [str(self.servidor.pk)],
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
            instance=oficio,
        )
        self.assertTrue(form.is_valid(), form.errors)

        atualizado = atualizar_oficio_dados_viajantes(oficio, form, action="save_draft")
        atualizado.refresh_from_db()

        self.assertEqual(atualizado.numero, 150)
        self.assertEqual(atualizado.ano, timezone.localdate().year)

    def test_avaliar_oficio_dados_viajantes_incomplete_e_complete(self):
        incompleto = Oficio.objects.create(custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        avaliacao_incompleta = avaliar_oficio_dados_viajantes(incompleto)
        self.assertEqual(avaliacao_incompleta["status"], "incomplete")
        self.assertIn("Informe o motivo.", avaliacao_incompleta["pendencias"])
        self.assertIn("Selecione ao menos um viajante.", avaliacao_incompleta["pendencias"])

        completo = Oficio.objects.create(
            protocolo="12.345.678-9",
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
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

    @override_settings(DOCUMENTOS_ARTIFACT_CACHE=True, DOCUMENTOS_PERSIST_ARTEFATOS=True)
    @mock.patch("oficios.document_generation.get_cached_document_artifact")
    @mock.patch("oficios.document_generation.build_template_cache_signature", return_value="tpl-sig")
    @mock.patch("oficios.document_generation.build_document_cache_key", return_value="cache-key")
    @mock.patch("oficios.document_generation.build_oficio_docxtpl_context", return_value={"ctx": True})
    @mock.patch("oficios.document_generation.build_canonical_document_payload", return_value={"payload": True})
    @mock.patch("oficios.document_generation.resolve_pdf_engine", return_value=SimpleNamespace(attempt_chain=["weasyprint"]))
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    def test_get_document_generation_status_nao_depende_de_arquivo_assinado(
        self,
        _m_validar,
        _m_resolve,
        _m_payload,
        _m_ctx,
        _m_cache_key,
        _m_tpl_sig,
        m_get_cached,
    ):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)
        artefato = DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="pdf",
            oficio=oficio,
            hash_sha256="0" * 64,
            arquivo=ContentFile(b"%PDF-1.4\n%%EOF\n", name="oficio.pdf"),
        )
        m_get_cached.return_value = artefato

        status = get_document_generation_status(oficio)

        self.assertEqual(status["oficio_pdf_signature_status"], "unsigned")
        self.assertEqual(status["oficio_pdf_artefato_id"], str(artefato.pk))
        self.assertTrue(status["oficio_pdf_botoes_assinatura"])

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
