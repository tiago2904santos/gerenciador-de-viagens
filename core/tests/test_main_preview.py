"""Contrato da galeria do sistema v2 (`/dev/main-preview/`).

NOVO-120: este arquivo media a prévia ANTERIOR — três variações de header, três
de sub-header, form-card, entity-card e collection-panel, servidas por
`cotton/dev/` e `css/dev/`. Aquela prévia foi apagada por decisão do dono, e com
ela os 6 componentes, as 18 folhas e o script do lab.

O que ficou é a galeria do v2. As asserções aqui cobrem as três coisas que de
fato falharam durante a construção:

1. a galeria RENDERIZA — um `{% cotton:vars %}` errado derruba a página inteira;
2. ela é o consumidor de produção de todo componente `cotton/v2/`, sem o qual o
   guarda de órfão reprova;
3. os grupos existem — se um sumir, algum componente saiu da vitrine sem que
   ninguém tenha decidido isso.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
LAB = ROOT / "templates" / "core" / "main_preview.html"
# A galeria virou uma página por seção (2026-08-16): a casca continua em
# `main_preview.html` e cada grupo mora num fragmento ao lado. Este contrato
# passa a ler a CASCA MAIS OS FRAGMENTOS — se olhasse só o arquivo antigo,
# todo componente que saiu para um fragmento seria dado como ausente da
# vitrine, e o guarda de órfão reprovaria a biblioteca inteira.
LAB_SECOES = ROOT / "templates" / "core" / "main_preview"
V2 = ROOT / "templates" / "cotton" / "v2"

GRUPOS = (
    "Ação",
    "Entrada",
    "Navegação",
    "Conteúdo",
    "Lista",
    "Formulário avançado",
    "Estrutura",
)

MARCAS_DA_PREVIA_V1 = (
    "main-preview-header",
    "main-preview-sub-header",
    "main-preview-form-card",
    "main-preview-entity-card",
    "main-preview-collection-panel",
)


class GaleriaV2ContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fragmentos = sorted(LAB_SECOES.glob("*.html"))
        cls.source = LAB.read_text(encoding="utf-8") + "".join(
            fragmento.read_text(encoding="utf-8") for fragmento in cls.fragmentos
        )

    def test_a_galeria_compila(self):
        get_template("core/main_preview.html")
        for fragmento in self.fragmentos:
            with self.subTest(secao=fragmento.name):
                get_template(f"core/main_preview/{fragmento.name}")

    def test_cada_secao_da_view_tem_fragmento(self):
        """A view aponta para `core/main_preview/<slug>.html`; um slug sem arquivo
        derruba a página com `TemplateDoesNotExist` só quando alguém a abre."""
        from core.views import SECOES_DA_GALERIA

        nomes = {fragmento.name for fragmento in self.fragmentos}
        faltando = [slug for slug, _ in SECOES_DA_GALERIA if f"{slug}.html" not in nomes]
        self.assertEqual(faltando, [], "seção declarada na view sem fragmento")

    def test_cada_fragmento_esta_declarado_na_view(self):
        """O contrário: fragmento que ninguém alcança é página órfã — não há link
        para ela, e ela sai do ar sem que nenhum teste perceba."""
        from core.views import SECOES_DA_GALERIA

        slugs = {slug for slug, _ in SECOES_DA_GALERIA}
        sobrando = [f.name for f in self.fragmentos if f.stem not in slugs]
        self.assertEqual(sobrando, [], "fragmento sem seção na view")

    def test_todo_componente_v2_aparece_na_galeria(self):
        """Sem consumidor, `test_componentes_sem_orfao` reprova o componente.

        Esta asserção falha ANTES daquela e diz QUAL componente ficou de fora —
        a informação que falta lá.
        """
        # Vale também o consumo INDIRETO: `stepper` só aparece dentro de
        # `wizard_page`, e isso é composição legítima — exigir citação direta
        # obrigaria a duplicar na vitrine o que um componente já compõe.
        entre_componentes = "".join(
            c.read_text(encoding="utf-8") for c in sorted(V2.glob("*.html"))
        )
        # As duas peças de CASCA não cabem numa vitrine: a barra lateral É a
        # página (mostrá-la dentro de um painel seria desenhá-la duas vezes na
        # mesma tela), e o sprite não desenha nada sozinho — ele é a folha de
        # símbolos que todo ícone referencia. As duas são renderizadas pelo
        # `base.html`, inclusive nesta galeria; o que falta é a moldura, não o
        # consumidor (2026-08-19).
        CASCA = {"sidebar.html", "sprite.html"}
        ausentes = [
            componente.name
            for componente in sorted(V2.glob("*.html"))
            if componente.name not in CASCA
            and f"<c-v2.{componente.stem}" not in self.source
            and f"<c-v2.{componente.stem}" not in entre_componentes
        ]
        self.assertEqual(ausentes, [], "componente v2 sem consumidor")

    def test_os_grupos_da_galeria_existem(self):
        for grupo in GRUPOS:
            with self.subTest(grupo=grupo):
                self.assertIn(f'class="v2-lab__group">{grupo}<', self.source)

    def test_a_previa_antiga_nao_voltou(self):
        """Trava de regressão, com a prova por marca que o `AGENTS.md` §3.6 pede."""
        for marca in MARCAS_DA_PREVIA_V1:
            with self.subTest(marca=marca):
                self.assertNotIn(marca, self.source)

    def test_os_diretorios_do_lab_v1_nao_voltaram(self):
        for rel in ("templates/cotton/dev", "static/css/dev", "static/js/dev"):
            with self.subTest(rel=rel):
                caminho = ROOT / rel
                arquivos = sorted(caminho.glob("*")) if caminho.exists() else []
                self.assertEqual(arquivos, [], f"{rel} voltou a ter arquivos")

    def test_a_galeria_nao_declara_folha_propria(self):
        """O v2 chega pelo bundle global; a galeria não carrega CSS de página.

        Enquanto a prévia v1 existiu, esta página trazia 18 `<link>` de
        `css/dev/`. Voltar a ter um é sinal de que algum componente ganhou folha
        fora de `static/css/v2/`.
        """
        self.assertNotIn("{% block extra_css %}", self.source)
