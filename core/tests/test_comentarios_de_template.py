"""`{# #}` de várias linhas vaza para o HTML — teste do `NOVO-18`.

Achado com Playwright durante o `H-03`. Um comentário `{# ... #}` que abre numa
linha e fecha em outra **não é comentário** para o Django: o texto sai verbatim
no HTML. Fora de uma tag, aparece como texto visível na página; dentro de uma
tag, o navegador transforma cada palavra num atributo inventado.

Havia um caso vivo em produção — 6 linhas de comentário na etapa Transporte do
wizard de ofício, introduzidas pelo PR #119 e não vistas por nenhum teste,
porque nenhum teste olhava o HTML daquela região.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import SimpleTestCase


# `{#` numa linha sem o `#}` correspondente antes do fim dela.
COMENTARIO_ABERTO = re.compile(r"\{#(?![^\n]*#\})")


class ComentarioDeTemplateTests(SimpleTestCase):
    def test_o_django_realmente_nao_fecha_comentario_entre_linhas(self):
        """A premissa do teste, medida — não assumida.

        Se um dia o Django passar a aceitar `{# #}` multilinha, é este teste que
        avisa, e a varredura abaixo pode ser aposentada.
        """
        fonte = "<p>antes</p>\n{# abre aqui\n   e fecha depois #}\n<p>depois</p>"

        saida = engines["django"].from_string(fonte).render({})

        self.assertIn("abre aqui", saida, "o Django ainda devolve o texto verbatim")

    def test_nenhum_template_abre_comentario_sem_fechar_na_mesma_linha(self):
        vazamentos = []
        raiz = Path(settings.BASE_DIR) / "templates"
        for path in sorted(raiz.rglob("*.html")):
            texto = path.read_text(encoding="utf-8-sig")
            for match in COMENTARIO_ABERTO.finditer(texto):
                linha = texto[: match.start()].count("\n") + 1
                vazamentos.append(f"{path.relative_to(raiz)}:{linha}")

        self.assertEqual(
            vazamentos,
            [],
            "use {% comment %} ... {% endcomment %} para comentário de várias linhas",
        )
