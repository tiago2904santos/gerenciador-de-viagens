"""Contrato de acessibilidade dos gatilhos e rótulos (H-06 e H-10).

O gate de CI (`scripts/audit_frontend_standards.py`) mede o mesmo que estes
testes, por outro caminho — a catraca protege o número no pipeline, o teste
protege o contrato quando alguém roda só a suíte. Os dois medindo a mesma coisa
é de propósito: em etapas anteriores um defeito passou porque o gate estava
verde num arquivo que o teste nem lia.
"""

import re
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


sys.path.insert(0, str(Path(settings.BASE_DIR) / "scripts"))

from audit_frontend_standards import (  # noqa: E402
    aria_expanded_sem_controls,
    label_sem_for,
)


JS_DIR = Path(settings.BASE_DIR) / "static" / "js"


class AriaExpandedTests(SimpleTestCase):
    def test_todo_aria_expanded_declara_aria_controls(self):
        """`aria-expanded` sem `aria-controls` não diz ao leitor de tela o que abriu."""
        self.assertEqual(aria_expanded_sem_controls(), [])

    def test_aria_controls_aponta_para_um_id_que_existe(self):
        """Um `aria-controls` para id inexistente é pior que nenhum: promete e não cumpre.

        A varredura é por arquivo porque gatilho e painel dos menus de ação vivem
        quase sempre no mesmo partial. Há duas travessias legítimas de arquivo:

        - `templates/base.html`, que aponta para o `id` da sidebar, declarado em
          `components/layout/sidebar.html`;
        - um partial que recebe o id por `{% include ... with var=... %}`. É o caso
          de `_bate_volta_date_controls.html`, incluído só por `date_picker.html`,
          que passa `panel_id` e declara o painel. Aqui o teste **segue** o include
          em vez de dispensar a checagem: um `{{ var }}` só passa se o template que
          inclui esse partial declarar `id="{{ var }}"`. Dispensar variáveis em
          bloco desligaria a garantia justamente onde ela é mais fácil de quebrar.
        """
        raiz = Path(settings.BASE_DIR) / "templates"
        producao = [
            p
            for p in sorted(raiz.rglob("*.html"))
            if not ({"ui_lab", "ui_lab2", "dev"} & set(p.parts))
        ]
        fontes = {p: p.read_text(encoding="utf-8-sig") for p in producao}

        def declarado_por_quem_inclui(alvo, variavel):
            """Algum template declara o painel e repassa a variável num `{% include %}`?

            Não dá para exigir que o pai cite o caminho do partial: `date_picker.html`
            inclui o dele por **variável** (`range_controls_template`), e quem nomeia o
            arquivo é o avô, `_bate_volta_body.html`. Então a checagem é pela dupla que
            de fato importa — alguém declara `id="{{ var }}"` e alguém repassa
            `var=var` adiante — em vez de tentar reconstruir a árvore de includes.
            """
            for outro, texto in fontes.items():
                if outro == alvo:
                    continue
                if f"{variavel}={variavel}" in texto and f'id="{{{{ {variavel} }}}}"' in texto:
                    return True
            return False

        orfaos = []
        for path in producao:
            if path.name == "base.html" and path.parent == raiz:
                continue
            texto = fontes[path]
            for match in re.finditer(r'aria-controls="([^"]+)"', texto):
                alvo = match.group(1)
                if f'id="{alvo}"' in texto:
                    continue
                variavel = re.fullmatch(r"\{\{\s*(\w+)\s*\}\}", alvo)
                if variavel and declarado_por_quem_inclui(path, variavel.group(1)):
                    continue
                orfaos.append(f"{path.relative_to(raiz)} -> {alvo}")
        self.assertEqual(orfaos, [])


class LabelForTests(SimpleTestCase):
    def test_todo_label_declara_for(self):
        """Sem `for`, clicar no rótulo não foca o campo quando ele é irmão, não filho."""
        self.assertEqual(label_sem_for(), [])


class AriaControlsViaEnhancerTests(SimpleTestCase):
    """O par gatilho/painel dos componentes flutuantes continua sendo escrito pelo JS.

    Estes testes existiam para justificar as isenções da catraca. As isenções
    caíram — o `cee354f` declarou `aria-controls` nos próprios templates — mas os
    testes ficam, porque o que eles medem não é a isenção: é que o gerador de id do
    sistema é **um só** (o `cv-select.js` mantinha um `_uid` paralelo) e que os
    enhancers seguem religando o par em runtime. Isso ainda importa: o painel do
    date picker é movido para `document.body`, e conteúdo trazido por AJAX é
    reprocessado pelo coordenador depois que o HTML do servidor já foi entregue.
    """

    def test_o_gerador_de_id_e_unico_e_mora_no_nucleo(self):
        app = (JS_DIR / "core" / "app.js").read_text(encoding="utf-8")
        self.assertIn("window.CV.a11y = {", app)
        self.assertIn("vincularExpansivel:", app)
        self.assertIn("idUnico:", app)

    def test_enhancers_de_painel_flutuante_chamam_o_helper(self):
        donos = {
            "templates/components/ui/forms/date_picker.html": "components/cv-date-picker.js",
            "templates/roteiros/partials/roteiro/_bate_volta_date_controls.html": (
                "components/cv-date-picker.js"
            ),
            "templates/components/ui/forms/dropdown.html": "cv-select.js",
            "templates/components/ui/forms/file_picker.html": "components/file-picker.js",
        }
        for template, js in donos.items():
            with self.subTest(template=template):
                fonte = (JS_DIR / js).read_text(encoding="utf-8")
                self.assertIn(
                    "CV.a11y.vincularExpansivel",
                    fonte,
                    f"{js} não liga aria-controls, mas {template} está isento do gate",
                )

    def test_nenhum_enhancer_mantem_gerador_de_id_proprio(self):
        """`cv-select.js` tinha seu próprio contador `_uid`; o gerador agora é um só."""
        self.assertNotIn("_uid", (JS_DIR / "cv-select.js").read_text(encoding="utf-8"))
