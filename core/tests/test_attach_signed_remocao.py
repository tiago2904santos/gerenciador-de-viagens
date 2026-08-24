"""Remover documento assinado falhava em silêncio — e pior, mentia (NOVO-23).

`attach-signed-modal.js` faz a única chamada AJAX deste modal:
`CV.http.request(currentRemoveUrl, { method: 'POST' })`. Eram dois
buracos no mesmo lugar:

1. **Sem `.catch`.** Falha de rede não removia, não recarregava e não avisava —
   o clique simplesmente não fazia nada. O usuário via o anexo ainda ali e
   concluía que o botão não tinha pegado.
2. **Sem checar o status.** `CV.http.request` devolve o `Response` cru
   (`core/http.js`), e status de erro **não rejeita** a promise: só falha de
   rede rejeita. Então 403 de permissão, 404 e 500 caíam no `.then` de sucesso
   e **recarregavam a página como se o documento tivesse sido removido**. Como
   a view só emite `messages.success` quando de fato remove, o usuário voltava
   para uma tela sem mensagem nenhuma, com o documento assinado ainda no lugar.

O segundo é o grave: silêncio é ruim, mas confirmar uma remoção que não
aconteceu é pior — é o tipo de coisa que só aparece numa auditoria de documento.

A view responde JSON ao autosave, então `response.ok` só é falso quando algo
deu errado de verdade. No sucesso, o componente atualiza o modal localmente:
recarregar a página fecharia o diálogo antes de o usuário anexar o substituto.

O teste é estático porque o projeto não roda JavaScript no CI (`JS-03`). Ele não
substitui a reprodução no navegador — guarda o padrão que a reprodução provou
correto.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


COMPONENTE = (
    Path(settings.BASE_DIR) / "static" / "js" / "components" / "attach-signed-modal.js"
)
MODAL = (
    Path(settings.BASE_DIR)
    / "templates"
    / "cotton"
    / "v2"
    / "attach_signed_modal.html"
)
FILE_PICKER = (
    Path(settings.BASE_DIR) / "templates" / "cotton" / "v2" / "file_picker.html"
)


def _corpo_de(nome: str) -> str:
    """Recorta o corpo de uma função do componente contando chaves."""
    fonte = COMPONENTE.read_text(encoding="utf-8")
    inicio = fonte.index("function %s(" % nome)
    abertura = fonte.index("{", inicio)
    profundidade = 0
    for pos in range(abertura, len(fonte)):
        if fonte[pos] == "{":
            profundidade += 1
        elif fonte[pos] == "}":
            profundidade -= 1
            if profundidade == 0:
                return fonte[abertura : pos + 1]
    raise AssertionError("não achei o fim de %s" % nome)


class RemoverAssinadoNaoMenteTests(SimpleTestCase):
    def test_status_de_erro_nao_passa_por_sucesso(self):
        corpo = _corpo_de("removeCurrentSigned")
        self.assertIn(
            "response.ok",
            corpo,
            "`CV.http.request` devolve o Response cru e status de erro não "
            "rejeita: sem checar `ok`, um 500 recarrega a página como se a "
            "remoção tivesse dado certo",
        )
        self.assertIn("new Error(", corpo)
        # O throw precisa vir ANTES da limpeza, senão um erro apagaria o anexo da UI.
        self.assertRegex(corpo, r"\bthrow\s+\w+;")
        self.assertLess(
            re.search(r"\bthrow\s+\w+;", corpo).start(),
            corpo.index("limparDocumentoPersistidoAtual(removeUrl)"),
            "o `throw` tem que barrar a limpeza local, não vir depois dela",
        )

    def test_falha_de_rede_avisa_na_tela_e_no_log(self):
        corpo = _corpo_de("removeCurrentSigned")
        self.assertIn(".catch(", corpo)
        self.assertIn("mostrarErro(", corpo)
        self.assertIn("window.CV.log.error(", corpo)

        vazios = re.findall(r"\.catch\(function\s*\([^)]*\)\s*\{\s*\}\s*\)", corpo)
        self.assertEqual(
            vazios, [], "catch vazio devolve o silêncio que este ID veio corrigir"
        )

    def test_falha_de_rede_nao_vaza_a_mensagem_crua_do_navegador(self):
        """Medido: sem o marcador, a faixa mostrava `Failed to fetch`.

        Falha de rede e recusa do servidor caem no mesmo `.catch`. Só o texto
        que este arquivo escreve serve para o usuário — o do `fetch` é inglês
        de infraestrutura. É a assimetria que `calculateDiarias` tem hoje no
        editor de roteiros e que não vale copiar.
        """
        corpo = _corpo_de("removeCurrentSigned")
        self.assertIn("paraUsuario", corpo)
        self.assertRegex(
            corpo,
            r"error\s*&&\s*error\.paraUsuario",
            "o `.catch` precisa distinguir o erro que ele mesmo lançou do que "
            "veio do fetch antes de jogar a mensagem na tela",
        )

    def test_a_faixa_de_erro_existe_e_nasce_escondida(self):
        markup = MODAL.read_text(encoding="utf-8")
        self.assertIn("data-attach-signed-error", markup)
        self.assertIn('role="alert"', markup)
        # Design system, não o `alert alert-*` do Bootstrap que o HT-03 vai varrer.
        self.assertIn("notice", markup)

        fonte = COMPONENTE.read_text(encoding="utf-8")
        for contrato in ("function mostrarErro(", "function limparErro("):
            with self.subTest(contrato=contrato):
                self.assertIn(contrato, fonte)

    def test_o_erro_nao_sobrevive_a_reabertura_do_modal(self):
        """Faixa que fica na tela depois de fechar vira erro fantasma."""
        for funcao in ("closeModal", "openModal"):
            with self.subTest(funcao=funcao):
                self.assertIn("limparErro()", _corpo_de(funcao))


class RemocaoContinuaAcontecendoTests(SimpleTestCase):
    """A rede que impede 'consertar' o defeito desligando a remoção."""

    def test_o_post_segue_e_o_modal_e_atualizado_sem_reload(self):
        corpo = _corpo_de("removeCurrentSigned")
        self.assertIn("window.CV.http.request(removeUrl", corpo)
        self.assertIn('method: "POST"', corpo)
        self.assertIn("limparDocumentoPersistidoAtual(removeUrl)", corpo)
        self.assertNotIn("window.location.reload()", corpo)

        limpeza = _corpo_de("limparDocumentoPersistidoAtual")
        self.assertIn("itemAtual.current_attachments", limpeza)
        self.assertIn("anexo.remove_url !== removeUrl", limpeza)
        self.assertIn('data-attach-signed-kinds', limpeza)


class AnexoAtualIntegradoAoPickerTests(SimpleTestCase):
    def test_modal_nao_renderiza_segunda_lista_para_o_anexo_atual(self):
        modal = MODAL.read_text(encoding="utf-8")

        self.assertIn(':current_attachment="True"', modal)
        self.assertNotIn('class="person-list attach-signed__current"', modal)

    def test_acoes_dos_anexos_atuais_moram_na_lista_do_picker(self):
        picker = FILE_PICKER.read_text(encoding="utf-8")

        self.assertIn("data-file-picker-name", picker)
        self.assertIn("data-attach-signed-current-list", picker)
        self.assertIn("data-attach-signed-current-template", picker)
        self.assertIn("data-attach-signed-list-open", picker)
        self.assertIn("data-attach-signed-remove", picker)

    def test_selecao_nova_preserva_a_lista_dos_anexos_atuais(self):
        corpo = _corpo_de("sincronizarDocumentoAtual")

        self.assertIn("fileInput.files.length", corpo)
        self.assertIn("placeholderRow.hidden = mostrarAtual", corpo)
        self.assertIn("renderizarAnexosPersistidos()", corpo)

        renderizacao = _corpo_de("renderizarAnexosPersistidos")
        self.assertIn("documentoAtual.currentAttachments", renderizacao)
        self.assertIn("currentList.hidden = !atuais.length", renderizacao)
