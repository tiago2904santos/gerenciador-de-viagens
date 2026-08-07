"""`NOVO-35` — excluir um servidor no cadastro não pode apagar prova de prestação.

`PrestacaoServidor.servidor` é `on_delete=CASCADE` — o único `CASCADE` entre as
treze FKs que apontam para `Servidor`. Excluir o servidor derrubava as linhas de
prestação dele e, por cascata, o comprovante de saque e a assinatura eletrônica.
Medido antes da correção: 1 anexo → 0.

**A armadilha que este arquivo existe para travar.** A guarda tem de consultar
`PrestacaoServidor.todos`, nunca `servidor.prestacoes_servidor`. O acessor reverso
herda o `_default_manager`, que desde o `DB-06` esconde as linhas com
`removida_em` preenchido — e o invariante do `DB-06` é que linha marcada é
exatamente a que TEM dados. A relação reversa esconde o conjunto que a guarda
existe para achar. Medido: com a reversa, a guarda bloqueia zero.

Por isso `RelacaoReversaEscondeAProvaTests` não testa a correção: testa a
armadilha. Ele fica vermelho se alguém "simplificar" a consulta.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from cadastros.services import CadastroVinculadoError
from cadastros.services import excluir_servidor
from cadastros.services import prestacoes_com_prova_irrefazivel
from oficios.models import Oficio
from prestacoes_contas.models import AssinaturaDocumento
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.models import PrestacaoDocumentoAnexo
from prestacoes_contas.models import PrestacaoServidor
from core.testing import area_de_teste
from core.testing import vincular_area

PDF_MINIMO = b"%PDF-1.4\n%%EOF\n"


class ExclusaoDeServidorBase(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Agente")
        self.alvo = Servidor.objects.create(area=area_de_teste(), 
            nome="Servidor Alvo", cargo=self.cargo, cpf="11122233344",
        )
        self.colega = Servidor.objects.create(area=area_de_teste(), 
            nome="Servidor Colega", cargo=self.cargo, cpf="55566677788",
        )
        for servidor in (self.alvo, self.colega):
            servidor.refresh_from_db()
        self.oficio = Oficio.objects.create(area=area_de_teste(), 
            numero=71, ano=2026, protocolo="717171717", status=Oficio.STATUS_RASCUNHO,
        )
        self.oficio.servidores.add(self.alvo, self.colega)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)

    def _ps(self, servidor):
        return PrestacaoServidor.todos.get(prestacao=self.prestacao, servidor=servidor)

    def _anexar_comprovante(self, ps):
        return PrestacaoDocumentoAnexo.objects.create(
            prestacao=ps.prestacao,
            servidor_prestacao=ps,
            tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
            arquivo=SimpleUploadedFile(
                "comprovante.pdf", PDF_MINIMO, content_type="application/pdf",
            ),
            nome_original="comprovante.pdf",
        )

    def _assinar_rt(self, ps):
        return AssinaturaDocumento.objects.create(
            prestacao=ps.prestacao,
            servidor_prestacao=ps,
            tipo=AssinaturaDocumento.TIPO_RT,
            signer=ps.servidor,
            status=AssinaturaDocumento.STATUS_ASSINADA,
            arquivo_assinado=SimpleUploadedFile(
                "rt.pdf", PDF_MINIMO, content_type="application/pdf",
            ),
        )


class ProvaIrrefazivelBloqueiaTests(ExclusaoDeServidorBase):
    """Cada sinal sozinho — nenhum deles pode passar por causa de outro."""

    def test_comprovante_sozinho_bloqueia(self):
        anexo = self._anexar_comprovante(self._ps(self.alvo))

        with self.assertRaises(CadastroVinculadoError):
            excluir_servidor(self.alvo)

        self.assertTrue(Servidor.all_objects.filter(pk=self.alvo.pk).exists())
        self.assertTrue(PrestacaoDocumentoAnexo.objects.filter(pk=anexo.pk).exists())

    def test_assinatura_sozinha_bloqueia_pela_guarda_nova(self):
        """Este caso já era barrado — mas por outro mecanismo, e com outra mensagem.

        `AssinaturaDocumento.signer` é `on_delete=PROTECT`, então a exclusão já
        estourava `ProtectedError`. Provei por inversão: removendo a guarda, este
        teste continuava verde se ele só verificasse "levantou e o dado ficou".
        Passava dos dois jeitos, e portanto não provava nada — oitava vez nesta
        refatoração.

        O que distingue os dois mecanismos é a **mensagem**: o `PROTECT` produz a
        genérica de `core/deletion.py`, que não diz qual ofício nem o que fazer; a
        guarda produz a específica. Asserção sobre a mensagem é o que torna este
        caso atribuível à correção.
        """
        ps = self._ps(self.alvo)
        assinatura = self._assinar_rt(ps)
        self.assertFalse(ps.documentos_anexos.exists())

        with self.assertRaises(CadastroVinculadoError) as capturado:
            excluir_servidor(self.alvo)

        self.assertIn(self.oficio.numero_formatado, str(capturado.exception))
        self.assertTrue(AssinaturaDocumento.objects.filter(pk=assinatura.pk).exists())

    def test_numero_da_solicitacao_sozinho_bloqueia(self):
        ps = self._ps(self.alvo)
        ps.numero_solicitacao = "2026/000123"
        ps.save(update_fields=["numero_solicitacao", "atualizado_em"])

        with self.assertRaises(CadastroVinculadoError):
            excluir_servidor(self.alvo)

    def test_a_mensagem_diz_o_que_fazer(self):
        self._anexar_comprovante(self._ps(self.alvo))

        with self.assertRaises(CadastroVinculadoError) as capturado:
            excluir_servidor(self.alvo)

        mensagem = str(capturado.exception)
        self.assertIn(self.alvo.nome, mensagem)
        self.assertIn(self.oficio.numero_formatado, mensagem)
        self.assertIn("Remova o servidor da equipe", mensagem)


class SemProvaContinuaExcluindoTests(ExclusaoDeServidorBase):
    """A outra metade da regra, e ela importa tanto quanto a primeira.

    Uma guarda que bloqueasse por vínculo — e não por dado — prenderia todo
    servidor que já tenha entrado em qualquer ofício. No banco de desenvolvimento
    seriam 3 de 4 contra 1 de 4, e os dois de diferença não têm nada a perder.
    """

    def test_servidor_sem_nada_coletado_e_excluido(self):
        excluir_servidor(self.alvo)

        self.assertFalse(Servidor.all_objects.filter(pk=self.alvo.pk).exists())

    def test_status_coletivo_nao_prende_o_servidor(self):
        """`status` é contaminado por ação de terceiro — por isso ficou fora.

        `_marcar_servidores_pendentes` marca TODA a equipe pendente do ofício ao
        salvar um documento compartilhado (despacho, RT, diário). Se o predicado
        olhasse `status`, bastaria um colega salvar o despacho para tornar
        indelével um servidor semeado por engano.
        """
        from prestacoes_contas.view_common import _marcar_servidores_pendentes

        _marcar_servidores_pendentes(self.prestacao)
        ps = self._ps(self.alvo)
        self.assertNotEqual(ps.status, PrestacaoServidor.STATUS_PENDENTE)
        self.assertTrue(ps.tem_dados_coletados(), "o predicado largo já considera coletado")
        self.assertFalse(ps.tem_prova_irrefazivel(), "o estreito, não — é o ponto")

        excluir_servidor(self.alvo)

        self.assertFalse(Servidor.all_objects.filter(pk=self.alvo.pk).exists())


class RelacaoReversaEscondeAProvaTests(ExclusaoDeServidorBase):
    """A armadilha do `DB-06`, travada por teste.

    Não prova a correção — prova por que a consulta é do jeito que é. Se alguém
    trocar `PrestacaoServidor.todos` pela relação reversa, este teste fica
    vermelho antes de o comprovante de alguém sumir em produção.
    """

    def test_a_reversa_nao_ve_a_linha_que_tem_o_comprovante(self):
        ps = self._ps(self.alvo)
        self._anexar_comprovante(ps)
        self.oficio.servidores.set([self.colega])  # `DB-06` marca `removida_em`
        self.alvo.refresh_from_db()

        self.assertEqual(
            self.alvo.prestacoes_servidor.count(), 0,
            "a relação reversa esconde a linha removida — é a armadilha",
        )
        self.assertEqual(PrestacaoServidor.todos.filter(servidor=self.alvo).count(), 1)

    def test_a_guarda_bloqueia_mesmo_com_a_linha_removida_da_equipe(self):
        ps = self._ps(self.alvo)
        anexo = self._anexar_comprovante(ps)
        self.oficio.servidores.set([self.colega])
        self.alvo.refresh_from_db()

        self.assertEqual(len(prestacoes_com_prova_irrefazivel(self.alvo)), 1)
        with self.assertRaises(CadastroVinculadoError):
            excluir_servidor(self.alvo)
        self.assertTrue(PrestacaoDocumentoAnexo.objects.filter(pk=anexo.pk).exists())


class TelaDeExclusaoTests(ExclusaoDeServidorBase):
    """A mensagem tem de chegar à tela — antes ela morria em dois pontos."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="tester_novo35", password="123456",
        )
        self.client.force_login(self.user)
        vincular_area(self.user)

    def test_post_bloqueado_mostra_a_razao_especifica(self):
        self._anexar_comprovante(self._ps(self.alvo))

        resposta = self.client.post(
            reverse("cadastros:servidor_delete", args=[self.alvo.pk]), follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(
            any(self.oficio.numero_formatado in m for m in mensagens),
            f"a razão específica não chegou à tela: {mensagens}",
        )
        self.assertTrue(Servidor.all_objects.filter(pk=self.alvo.pk).exists())

    def test_post_sem_prova_exclui_e_avisa(self):
        resposta = self.client.post(
            reverse("cadastros:servidor_delete", args=[self.alvo.pk]), follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Servidor.all_objects.filter(pk=self.alvo.pk).exists())
