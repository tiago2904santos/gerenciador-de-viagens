"""Testes dos services internos do app protocolos (modo mock)."""

from __future__ import annotations

from django.test import TestCase

from oficios.models import Oficio
from protocolos import services
from protocolos.models import (
    Protocolo,
    ProtocoloAssinatura,
    ProtocoloLog,
    ProtocoloPendencia,
    ProtocoloTramitacao,
)
from protocolos.models import mascarar_cpf


class MascararCpfTests(TestCase):
    def test_mascara_cpf_valido(self):
        self.assertEqual(mascarar_cpf("11144477735"), "111.***.***-35")

    def test_cpf_incompleto_inalterado(self):
        self.assertEqual(mascarar_cpf("123"), "123")


class CriacaoProtocoloTests(TestCase):
    def setUp(self):
        self.oficio = Oficio.objects.create(numero=10, ano=2026, assunto="Viagem a Curitiba")

    def test_criar_a_partir_de_documento_mock(self):
        protocolo = services.criar_protocolo_a_partir_de_documento(self.oficio)
        self.assertTrue(protocolo.numero)  # número mock atribuído
        self.assertEqual(protocolo.status_local, Protocolo.STATUS_CRIADO)
        self.assertTrue(protocolo.modo_mock)
        self.assertEqual(protocolo.origem_object, self.oficio)
        # movimentação + log registrados
        self.assertTrue(protocolo.movimentacoes.exists())
        self.assertTrue(ProtocoloLog.objects.filter(protocolo=protocolo, acao="criar_protocolo").exists())

    def test_vincular_manual(self):
        protocolo = services.vincular_protocolo_manual("24.123.456-7", assunto="Externo")
        self.assertEqual(protocolo.numero, "24.123.456-7")
        self.assertEqual(protocolo.origem_tipo, Protocolo.ORIGEM_MANUAL)
        self.assertEqual(protocolo.status_local, Protocolo.STATUS_CRIADO)

    def test_vincular_manual_com_documento_marca_origem_interna(self):
        protocolo = services.vincular_protocolo_manual("24.1.1-1", documento=self.oficio)
        self.assertEqual(protocolo.origem_tipo, Protocolo.ORIGEM_INTERNA)
        self.assertEqual(protocolo.origem_object, self.oficio)

    def test_numero_unico_quando_preenchido(self):
        services.vincular_protocolo_manual("24.999.999-9")
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Protocolo.objects.create(numero="24.999.999-9")

    def test_gerar_payload_usa_mapper_do_oficio(self):
        protocolo = services.criar_protocolo_a_partir_de_documento(self.oficio, criar_no_eprotocolo=False)
        payload = services.gerar_payload_protocolo(protocolo)
        self.assertEqual(payload["tipoOrigem"], "OFICIO")
        self.assertEqual(payload["numeroDocumento"], 10)


class DocumentoTests(TestCase):
    def setUp(self):
        self.protocolo = services.vincular_protocolo_manual("24.5.5-5")

    def test_anexar_documento_registra_md5_e_tamanho(self):
        conteudo = b"%PDF-1.4 conteudo"
        doc = services.anexar_documento(
            self.protocolo, tipo="ANEXO", nome_arquivo="anexo.pdf", conteudo=conteudo,
        )
        self.assertEqual(doc.tamanho_bytes, len(conteudo))
        self.assertEqual(len(doc.md5), 32)
        self.protocolo.refresh_from_db()
        self.assertEqual(self.protocolo.status_local, Protocolo.STATUS_DOCUMENTOS_ENVIADOS)


class AssinaturaTramitacaoTests(TestCase):
    def setUp(self):
        self.protocolo = services.vincular_protocolo_manual("24.6.6-6")

    def test_solicitar_assinatura(self):
        assinatura = services.solicitar_assinatura_documento(
            self.protocolo, documento=None, cpf="111.444.777-35", nome="Fulano",
        )
        self.assertEqual(assinatura.cpf_assinante, "11144477735")
        self.assertEqual(assinatura.status, ProtocoloAssinatura.STATUS_PENDENTE)
        self.assertTrue(ProtocoloPendencia.objects.filter(protocolo=self.protocolo, tipo="ASSINATURA").exists())
        self.protocolo.refresh_from_db()
        self.assertEqual(self.protocolo.status_local, Protocolo.STATUS_AGUARDANDO_ASSINATURA)

    def test_tramitar(self):
        tram = services.tramitar(self.protocolo, "0002", parecer="Encaminhado", nome_local_para="Setor B")
        self.assertIsInstance(tram, ProtocoloTramitacao)
        self.protocolo.refresh_from_db()
        self.assertEqual(self.protocolo.cod_local_atual, "0002")
        self.assertEqual(self.protocolo.status_local, Protocolo.STATUS_EM_TRAMITACAO)


class SincronizacaoTests(TestCase):
    def setUp(self):
        self.protocolo = services.vincular_protocolo_manual("24.7.7-7")

    def test_sincronizar_atualiza_situacao_e_data(self):
        services.sincronizar_protocolo(self.protocolo)
        self.protocolo.refresh_from_db()
        self.assertIsNotNone(self.protocolo.ultima_sincronizacao_em)
        self.assertEqual(self.protocolo.situacao_eprotocolo, "EM_TRAMITACAO")
        # movimentações do mock importadas
        self.assertTrue(self.protocolo.movimentacoes.exists())

    def test_sincronizar_ativos(self):
        ok, falhas = services.sincronizar_protocolos_ativos()
        self.assertGreaterEqual(ok, 1)
        self.assertEqual(falhas, 0)


class LogTests(TestCase):
    def test_log_nao_contem_dados_sensiveis(self):
        protocolo = services.vincular_protocolo_manual("24.8.8-8")
        services.registrar_log(
            protocolo, "teste",
            request_payload={"Authorization": "Bearer x", "client_secret": "s", "ok": "v"},
        )
        log = ProtocoloLog.objects.filter(protocolo=protocolo, acao="teste").first()
        self.assertEqual(log.request_payload["Authorization"], "***")
        self.assertEqual(log.request_payload["client_secret"], "***")
        self.assertEqual(log.request_payload["ok"], "v")
