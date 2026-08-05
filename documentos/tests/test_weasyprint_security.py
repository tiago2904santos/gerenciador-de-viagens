"""QA-06 — a mitigação da PYSEC-2026-3412 precisa ser provada por comportamento.

O `pip-audit` do CI (`tests.yml`) **ignora essa CVE** citando este arquivo como
justificativa. A versão original do teste era:

    self.assertIn("presentational_hints=False", inspect.getsource(...))

Isso prova que a string existe no código-fonte da função, não que o PDF gerado
ignora atributo de apresentação do HTML. Um refactor que movesse a flag para um
dict de kwargs, ou que abrisse um segundo caminho de renderização sem ela,
passaria no teste e regrediria a mitigação — enquanto o CI continuaria ignorando
a CVE em nome dele.

## Por que a comparação é adaptador contra adaptador

A primeira reescrita renderizava com `weasyprint.HTML(...)` direto e comparava o
resultado do adaptador com essa referência. **Passou local e reprovou no CI**: o
adaptador produziu um terceiro documento, diferente das duas referências. Mesma
versão de WeasyPrint (68.1, travada no `lock.txt`) e `base_url` provadamente
irrelevante para a saída — a diferença não foi reproduzível fora do runner.

A causa exata importa menos que a lição: reconstruir a chamada do adaptador à mão
acopla a asserção a tudo que o adaptador faz de diferente (`base_url`, folhas de
estilo, fontes instaladas) e a tudo que o ambiente faz de diferente. O teste
passa a falhar por motivo que não é o defeito que ele vigia.

Aqui os dois lados da comparação são **o mesmo adaptador, no mesmo processo**,
com um espião que troca só o valor de `presentational_hints`. O que sobra de
diferença entre eles é, por construção, o efeito da flag — e nada mais.
"""

from __future__ import annotations

import contextlib
import hashlib
from unittest import mock

import weasyprint
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


@contextlib.contextmanager
def _espiar_write_pdf(*, forcar_hints=None):
    """Observa (e opcionalmente sobrescreve) o `presentational_hints` da chamada real.

    O adaptador faz `from weasyprint import HTML` **dentro** da função, então o
    alvo do patch é `weasyprint.HTML`, não um atributo do módulo adaptador.
    """
    chamadas: list[dict] = []
    HTMLOriginal = weasyprint.HTML

    class HTMLEspiao(HTMLOriginal):
        def write_pdf(self, *args, **kwargs):
            chamadas.append(dict(kwargs))
            if forcar_hints is not None:
                kwargs["presentational_hints"] = forcar_hints
            return super().write_pdf(*args, **kwargs)

    with mock.patch.object(weasyprint, "HTML", HTMLEspiao):
        yield chamadas


class WeasyPrintSecurityTests(SimpleTestCase):
    def _render(self, *, forcar_hints=None):
        """Roda o adaptador de verdade; devolve `(pdf, kwargs_de_cada_write_pdf)`."""
        with _espiar_write_pdf(forcar_hints=forcar_hints) as chamadas:
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
        return pdf, chamadas

    def test_o_adaptador_desliga_as_dicas_na_chamada_real(self):
        """Substitui o `inspect.getsource`: lê o argumento que de fato chegou ao WeasyPrint.

        Mover a flag para um dict de kwargs continua passando — como deve. Abrir um
        caminho de renderização que não a passe reprova aqui.
        """
        _, chamadas = self._render()

        self.assertEqual(len(chamadas), 1, msg=f"esperava uma renderização, houve {len(chamadas)}")
        self.assertIs(
            chamadas[0].get("presentational_hints"),
            False,
            msg=f"o adaptador chamou write_pdf com {chamadas[0].get('presentational_hints')!r}",
        )

    def test_com_as_dicas_ligadas_o_documento_sairia_diferente(self):
        """A asserção que sustenta a CVE — e a que impede este teste de virar vácuo.

        Os dois lados são o mesmo adaptador; só a flag muda. Se o HTML de teste
        deixasse de exercitar as dicas, os dois sairiam iguais e isto reprova.
        """
        real, _ = self._render()
        com_dicas, _ = self._render(forcar_hints=True)

        self.assertNotEqual(
            hashlib.sha256(real).hexdigest(),
            hashlib.sha256(com_dicas).hexdigest(),
            msg="ligar as dicas não mudou o documento — ou a flag não tem efeito, "
            "ou o HTML de teste parou de exercitá-la; nos dois casos a CVE ficou sem prova",
        )

    def test_forcar_a_flag_para_false_reproduz_o_documento_real(self):
        """Prova que o espião é fiel: forçar o valor que já era usado não muda nada.

        Sem isto, o teste acima poderia estar medindo o efeito do próprio espião.

        As duas asserções são separadas de propósito. Uma comparação de bytes pode
        falhar por dois motivos bem diferentes — renderização não determinística ou
        espião infiel — e a mensagem tem que dizer qual dos dois foi, em vez de
        deixar quem lê adivinhar. Foi justamente a falta disso que fez a primeira
        versão deste arquivo reprovar no CI sem explicar por quê.
        """
        real, _ = self._render()
        de_novo, _ = self._render()
        forcado, _ = self._render(forcar_hints=False)

        self.assertEqual(
            hashlib.sha256(real).hexdigest(),
            hashlib.sha256(de_novo).hexdigest(),
            msg="duas renderizações idênticas deram documentos diferentes — o WeasyPrint "
            "deixou de ser determinístico neste ambiente, e nenhuma comparação de bytes "
            "deste arquivo é confiável",
        )
        self.assertEqual(
            hashlib.sha256(real).hexdigest(),
            hashlib.sha256(forcado).hexdigest(),
            msg="o espião alterou o documento — a comparação do teste anterior não é confiável",
        )
