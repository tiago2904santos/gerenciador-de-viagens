"""Nenhuma tela entrega `href="#"` (NOVO-40).

`href="#"` nao e um link: e um link que **pula a pagina para o topo**. O
`DESIGN_SYSTEM.md` ja proibia — "Proibido `href=\"#\"` para acao visual" — e o
auditor tinha uma regra para isso. So que a regra olhava o literal escrito no
template, e a ancora vazia chegava ao HTML por **outros dois caminhos**:

1. **Parametro de componente** — `secondary_url="#"`, `back_url="#"`,
   `primary_action_url="#"`. Eram 19 ocorrencias, contra 10 visiveis a regra.
2. **Dado de contexto** — 43 valores `"#"` nas constantes de demonstracao das
   vitrines, em `core/views.py` e `ui_lab2/views.py`. Nenhuma regra de template
   alcanca isso: o `#` nao esta no `.html`.

Uma so pagina de vitrine entregava **180** ancoras vazias.

Este teste fecha o terceiro caminho, que e o unico que nenhuma regra estatica
sobre arquivos consegue ver: ele RENDERIZA as telas e olha o HTML entregue.
"""

from __future__ import annotations

import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import clear_url_caches
from django.urls import reverse

import config.urls
import core.urls

# As vitrines sao onde a ancora vazia se acumula: elas mostram componentes sem
# ter para onde apontar. Se estas estao limpas, o padrao esta valendo onde ele e
# mais tentador de quebrar.
ROTAS = [
    "/dev/ui-lab/",
    "/dev/ui-lab/buttons/",
    "/dev/ui-lab/cards/",
    "/dev/ui-lab/documents/",
    "/dev/ui-lab/eventos/cadastro/",
    "/dev/ui-lab/eventos/lista/",
    "/dev/ui-lab/feedback/",
    "/dev/ui-lab/fields/",
    "/dev/ui-lab/headers/",
    "/dev/ui-lab/lists/",
    "/dev/ui-lab/overlays/",
    "/dev/ui-lab/selects-filters/",
    "/dev/ui-lab/signature/",
    "/dev/ui-lab/status/",
    "/dev/ui-lab/structures/",
    "/dev/ui-lab/tables/",
    "/dev/ui-lab-2/",
    "/dev/ui-lab-2/buttons/",
    "/dev/ui-lab-2/feedback/",
    "/dev/ui-lab-2/headers/",
    "/dev/ui-lab-2/section-cards/",
    "/dev/ui-lab-2/selects/",
]


class AncoraVaziaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="av_test", password="x")
        self.client.force_login(self.user)

    def _recarrega_urls(self):
        """As rotas de vitrine so existem com DEBUG — ver core/tests/test_ui_lab.py."""
        importlib.reload(core.urls)
        importlib.reload(config.urls)
        clear_url_caches()

    def tearDown(self):
        self._recarrega_urls()

    @override_settings(DEBUG=True)
    def test_nenhuma_vitrine_entrega_ancora_vazia(self):
        self._recarrega_urls()
        sujas = []
        for rota in ROTAS:
            resposta = self.client.get(rota)
            self.assertEqual(resposta.status_code, 200, f"{rota} nao respondeu 200")
            quantas = resposta.content.decode().count('href="#"')
            if quantas:
                sujas.append(f"{rota} ({quantas})")
        self.assertEqual(
            sujas, [],
            "ancora vazia de volta no HTML entregue — link que so pula para o "
            f"topo: {sujas}",
        )

    def test_o_dashboard_e_o_perfil_tambem(self):
        """Tela de produto, para o teste nao virar assunto so de vitrine."""
        for nome in ("core:dashboard", "core:perfil"):
            resposta = self.client.get(reverse(nome))
            self.assertEqual(resposta.status_code, 200)
            self.assertNotIn('href="#"', resposta.content.decode(), nome)
