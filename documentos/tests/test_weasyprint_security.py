"""QA-06 — a mitigação da PYSEC-2026-3412 precisa ser provada por comportamento.

O `pip-audit` do CI (`tests.yml`) **ignora essa CVE** citando este arquivo como
justificativa. A versão anterior do teste era:

    self.assertIn("presentational_hints=False", inspect.getsource(...))

Isso prova que a string existe no código-fonte da função, não que o PDF gerado
ignora atributo de apresentação do HTML. Um refactor que movesse a flag para um
dict de kwargs, ou que abrisse um segundo caminho de renderização sem ela,
passaria no teste e regrediria a mitigação — enquanto o CI continuaria ignorando
a CVE em nome dele.

Aqui o teste renderiza de verdade e compara o resultado com as duas referências:
tem que bater com `presentational_hints=False` e diferir de `True`. A renderização
do WeasyPrint é determinística e não embute timestamp, então a comparação é estável.

Compara por digest, não pelos bytes: um PDF de referência tem ~8 KB, e o
`assertEqual` de bytes despeja o binário inteiro na mensagem de falha. Teste cuja
falha é ilegível é teste que ninguém lê.
"""

from __future__ import annotations

import hashlib
from unittest import mock

from django.test import SimpleTestCase

from documentos.services.adapters.weasyprint_pdf import render_pdf_bytes_weasyprint

# HTML que só um atacante escreveria: atributos de apresentação em vez de CSS.
# `bgcolor`, `color` e `size` só têm efeito quando as dicas estão habilitadas.
HTML_COM_DICAS_DE_APRESENTACAO = """
<html><body>
  <table bgcolor="#ff0000" border="3" width="500">
    <tr><td><font color="#00ff00" size="7" face="Courier">conteúdo</font></td></tr>
  </table>
</body></html>
"""


def _digest(pdf: bytes) -> str:
    return hashlib.sha256(pdf).hexdigest()


def _referencia(*, hints: bool) -> str:
    from weasyprint import HTML

    return _digest(
        HTML(string=HTML_COM_DICAS_DE_APRESENTACAO).write_pdf(
            stylesheets=[],
            presentational_hints=hints,
        )
    )


class WeasyPrintSecurityTests(SimpleTestCase):
    def _render_pelo_adaptador(self) -> str:
        # O que está sob teste é o adaptador, não o motor de template.
        with mock.patch(
            "documentos.services.adapters.weasyprint_pdf.render_to_string",
            return_value=HTML_COM_DICAS_DE_APRESENTACAO,
        ):
            pdf = render_pdf_bytes_weasyprint(
                html_template_name="irrelevante.html",
                context={},
                stylesheet_paths=(),
            )
        return _digest(pdf)

    def test_a_flag_muda_o_documento_produzido(self):
        """Guarda o próprio teste: sem isto, os dois lados poderiam ser iguais por acidente."""
        self.assertNotEqual(
            _referencia(hints=False),
            _referencia(hints=True),
            msg="o HTML de teste não exercita as dicas de apresentação — o teste viraria vácuo",
        )

    def test_o_adaptador_ignora_as_dicas_de_apresentacao_do_html(self):
        gerado = self._render_pelo_adaptador()

        self.assertEqual(
            gerado,
            _referencia(hints=False),
            msg="o PDF gerado não corresponde ao de presentational_hints=False",
        )

    def test_o_adaptador_nao_produz_o_documento_com_as_dicas_habilitadas(self):
        gerado = self._render_pelo_adaptador()

        self.assertNotEqual(
            gerado,
            _referencia(hints=True),
            msg="o PDF gerado corresponde ao de presentational_hints=True — mitigação regrediu",
        )
