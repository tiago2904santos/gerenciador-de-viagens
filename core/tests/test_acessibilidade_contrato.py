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
    ARIA_CONTROLS_VIA_ENHANCER,
    aria_expanded_sem_controls,
    label_sem_for,
)


JS_DIR = Path(settings.BASE_DIR) / "static" / "js"


class AriaExpandedTests(SimpleTestCase):
    def test_todo_aria_expanded_declara_aria_controls(self):
        """`aria-expanded` sem `aria-controls` não diz ao leitor de tela o que abriu."""
        self.assertEqual(aria_expanded_sem_controls(), [])

    def test_aria_controls_aponta_para_um_id_que_existe_no_mesmo_template(self):
        """Um `aria-controls` para id inexistente é pior que nenhum: promete e não cumpre.

        A varredura é por arquivo porque gatilho e painel dos menus de ação vivem
        sempre no mesmo partial. `templates/base.html` é a exceção conhecida — ele
        aponta para o `id` da sidebar, que mora em `components/layout/sidebar.html`.
        """
        raiz = Path(settings.BASE_DIR) / "templates"
        orfaos = []
        for path in sorted(raiz.rglob("*.html")):
            if {"ui_lab", "ui_lab2", "dev"} & set(path.parts):
                continue
            if path.name == "base.html" and path.parent == raiz:
                continue
            texto = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r'aria-controls="([^"]+)"', texto):
                if f'id="{match.group(1)}"' not in texto:
                    orfaos.append(f"{path.relative_to(raiz)} -> {match.group(1)}")
        self.assertEqual(orfaos, [])


class LabelForTests(SimpleTestCase):
    def test_todo_label_declara_for(self):
        """Sem `for`, clicar no rótulo não foca o campo quando ele é irmão, não filho."""
        self.assertEqual(label_sem_for(), [])


class AriaControlsViaEnhancerTests(SimpleTestCase):
    """Os quatro templates isentos da catraca só podem ficar isentos porque o JS cumpre.

    Sem estes testes a isenção seria uma desculpa: bastaria alguém apagar a
    chamada no enhancer para o `aria-controls` desaparecer da tela sem que gate
    nem suíte reclamassem.
    """

    def test_o_gerador_de_id_e_unico_e_mora_no_nucleo(self):
        app = (JS_DIR / "core" / "app.js").read_text(encoding="utf-8")
        self.assertIn("window.CV.a11y = {", app)
        self.assertIn("vincularExpansivel:", app)
        self.assertIn("idUnico:", app)

    def test_enhancers_dos_templates_isentos_chamam_o_helper(self):
        donos = {
            "templates/components/ui/forms/date_picker.html": "components/cv-date-picker.js",
            "templates/roteiros/partials/roteiro/_bate_volta_date_controls.html": (
                "components/cv-date-picker.js"
            ),
            "templates/components/ui/forms/dropdown.html": "cv-select.js",
            "templates/components/ui/forms/file_picker.html": "components/file-picker.js",
        }
        self.assertEqual(
            sorted(donos),
            sorted(ARIA_CONTROLS_VIA_ENHANCER),
            "a lista de isentos do auditor divergiu da lista de donos deste teste",
        )
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
