import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DownloadPickerModalTests(SimpleTestCase):
    def test_modal_preserva_shell_e_fechamento_dentro_de_formulario(self):
        """O diálogo saiu de `download_picker.html` mas o contrato é o mesmo.

        `NOVO-20260826-111043-802915c4fd6a` (`PF-07`): o bloco do `<dialog>`
        virou `download_picker_dialogo.html`, um por página em vez de um por
        gatilho. As três garantias que este teste protege — `own_form`, o gancho
        de fechamento e o par dele no JS — continuam valendo, só mudaram de
        arquivo.
        """
        template = (
            Path(settings.BASE_DIR)
            / "templates" / "cotton" / "v2" / "download_picker_dialogo.html"
        ).read_text(encoding="utf-8")
        javascript = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "download-queue.js"
        ).read_text(encoding="utf-8")

        self.assertIn(':own_form="True"', template)
        self.assertIn('hook="data-download-picker-close"', template)
        self.assertIn('[data-download-picker-close]', javascript)
        self.assertIn("window.CV.overlay.closeDialog(dialogo)", javascript)
        self.assertIn('data-download-picker-close-bound', javascript)
        self.assertIn('fechar.addEventListener("click"', javascript)

    def test_gatilho_carrega_o_src_e_o_js_le_dele(self):
        """O que substituiu o `data-src` por diálogo: um `data-src` por gatilho."""
        gatilho = (
            Path(settings.BASE_DIR) / "templates" / "cotton" / "v2" / "download_picker.html"
        ).read_text(encoding="utf-8")
        javascript = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "download-queue.js"
        ).read_text(encoding="utf-8")

        self.assertIn('<span class="download-picker-mount" data-src="{{ src }}">', gatilho)
        self.assertNotIn("<c-v2.modal", gatilho)
        self.assertIn('montagem.getAttribute("data-src")', javascript)
        self.assertIn('document.querySelector("[data-download-picker]")', javascript)

    def test_cabecalho_do_documento_nao_bloqueia_cliques_do_modal(self):
        javascript = (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "pages"
            / "oficios-documentos-inline.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "dialog, [data-overlay-trigger], [data-attach-signed-trigger], "
            "[data-download-picker-trigger]",
            javascript,
        )


class DownloadPickerInventarioTests(SimpleTestCase):
    """Todo gatilho precisa de uma página que inclua o diálogo.

    `NOVO-20260826-111043-802915c4fd6a` (`PF-07`): separar o diálogo do gatilho
    corta 23% do HTML da lista de prestações, mas cria um jeito novo de errar —
    incluir o gatilho numa página que não tem diálogo. O botão renderiza e não
    abre nada; o `download-queue.js` registra erro no console, e é só.

    Este teste é o inventário das duas pontas. Mexer nele é deliberado: quem
    adicionar um gatilho tem de dizer em que página o diálogo entra.
    """

    RAIZ = Path(settings.BASE_DIR) / "templates"

    GATILHOS = {
        "cotton/v2/prestacao_card.html",
        "core/main_preview/acao.html",
        "core/main_preview/lista.html",
        "core/main_preview/modais.html",
        "eventos/partials/_detalhe_termo_linha.html",
        "termos/partials/_preview_body.html",
        "termos/partials/termo_list_card.html",
    }

    PAGINAS_COM_DIALOGO = {
        "core/main_preview.html",
        "eventos/detalhe.html",
        "prestacoes_contas/diario_bordo_form.html",
        "prestacoes_contas/index.html",
        "termos/form.html",
        "termos/index.html",
        "termos/preview.html",
    }

    def _templates_com(self, padrao, excluir=()):
        """Casa `src=` e `:src=`: o valor pode ser literal ou vir do contexto."""
        alvo = re.compile(padrao)
        achados = set()
        for caminho in self.RAIZ.rglob("*.html"):
            relativo = caminho.relative_to(self.RAIZ).as_posix()
            if relativo in excluir:
                continue
            if alvo.search(caminho.read_text(encoding="utf-8")):
                achados.add(relativo)
        return achados

    def test_o_inventario_de_gatilhos_e_o_esperado(self):
        gatilhos = self._templates_com(
            r"<c-v2\.download_picker\s+:?src=",
            excluir=("cotton/v2/download_picker.html", "cotton/v2/download_picker_dialogo.html"),
        )

        self.assertEqual(
            gatilhos,
            self.GATILHOS,
            "gatilho novo ou removido: confira se a PÁGINA dele inclui "
            "<c-v2.download_picker_dialogo />, e atualize este inventário",
        )

    def test_o_inventario_de_paginas_com_dialogo_e_o_esperado(self):
        paginas = self._templates_com(
            r"<c-v2\.download_picker_dialogo />",
            excluir=("cotton/v2/download_picker.html",),
        )

        self.assertEqual(paginas, self.PAGINAS_COM_DIALOGO)

    def test_toda_pagina_do_inventario_estende_um_layout(self):
        """Diálogo em parcial não vale: ele tem de sair uma vez, no nível da página."""
        for relativo in sorted(self.PAGINAS_COM_DIALOGO):
            with self.subTest(pagina=relativo):
                texto = (self.RAIZ / relativo).read_text(encoding="utf-8")
                self.assertIn("{% extends", texto)
                self.assertEqual(texto.count("<c-v2.download_picker_dialogo />"), 1)

