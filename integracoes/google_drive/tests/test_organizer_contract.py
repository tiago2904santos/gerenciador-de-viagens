import hashlib
from datetime import date
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from eventos.models import Evento, TipoEvento
from integracoes.google_drive import naming, organizer, services
from integracoes.google_drive.models import DriveArquivo, DriveArquivoExterno
from oficios.models import Oficio
from core.testing import area_de_teste


class DriveClientDouble(services._MockClient):
    """Double com estado: representa os efeitos públicos do cliente do Drive."""

    def __init__(self):
        self.pastas = {}
        self.arquivos = {}
        self.atalhos = {}
        self.falhar_proximo_upload = False
        self.omitir_url = False

    @staticmethod
    def _id(prefixo, *partes):
        digest = hashlib.sha1("|".join(partes).encode()).hexdigest()[:24]
        return f"{prefixo}_{digest}"

    def get_or_create_pasta(self, nome, pai_id=None):
        chave = (pai_id or "root", nome)
        return self.pastas.setdefault(chave, self._id("folder", *chave))

    def buscar_pasta_por_nome(self, nome, pasta_id):
        return self.pastas.get((pasta_id or "root", nome))

    def upload(self, nome, conteudo, mimetype, pasta_id=None):
        if self.falhar_proximo_upload:
            self.falhar_proximo_upload = False
            raise RuntimeError("indisponibilidade transitória do Drive")
        file_id = self._id("file", pasta_id or "root", nome)
        self.arquivos[file_id] = {
            "nome": nome,
            "conteudo": conteudo,
            "mime_type": mimetype,
            "pasta_id": pasta_id,
        }
        url = (
            ""
            if self.omitir_url
            else f"https://drive.google.com/file/d/{file_id}/view"
        )
        return file_id, url

    def buscar_arquivo_por_nome(self, nome, pasta_id):
        return next(
            (
                file_id
                for file_id, arquivo in self.arquivos.items()
                if arquivo["nome"] == nome and arquivo["pasta_id"] == pasta_id
            ),
            None,
        )

    def atualizar_conteudo(self, file_id, novo_nome, conteudo, mimetype, pasta_id=None):
        self.arquivos[file_id] = {
            "nome": novo_nome,
            "conteudo": conteudo,
            "mime_type": mimetype,
            "pasta_id": pasta_id,
        }
        url = (
            ""
            if self.omitir_url
            else f"https://drive.google.com/file/d/{file_id}/view"
        )
        return file_id, url

    def mover_renomear(self, file_id, novo_nome, nova_pasta_id=None):
        if file_id in self.arquivos:
            self.arquivos[file_id]["nome"] = novo_nome
            self.arquivos[file_id]["pasta_id"] = nova_pasta_id
        else:
            chave_anterior = next(
                (chave for chave, pasta_id in self.pastas.items() if pasta_id == file_id),
                None,
            )
            if chave_anterior:
                del self.pastas[chave_anterior]
                self.pastas[(nova_pasta_id or "root", novo_nome)] = file_id
        return file_id

    def criar_ou_atualizar_atalho(self, nome, target_id, pasta_id, existing_id=None):
        atalho_id = existing_id or self._id("shortcut", pasta_id, nome)
        self.atalhos[atalho_id] = {
            "nome": nome,
            "target_id": target_id,
            "pasta_id": pasta_id,
        }
        return atalho_id


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class OrganizerContractTests(TestCase):
    def setUp(self):
        services._reset_client()
        self.client = DriveClientDouble()
        self.client_patch = patch(
            "integracoes.google_drive.organizer._get_client", return_value=self.client
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

        cargo = Cargo.objects.create(area=area_de_teste(), nome="Investigador")
        servidor = Servidor.objects.create(area=area_de_teste(), 
            nome="Ana Contrato", cargo=cargo, cpf="12345678901"
        )
        self.evento = Evento.objects.create(area=area_de_teste(), 
            titulo="Operação contrato",
            destino_cidade="Maringá",
            destino_uf="PR",
            data_inicio=date(2026, 7, 22),
            data_fim=date(2026, 7, 23),
        )
        self.evento.tipos.add(
            TipoEvento.objects.get_or_create(area=area_de_teste(), nome="PCPR na Comunidade")[0]
        )
        self.oficio = Oficio.objects.create(area=area_de_teste(), 
            numero=17,
            ano=2026,
            protocolo="123456789",
            motivo="Contrato do organizer",
            evento=self.evento,
        )
        self.oficio.servidores.add(servidor)

    def _artefato(self, *, com_arquivo=True):
        dados = {
            "tipo": "oficio",
            "formato": "pdf",
            "oficio": self.oficio,
            "hash_sha256": "a" * 64,
        }
        if com_arquivo:
            dados["arquivo"] = ContentFile(
                b"%PDF-1.4\ncontrato\n%%EOF", name="contrato.pdf"
            )
        return DocumentoArtefato.objects.create(area=area_de_teste(), **dados)

    def test_repetir_operacao_preserva_arquivo_atalho_e_estado_local(self):
        artefato = self._artefato()

        primeiro = organizer.organizar_artefato(artefato)
        segundo = organizer.organizar_artefato(artefato)

        registro = DriveArquivo.objects.get(artefato=artefato)
        self.assertEqual(segundo, primeiro)
        self.assertEqual(DriveArquivo.objects.filter(artefato=artefato).count(), 1)
        self.assertEqual(set(self.client.arquivos), {registro.file_id})
        self.assertEqual(set(self.client.atalhos), {registro.atalho_id})
        self.assertLess(len(registro.file_id), 200)
        self.assertLess(len(registro.atalho_id), 200)

    def test_arvore_e_arquivo_ja_existentes_sao_localizados_sem_duplicacao(self):
        artefato = self._artefato()
        resultado_inicial = organizer.organizar_artefato(artefato)
        DriveArquivo.objects.get(artefato=artefato).delete()

        resultado_recuperado = organizer.organizar_artefato(artefato)

        registro = DriveArquivo.objects.get(artefato=artefato)
        self.assertEqual(resultado_recuperado[0], resultado_inicial[0])
        self.assertEqual(len(self.client.arquivos), 1)
        self.assertIn(registro.atalho_pasta_id, self.client.pastas.values())

    def test_artefato_sem_arquivo_nao_cria_estado_remoto_nem_local(self):
        artefato = self._artefato(com_arquivo=False)

        resultado = organizer.organizar_artefato(artefato)

        self.assertIsNone(resultado)
        self.assertFalse(DriveArquivo.objects.filter(artefato=artefato).exists())
        self.assertEqual(self.client.arquivos, {})
        self.assertEqual(self.client.atalhos, {})

    def test_resposta_sem_url_ainda_persiste_ids_e_metadados_coerentes(self):
        self.client.omitir_url = True
        artefato = self._artefato()

        resultado = organizer.organizar_artefato(artefato)

        registro = DriveArquivo.objects.get(artefato=artefato)
        self.assertEqual(resultado, (registro.file_id, ""))
        self.assertEqual(registro.url, "")
        self.assertEqual(registro.mime_type, "application/pdf")
        self.assertEqual(
            self.client.atalhos[registro.atalho_id]["target_id"], registro.file_id
        )

    def test_falha_transitoria_nao_persiste_registro_incompleto_e_permite_retry(self):
        artefato = self._artefato()
        self.client.falhar_proximo_upload = True

        with self.assertRaisesRegex(RuntimeError, "indisponibilidade transitória"):
            organizer.organizar_artefato(artefato)

        self.assertFalse(DriveArquivo.objects.filter(artefato=artefato).exists())
        self.assertEqual(self.client.arquivos, {})
        resultado = organizer.organizar_artefato(artefato)
        self.assertEqual(resultado[0], DriveArquivo.objects.get(artefato=artefato).file_id)

    def test_renomear_evento_reutiliza_id_persistido_e_nao_deixa_pasta_orfa(self):
        organizer.sincronizar_pasta_evento(self.evento)
        self.evento.refresh_from_db()
        pasta_inicial = self.evento.drive_folder_id
        self.evento.destino_cidade = "Londrina"
        self.evento.save(update_fields=["destino_cidade"])

        organizer.sincronizar_pasta_evento(self.evento)
        self.evento.refresh_from_db()
        pasta_renomeada = self.evento.drive_folder_id

        registros = DriveArquivoExterno.objects.filter(
            object_id=self.evento.pk, campo="pasta_evento"
        )
        self.assertEqual(pasta_renomeada, pasta_inicial)
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.get().file_id, pasta_inicial)
        nomes_evento = [
            nome
            for (_pai, nome), pasta_id in self.client.pastas.items()
            if pasta_id == pasta_inicial
        ]
        self.assertEqual(nomes_evento, [naming.pasta_evento(self.evento)])
