import hashlib
from datetime import date
from unittest.mock import ANY, patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from googleapiclient.errors import HttpError

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from eventos.models import TipoEvento
from oficios.models import Oficio
from integracoes.google_drive import naming, organizer, services
from integracoes.google_drive.models import DriveArquivo


def _http_404():
    import httplib2

    resp = httplib2.Response({"status": 404})
    return HttpError(resp, b'{"error": {"message": "File not found"}}')


def _http_403_sem_permissao():
    import httplib2

    resp = httplib2.Response({"status": 403})
    return HttpError(
        resp,
        b'{"error": {"errors": [{"reason": "insufficientFilePermissions", '
        b'"message": "The user does not have sufficient permissions for this file."}]}}',
    )


def _pdf(name):
    raw = b"%PDF-1.4\n%%EOF\n" + name.encode()
    return ContentFile(raw, name=name), hashlib.sha256(raw).hexdigest()


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class OrganizerTests(TestCase):
    def setUp(self):
        services._reset_client()
        self.cargo = Cargo.objects.create(nome="Investigador")
        self.ana = Servidor.objects.create(nome="Ana", cargo=self.cargo, cpf="12345678901")
        self.bruno = Servidor.objects.create(nome="Bruno", cargo=self.cargo, cpf="98765432100")
        self.evento = Evento.objects.create(
            destino_cidade="Maringá",
            destino_uf="PR",
            data_inicio=date(2026, 7, 22),
            data_fim=date(2026, 7, 23),
        )
        self.evento.tipos.add(TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0])
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=self.evento,
        )
        self.oficio.servidores.add(self.ana, self.bruno)

    def _artefato(self, tipo, servidor=None, name="doc.pdf"):
        arquivo, digest = _pdf(name)
        return DocumentoArtefato.objects.create(
            tipo=tipo, formato="pdf", oficio=self.oficio, servidor=servidor,
            hash_sha256=digest, arquivo=arquivo,
        )

    def test_artefato_oficio_recebe_nome_bonito(self):
        art = self._artefato("oficio", name="oficio_feio_123.pdf")
        result = organizer.organizar_artefato(art)
        self.assertIsNotNone(result)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(
            reg.nome, "Ofício 01-2026 protocolo 12.345.678-9 Ana e Bruno (Maringá).pdf"
        )

    def test_termo_usa_servidor_do_artefato(self):
        art = self._artefato("termo_autorizacao", servidor=self.ana, name="termo.pdf")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(
            reg.nome, "Termo de autorização 01-2026 protocolo 12.345.678-9 Ana (Maringá).pdf"
        )

    def test_idempotente_nao_duplica(self):
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        organizer.organizar_artefato(art)
        self.assertEqual(DriveArquivo.objects.filter(artefato=art).count(), 1)

    def test_recria_quando_arquivo_proprio_foi_apagado_no_drive(self):
        """Se o file_id salvo não existe mais no Drive (404), reenviar em vez
        de travar a sincronização inteira (bug real: 46 pendências e
        "Reorganizar" não enviando nada)."""
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        reg.mock = False
        reg.save()

        client = services.get_client()
        with patch.object(client, "mover_renomear", side_effect=_http_404()):
            resultado = organizer.organizar_artefato(art)

        self.assertIsNotNone(resultado)
        reg.refresh_from_db()
        self.assertTrue(reg.file_id)

    def test_recria_quando_sem_permissao_no_arquivo_proprio(self):
        """403 insufficientFilePermissions (arquivo existe, mas a conta
        conectada não pode mais mexer nele — visto em produção ao mover
        arquivos entre pastas após reconexão/mudança de permissão) deve
        recriar, igual ao 404."""
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        reg.mock = False
        reg.save()

        client = services.get_client()
        with patch.object(client, "mover_renomear", side_effect=_http_403_sem_permissao()):
            resultado = organizer.organizar_artefato(art)

        self.assertIsNotNone(resultado)
        reg.refresh_from_db()
        self.assertTrue(reg.file_id)

    def test_outros_403_continuam_propagando(self):
        """Só insufficientFilePermissions vira "recriar" — outro motivo de 403
        (ex.: limite de taxa) não deve ser mascarado como se fosse um problema
        de arquivo perdido."""
        import httplib2

        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        reg.mock = False
        reg.save()

        resp = httplib2.Response({"status": 403})
        erro_limite = HttpError(
            resp, b'{"error": {"errors": [{"reason": "rateLimitExceeded"}]}}'
        )
        client = services.get_client()
        with patch.object(client, "mover_renomear", side_effect=erro_limite):
            with self.assertRaises(HttpError):
                organizer.organizar_artefato(art)

    def test_recria_quando_arquivo_anterior_foi_apagado_no_drive(self):
        """Editar/regerar um documento cujo arquivo anterior sumiu do Drive
        (404 ao sobrescrever) deve criar um novo em vez de falhar."""
        anterior = self._artefato("oficio", name="oficio_v1.pdf")
        organizer.organizar_artefato(anterior)
        reg_anterior = DriveArquivo.objects.get(artefato=anterior)
        reg_anterior.mock = False
        reg_anterior.save()

        novo = self._artefato("oficio", name="oficio_v2.pdf")
        client = services.get_client()
        with patch.object(client, "atualizar_conteudo", side_effect=_http_404()):
            resultado = organizer.organizar_artefato(novo)

        self.assertIsNotNone(resultado)
        self.assertTrue(DriveArquivo.objects.filter(artefato=novo).exists())

    def test_colocar_arquivo_externo_recria_quando_apagado_no_drive(self):
        """Mesmo bug de test_recria_quando_arquivo_proprio_foi_apagado_no_drive,
        mas na rota de arquivos externos (EventoAnexo, PrestacaoContas, etc.):
        um 404 ao sobrescrever o file_id salvo travava a organização do evento
        inteiro em vez de reenviar."""
        from eventos.models import EventoAnexo
        from integracoes.google_drive.models import DriveArquivoExterno

        arquivo, _digest = _pdf("convite.pdf")
        anexo = EventoAnexo.objects.create(
            evento=self.evento, tipo=EventoAnexo.TIPO_CONVITE, arquivo=arquivo,
        )

        resultado = organizer.colocar_arquivo_externo(
            anexo, anexo.arquivo, campo="arquivo", pasta_id="pasta-1", nome="convite.pdf",
        )
        self.assertIsNotNone(resultado)
        reg = DriveArquivoExterno.objects.get(content_type__model="eventoanexo", object_id=anexo.pk, campo="arquivo")
        reg.mock = False
        reg.save()

        client = services.get_client()
        with patch.object(client, "atualizar_conteudo", side_effect=_http_404()):
            resultado = organizer.colocar_arquivo_externo(
                anexo, anexo.arquivo, campo="arquivo", pasta_id="pasta-1", nome="convite.pdf",
            )

        self.assertIsNotNone(resultado)
        reg.refresh_from_db()
        self.assertTrue(reg.file_id)

    def test_nome_os_usa_dados_da_propria_os(self):
        """O nome do arquivo da OS vem da própria OrdemServico (número, destino,
        período, servidores) — não do ofício "âncora": uma OS pode cobrir
        vários ofícios com destino/período/participantes diferentes dela."""
        from cadastros.models import Cidade, Estado
        from integracoes.google_drive import naming
        from ordens_servico.models import OrdemServico

        estado = Estado.objects.create(nome="Paraná", sigla="PR")
        cidade = Cidade.objects.create(nome="Rio Branco do Sul", uf="PR", estado=estado)
        ordem = OrdemServico.objects.create(
            numero=4, ano=2026,
            data_evento_inicio=date(2026, 7, 17), data_evento_fim=date(2026, 7, 17),
        )
        ordem.destinos.add(cidade)
        ordem.servidores.add(self.ana, self.bruno)

        nome = naming.nome_os(ordem)
        self.assertEqual(
            nome,
            "Ordem de Serviço 004-2026 - Rio Branco do Sul-PR - 17 de julho de 2026 - Ana e Bruno.pdf",
        )

    def test_organizar_oficio_limpa_pendencia_apos_sucesso(self):
        """organizar_oficio (usado por "Reorganizar tudo") passava batido pelo
        DriveSyncStatus: um artefato que tinha falhado antes (pendência
        registrada pelo caminho do signal) e agora sobe com sucesso via
        Reorganizar continuava aparecendo pra sempre no painel de pendências,
        porque só o caminho signal/Celery chamava status.registrar_sucesso."""
        from integracoes.google_drive import status
        from integracoes.google_drive.models import DriveSyncStatus

        art = self._artefato("oficio")
        status.registrar_falha(art, RuntimeError("Drive fora do ar (simulado)"))
        self.assertEqual(DriveSyncStatus.objects.count(), 1)

        organizer.organizar_oficio(self.oficio)

        self.assertEqual(DriveSyncStatus.objects.count(), 0)

    def test_planejar_oficio_monta_arvore(self):
        """O CANÔNICO (arquivo real) fica sempre direto na pasta global do tipo
        (sem subpasta), tenha evento ou não — dentro de Eventos/ existe
        apenas um atalho."""
        self._artefato("oficio")
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertIn(
            "Ofícios/Ofício 01-2026 protocolo 12.345.678-9 Ana e Bruno (Maringá).pdf",
            linhas,
        )

    def test_os_e_plano_canonicos_ficam_na_pasta_global_do_tipo(self):
        """OS e plano: o CANÔNICO vive em Ordens de serviço/Planos de trabalho
        (pasta global) — dentro do evento existe só um atalho, no nível do
        evento (não dentro da pasta do ofício)."""
        art_os = self._artefato("ordem_servico", name="os.pdf")
        art_plano = self._artefato("plano_trabalho", name="plano.pdf")
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertTrue(any(l.startswith("Ordens de serviço/") for l in linhas), linhas)
        self.assertTrue(any(l.startswith("Planos de trabalho/") for l in linhas), linhas)

        organizer.organizar_artefato(art_os)
        reg_os = DriveArquivo.objects.get(artefato=art_os)
        self.assertTrue(reg_os.atalho_id)
        client = services.get_client()
        pasta_evento_id = organizer._pasta_evento_folder(client, self.evento)
        self.assertEqual(reg_os.atalho_pasta_id, pasta_evento_id)

    def test_nome_da_os_sempre_recalcula_mesmo_com_nome_drive_antigo_salvo(self):
        """Bug real visto em produção: OS geradas antes do novo formato de nome
        ficavam com o nome antigo (derivado do ofício, com "protocolo X") pra
        sempre — organizar_artefato reusava o nome_drive já salvo em vez de
        recalcular, e "Reorganizar" nunca corrigia."""
        from ordens_servico.models import OrdemServico

        ordem = OrdemServico.objects.create(
            numero=7, ano=2026,
            data_evento_inicio=date(2026, 7, 21), data_evento_fim=date(2026, 7, 27),
        )
        ordem.oficios.add(self.oficio)
        ordem.servidores.add(self.ana, self.bruno)

        art = self._artefato("ordem_servico", name="os.pdf")
        art.nome_drive = "Ordem de serviço 086-2026 protocolo 26.174.695-6 Ana e Bruno (Ivaiporã).pdf"
        art.save(update_fields=["nome_drive"])

        organizer.organizar_artefato(art)

        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(reg.nome, naming.nome_os(ordem))
        self.assertNotIn("protocolo", reg.nome)

    def test_oficio_sem_evento_vai_para_pasta_de_tipo(self):
        self.oficio.evento = None
        self.oficio.save()
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertTrue(any(linha.startswith("Ofícios/") for linha in linhas))
        self.assertFalse(any("Avulsos" in linha for linha in linhas))


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class CancelamentoTests(TestCase):
    """Evento/documento cancelado: pasta do evento vai pra "Eventos cancelados/",
    nota com o motivo, e "(cancelado)" no nome de cada documento."""

    def setUp(self):
        services._reset_client()
        self.cargo = Cargo.objects.create(nome="Investigador")
        self.ana = Servidor.objects.create(nome="Ana", cargo=self.cargo, cpf="12345678901")
        self.evento = Evento.objects.create(
            destino_cidade="Maringá", destino_uf="PR",
            data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 23),
        )
        self.evento.tipos.add(TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0])
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=self.evento,
        )
        self.oficio.servidores.add(self.ana)

    def _artefato(self, tipo, name="doc.pdf"):
        arquivo, digest = _pdf(name)
        return DocumentoArtefato.objects.create(
            tipo=tipo, formato="pdf", oficio=self.oficio, hash_sha256=digest, arquivo=arquivo,
        )

    def _cancelar_evento(self, motivo="Chuva forte"):
        """Seta os campos de cancelamento via queryset.update() — evita passar
        por Evento.save(), que agora dispara o signal (organização em thread
        de verdade) e causa "database is locked" contra a transação do teste."""
        from django.utils import timezone

        Evento.objects.filter(pk=self.evento.pk).update(
            status=Evento.STATUS_CANCELADO, motivo_cancelamento=motivo, cancelado_em=timezone.now()
        )
        self.evento.refresh_from_db()

    def test_pasta_evento_ativo_fica_em_eventos(self):
        client = services.get_client()
        resultado = organizer._pasta_evento_folder(client, self.evento)
        pai = client.get_or_create_pasta(naming.PASTA_EVENTOS, None)
        esperado = client.get_or_create_pasta(naming.pasta_evento(self.evento), pai)
        self.assertEqual(resultado, esperado)

    def test_pasta_evento_cancelado_vai_para_eventos_cancelados(self):
        self._cancelar_evento()
        client = services.get_client()
        resultado = organizer._pasta_evento_folder(client, self.evento)
        pai = client.get_or_create_pasta(naming.PASTA_EVENTOS_CANCELADOS, None)
        esperado = client.get_or_create_pasta(naming.pasta_evento(self.evento), pai)
        self.assertEqual(resultado, esperado)

    def test_pasta_evento_cancelado_ja_existente_em_eventos_e_movida(self):
        """Evento cancelado depois de já ter sido organizado antes: a pasta que
        já existe em "Eventos/" é MOVIDA pra "Eventos cancelados/", não
        duplicada."""
        client = services.get_client()
        self._cancelar_evento()
        with patch.object(client, "buscar_pasta_por_nome", return_value="pasta-antiga-id") as m_buscar, \
                patch.object(client, "mover_renomear") as m_mover:
            resultado = organizer._pasta_evento_folder(client, self.evento)

        m_buscar.assert_called_once()
        pai_cancelados = client.get_or_create_pasta(naming.PASTA_EVENTOS_CANCELADOS, None)
        m_mover.assert_called_once_with("pasta-antiga-id", naming.pasta_evento(self.evento), pai_cancelados)
        self.assertEqual(resultado, "pasta-antiga-id")

    def test_organizar_artefato_com_oficio_cancelado_ganha_sufixo(self):
        art = self._artefato("oficio")
        self.oficio.cancelado = True
        self.oficio.save(update_fields=["cancelado"])

        organizer.organizar_artefato(art)

        reg = DriveArquivo.objects.get(artefato=art)
        self.assertTrue(reg.nome.endswith(" (cancelado).pdf"), reg.nome)

    def test_organizar_artefato_sem_cancelamento_nao_ganha_sufixo(self):
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertNotIn("cancelado", reg.nome)

    def test_organizar_motivo_cancelamento_grava_nota(self):
        from django.contrib.contenttypes.models import ContentType

        from integracoes.google_drive.models import DriveArquivoExterno

        self._cancelar_evento("Chuva forte demais")
        organizer.organizar_motivo_cancelamento(self.evento)

        ct = ContentType.objects.get_for_model(Evento)
        reg = DriveArquivoExterno.objects.get(
            content_type=ct, object_id=self.evento.pk, campo="motivo_cancelamento"
        )
        self.assertEqual(reg.nome, naming.NOME_MOTIVO_CANCELAMENTO)

    def test_organizar_motivo_cancelamento_noop_se_nao_cancelado(self):
        from integracoes.google_drive.models import DriveArquivoExterno

        organizer.organizar_motivo_cancelamento(self.evento)
        self.assertEqual(DriveArquivoExterno.objects.count(), 0)


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class SincronizarPastaEventoTests(TestCase):
    """A pasta do evento só deve existir no Drive depois que a Etapa 1 tiver
    dados suficientes (evita criar uma pasta genérica "Evento" antes disso);
    e alterações posteriores (ex.: mudar a data) devem renomear a pasta já
    existente em vez de criar uma duplicata."""

    def setUp(self):
        services._reset_client()

    def _evento_completo(self, **overrides):
        dados = dict(
            titulo="PCPR na Comunidade",
            destino_cidade="Londrina",
            destino_uf="PR",
            data_inicio=date(2026, 7, 3),
            data_fim=date(2026, 7, 3),
        )
        dados.update(overrides)
        return Evento.objects.create(**dados)

    def test_sincronizar_pasta_evento_nao_cria_pasta_sem_dados_essenciais(self):
        evento = Evento.objects.create()
        self.assertEqual(evento.status, Evento.STATUS_RASCUNHO)

        with patch(
            "integracoes.google_drive.services._MockClient.get_or_create_pasta"
        ) as mock_create:
            organizer.sincronizar_pasta_evento(evento)

        mock_create.assert_not_called()
        evento.refresh_from_db()
        self.assertEqual(evento.drive_folder_id, "")

    def test_sincronizar_pasta_evento_cria_pasta_com_dados_completos(self):
        # ``_evento_completo`` já dispara o signal (post_save) de verdade; zera
        # ``drive_folder_id`` pra testar isoladamente o caminho "ainda sem pasta".
        evento = self._evento_completo()
        Evento.objects.filter(pk=evento.pk).update(drive_folder_id="")
        evento.refresh_from_db()
        nome_pasta = naming.pasta_evento(evento)

        with patch(
            "integracoes.google_drive.services._MockClient.get_or_create_pasta"
        ) as mock_create:
            mock_create.return_value = "mock-pasta-id"
            organizer.sincronizar_pasta_evento(evento)

        mock_create.assert_any_call(nome_pasta, "mock-pasta-id")
        evento.refresh_from_db()
        self.assertEqual(evento.drive_folder_id, "mock-pasta-id")

    def test_sincronizar_pasta_evento_renomeia_pasta_existente_ao_mudar_dados(self):
        evento = self._evento_completo()
        evento.refresh_from_db()
        pasta_id_original = evento.drive_folder_id
        self.assertTrue(pasta_id_original)

        evento.data_inicio = date(2026, 7, 4)
        evento.data_fim = date(2026, 7, 4)
        evento.save()
        novo_nome = naming.pasta_evento(evento)

        with patch(
            "integracoes.google_drive.services._MockClient.mover_renomear"
        ) as mock_renomear, patch(
            "integracoes.google_drive.services._MockClient.get_or_create_pasta"
        ) as mock_create:
            mock_renomear.return_value = pasta_id_original
            mock_create.return_value = "mock-pasta-eventos-pai"
            organizer.sincronizar_pasta_evento(evento)

        # Renomeia a pasta já existente (mesmo id) — nunca cria uma pasta nova
        # com o nome do evento (só o "Eventos/" pai, se ainda não resolvido).
        mock_renomear.assert_any_call(pasta_id_original, novo_nome, "mock-pasta-eventos-pai")
        for chamada in mock_create.call_args_list:
            self.assertNotEqual(chamada.args[0], novo_nome)
        evento.refresh_from_db()
        self.assertEqual(evento.drive_folder_id, pasta_id_original)

    def test_evento_ao_salvar_sincroniza_pasta_automaticamente(self):
        """Ponta a ponta: criar o Evento (post_save) já com dados da Etapa 1
        cria a pasta, sem precisar de nenhum ofício/documento."""
        with patch(
            "integracoes.google_drive.services._MockClient.get_or_create_pasta"
        ) as mock_create:
            mock_create.return_value = "mock-pasta-id"
            evento = self._evento_completo()

        nome_pasta = naming.pasta_evento(evento)
        mock_create.assert_any_call(nome_pasta, "mock-pasta-id")

    def test_evento_ao_salvar_nao_cria_pasta_sem_dados_da_etapa_1(self):
        with patch(
            "integracoes.google_drive.services._MockClient.get_or_create_pasta"
        ) as mock_create:
            Evento.objects.create()
        mock_create.assert_not_called()

    def test_evento_ao_salvar_nao_cria_pasta_com_drive_desligado(self):
        with override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": False}):
            with patch(
                "integracoes.google_drive.services._MockClient.get_or_create_pasta"
            ) as mock_create:
                self._evento_completo()
            mock_create.assert_not_called()
