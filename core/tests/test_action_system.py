"""O que restou de `actions/action-system.css` — nada, e é isso que se guarda.

A folha era a camada unificada de ação do sistema antigo: botões (`cv-btn`,
`btn`, `app-btn`, `icon-btn`), grupos, os dois diálogos globais e o menu de
ações. Ao longo de 2026-08-20 cada peça virou componente do v2 com folha
própria, e no dia 20 o último inquilino saiu — o menu do card de prestação, que
era o único lugar do projeto que ainda escrevia `action-menu__item` à mão.

Os testes daqui em diante medem o SUBSTITUTO, não o defunto: as regras vivem em
`static/css/v2/menu.css`, e o contrato do item de menu é o do
`cotton/v2/menu_item.html`.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)


def _sem_comentario(css: str) -> str:
    """O que o navegador enxerga.

    A varredura é sobre SELETOR, não sobre texto: `v2/menu.css` cita o
    `.action-menu` legado no cabeçalho para registrar de onde veio o desenho, e
    esse parágrafo é justamente o tipo de nota que não pode virar falha.
    """
    return COMENTARIO.sub("", css)


class GlobalActionSystemTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR)
        self.menu_css = (
            self.root / "static" / "css" / "v2" / "menu.css"
        ).read_text(encoding="utf-8")

    def test_a_camada_de_acao_do_sistema_antigo_nao_voltou(self):
        """Nem a folha, nem a pasta, nem o vocabulário dela.

        `.cv-btn`, `.btn`, `.app-btn` e `.icon-btn` eram a geometria dos botões
        antigos; `.action-menu__*` era o menu. Hoje o botão é `c-v2.button`, o de
        ícone é `c-v2.icon_button` e o menu é `c-v2.menu` — cada um com folha
        própria.

        A varredura do MENU é sobre todo o CSS de origem, porque o risco não é a
        folha voltar com o mesmo nome: é o vocabulário reaparecer em outra. A dos
        botões ainda não pode ser: cinco folhas citam `.cv-btn` em `:not()` e em
        regra morta (`v2/date-picker.css`, `v2/form-block.css` e três em
        comentário). São restos de guarda contra um botão que não existe mais, e
        saem na varredura seguinte — o que este teste trava por ora é a pasta.
        """
        css_root = self.root / "static" / "css"
        self.assertFalse(
            (css_root / "actions").exists(),
            "a pasta do sistema de ação antigo voltou",
        )
        fontes = [
            arquivo
            for arquivo in css_root.rglob("*.css")
            if "profiles" not in arquivo.parts and ".bundle." not in arquivo.name
        ]
        for arquivo in fontes:
            texto = _sem_comentario(arquivo.read_text(encoding="utf-8"))
            with self.subTest(arquivo=arquivo.name):
                self.assertNotIn(".action-menu", texto)

    def test_o_dialogo_do_sistema_antigo_nao_voltou(self):
        """O diálogo é `<dialog class="modal">` — de template ou montado em JS.

        `delete-confirm-modal*` e `attach-signed-modal*` eram o desenho anterior
        dos dois diálogos globais. Os dois viraram `c-v2.modal` (o de anexar em
        2026-08-16, o de confirmação em 2026-08-20, dentro de `core/app.js`).
        """
        css_root = self.root / "static" / "css"
        for arquivo in css_root.rglob("*.css"):
            if "profiles" in arquivo.parts or ".bundle." in arquivo.name:
                continue
            texto = _sem_comentario(arquivo.read_text(encoding="utf-8"))
            for morta in (".delete-confirm-modal", ".attach-signed-modal"):
                with self.subTest(arquivo=arquivo.name, seletor=morta):
                    self.assertNotIn(morta, texto)

    def test_o_menu_do_v2_tem_as_primitivas_do_menu_rico(self):
        """Cabeçalho de menu não existe mais; o resto do desenho continua.

        O `.action-menu--rich` tinha três peças: a caixa, o cabeçalho e o item
        com descrição. O v2 herdou duas — a caixa e o item —, e o cabeçalho saiu
        em 2026-08-16: o contexto do menu virou `aria-label`, porque repetir o
        nome do registro dentro de um menu aberto A PARTIR dele era dizer duas
        vezes a mesma coisa.
        """
        self.assertIn(".menu {", self.menu_css)
        self.assertIn(".menu__item {", self.menu_css)
        self.assertIn(".menu__description", self.menu_css)

        item = render_to_string(
            "cotton/v2/menu_item.html",
            {
                "href": "/documento.pdf",
                "title": "Baixar PDF",
                "description": "Documento pronto para impressão",
                "icon": "pdf",
                "tone": "pdf",
                "download": True,
            },
        )
        self.assertIn("menu__item", item)
        self.assertIn("Documento pronto para impressão", item)
        self.assertIn("download", item)

    def test_document_action_tones_are_distinct_and_motion_can_be_reduced(self):
        """Quem pinta o tom de cada item de menu agora é o v2, por `data-tone`.

        `.action-menu__item-icon--docx/--preview/--edit` saíram na poda de
        2026-08-20: nenhum template as emitia desde que o menu de ações virou
        `c-v2.menu_item`, que marca o tom num atributo em vez de uma classe por
        formato. Os quatro tons continuam SENDO QUATRO — é isso que este teste
        guarda —, só que medidos onde eles vivem agora.

        A trava de movimento veio junto na mudança de casa: era a única linha da
        folha antiga que ainda alcançava o menu.
        """
        tons = [
            linha
            for linha in self.menu_css.splitlines()
            if ".menu__icon[data-tone=" in linha
        ]
        for tone in ("pdf", "docx", "success", "warning"):
            with self.subTest(tone=tone):
                self.assertTrue(
                    any(f'data-tone="{tone}"' in linha for linha in tons),
                    f"o menu do v2 não pinta o tom {tone}",
                )
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.menu_css)

    def test_menu_item_does_not_require_a_model_pk(self):
        html = render_to_string(
            "cotton/v2/menu_item.html",
            {
                "href": "/termos/7/pdf/",
                "title": "Destino não informado",
                "description": "PDF do termo",
                "icon": "pdf",
            },
        )
        self.assertIn('href="/termos/7/pdf/"', html)
        self.assertIn("Destino não informado", html)

    def test_item_desabilitado_sai_como_span_anunciavel(self):
        """"Diário de bordo — ainda não foi criado" não é um link quebrado.

        O menu do card de prestação lista o diário mesmo quando ele não existe,
        para dizer o que caberia ali. Como `<a>` sem `href` o item sumiria da
        navegação por teclado sem se anunciar como indisponível; como `<span
        role="menuitem" aria-disabled>`, ele é lido pelo que é.
        """
        html = render_to_string(
            "cotton/v2/menu_item.html",
            {
                "title": "Diário de bordo",
                "description": "Ainda não foi criado",
                "icon": "route",
                "disabled": True,
            },
        )
        self.assertIn('aria-disabled="true"', html)
        self.assertIn('role="menuitem"', html)
        self.assertNotIn("<a", html)
        self.assertIn('.menu__item[aria-disabled="true"]', self.menu_css)

    def test_base_carrega_o_bundle_antes_do_css_de_tela(self):
        """A ordem da cascata mora no bundle; `extra_css` vem depois dele.

        O teste guardava também a ordem entre `actions/buttons.css` e
        `actions/action-system.css`. As duas foram apagadas em 2026-08-20 — a
        primeira porque 48 das 54 classes dela não vestiam nada e o que sobrava
        (o tooltip global) já era do `v2/tooltip.css`; a segunda porque o último
        menu do sistema antigo virou `c-v2.menu`.
        """
        base = (self.root / "templates" / "base.html").read_text(encoding="utf-8")

        self.assertIn("css/shell.bundle.css", base)
        self.assertLess(
            base.index("css/shell.bundle.css"),
            base.index("{% block extra_css %}"),
        )
        self.assertFalse(
            (self.root / "static" / "css" / "actions").exists(),
            "a pasta de folhas de botão legadas voltou",
        )
