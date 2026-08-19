"""NOVO-20260818-213853-fab772ef1b6e: conclusão das telas de Ofícios no v2.

Espelha `cadastros/tests/test_componentes_v2.py`. O guarda principal é o
primeiro: nenhum template de Ofícios pode chamar um componente de namespace
anterior ao v2. Ele é a trava que impede a migração de voltar por partes — que
foi como o sistema antigo acumulou seis vocabulários visuais.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.test import TestCase


ROOT = Path(settings.BASE_DIR)
TEMPLATES = ROOT / "templates"
OFICIOS = TEMPLATES / "oficios"

#: `{% comment %} … {% endcomment %}`, que é onde a documentação do template
#: mora. As varreduras abaixo olham a MARCAÇÃO: um comentário que explica por
#: que uma classe saiu não pode contar como a classe tendo voltado.
COMENTARIO = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.DOTALL)


def marcacao(template: Path) -> str:
    return COMENTARIO.sub("", template.read_text(encoding="utf-8"))


class ComponentesOficiosV2SourceTests(SimpleTestCase):
    def test_oficios_nao_chamam_componentes_visuais_anteriores_ao_v2(self):
        namespaces_legados = (
            "<c-ui.",
            "<c-cards.",
            "<c-feedback.",
            "<c-form.",
            "<c-lists.",
            "<c-travel.",
        )
        offenders = {}
        for template in sorted(OFICIOS.rglob("*.html")):
            source = marcacao(template)
            encontrados = [tag for tag in namespaces_legados if tag in source]
            if encontrados:
                offenders[str(template.relative_to(TEMPLATES))] = encontrados

        self.assertEqual(offenders, {})

    def test_as_cinco_etapas_do_wizard_partem_da_mesma_casca(self):
        """Uma casca só, e ela é o `c-v2.wizard_page`.

        O legado tinha o cabeçalho grudento (`wizard-sticky-scope`) montado na
        base e repetido em classes de página por etapa. Se uma etapa deixar de
        estender a base, ela volta a desenhar a própria casca sem que nada
        quebre.
        """
        base = marcacao(OFICIOS / "wizard_base.html")
        self.assertIn("<c-v2.wizard_page", base)
        self.assertNotIn("wizard-sticky-scope", base)
        self.assertNotIn("page-shell--wizard", base)

        for nome in (
            "wizard_dados_viajantes.html",
            "wizard_transporte.html",
            "wizard_roteiro.html",
            "wizard_justificativa.html",
            "wizard_documentos.html",
        ):
            with self.subTest(etapa=nome):
                source = marcacao(OFICIOS / nome)
                self.assertIn('{% extends "oficios/wizard_base.html" %}', source)

    def test_nenhuma_tela_de_oficio_carrega_folha_de_pagina_propria(self):
        """As folhas de `css/pages/` saíram: tudo vem do bundle do v2.

        A exceção é o Leaflet, que é folha de terceiro e desenha o mapa — a
        mesma exceção que a tela avulsa de roteiro já carrega.
        """
        offenders = {}
        for template in sorted(OFICIOS.rglob("*.html")):
            source = marcacao(template)
            folhas = [
                linha.strip()
                for linha in source.splitlines()
                if "css/pages/" in linha or "css/base/" in linha
            ]
            if folhas:
                offenders[str(template.relative_to(TEMPLATES))] = folhas

        self.assertEqual(offenders, {})

    def test_parciais_substituidas_pela_composicao_v2_foram_removidas(self):
        """Rodapé e cartão de ação viraram composição na própria etapa.

        Cada um destes era um arquivo de uma linha, que existia só porque o
        `c-form.card` cobrava um slot por peça. No v2 o rodapé são dois botões
        dentro do `card_footer`, escritos onde os rótulos mudam.
        """
        removidas = (
            "oficios/partials/_dados_viajantes_footer.html",
            "oficios/partials/_transporte_footer.html",
            "oficios/partials/_transporte_header_actions.html",
            "oficios/partials/_justificativa_wizard_body.html",
            "oficios/partials/_justificativa_wizard_footer.html",
            "oficios/partials/_documentos_wizard_footer.html",
            "oficios/partials/_motorista_modo_toggle.html",
            "oficios/partials/wizard_dados_card_viatura.html",
            "oficios/partials/_viatura_card_body.html",
            "oficios/partials/_viatura_card_footer.html",
            "oficios/partials/_viatura_card_header_actions.html",
            "oficios/partials/wizard_actions.html",
            "oficios/partials/wizard_stepper.html",
            # Órfãos medidos na migração: zero referências em `templates/`,
            # `static/js/`, `static/css/` e `*.py`.
            "oficios/partials/assinatura_central_documento.html",
            "oficios/partials/assinatura_etiqueta_actions.html",
        )
        existentes = [relative for relative in removidas if (TEMPLATES / relative).exists()]
        self.assertEqual(existentes, [])

    def test_a_etapa_de_roteiro_usa_o_mesmo_editor_da_tela_avulsa(self):
        """Um editor, duas telas.

        O legado (`_roteiro_editor.html`) mantinha uma segunda cópia da mesma
        tela só para o wizard, e as duas divergiram por um ciclo inteiro.
        """
        source = marcacao(OFICIOS / "wizard_roteiro.html")
        self.assertIn("roteiros/includes/_roteiro_editor_v2.html", source)
        self.assertNotIn("roteiros/includes/_roteiro_editor.html", source)


class ConferenciaDeDocumentosV2Tests(TestCase):
    """Os dois defeitos que a revisão automática pegou na etapa de documentos.

    Ambos passavam calados: o Django não levanta erro em nenhum dos dois, e o
    contrato de marcação não olha valor renderizado.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        from cadastros.models import Cargo
        from cadastros.models import Servidor
        from core.testing import area_de_teste
        from core.testing import vincular_area
        from oficios.models import Oficio

        usuario = get_user_model().objects.create_user(username="conferencia", password="123456")
        self.client.force_login(usuario)
        vincular_area(usuario)
        area = area_de_teste()
        cargo = Cargo.objects.create(area=area, nome="AGENTE")
        self.oficio = Oficio.objects.create(
            area=area,
            numero=1,
            ano=2026,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        for indice, nome in enumerate(("ADEMAR SCHONS", "ADRIANO SILVA"), start=1):
            servidor = Servidor.objects.create(
                area=area,
                nome=nome,
                cargo=cargo,
                cpf=f"1234567890{indice}",
            )
            self.oficio.servidores.add(servidor)
            self.oficio.servidores_termo_autorizacao.add(servidor)

    def _html(self):
        from django.urls import reverse

        resposta = self.client.get(reverse("oficios:wizard_documentos", args=[self.oficio.pk]))
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode("utf-8")

    def test_cada_termo_tem_o_id_do_proprio_menu(self):
        """`"texto"|add:forloop.counter` devolve string VAZIA, sem erro.

        O filtro tenta `int(valor) + int(arg)`, falha no prefixo, tenta
        `valor + arg`, e somar `str` com `int` falha de novo — `add` cai no
        `except` e devolve `''`. Com o id vazio o gatilho perdia os três
        atributos de overlay e o menu nascia sem `id` e sem `hidden`: botão
        inerte e lista de ações cravada na página.
        """
        html = self._html()
        for contador in (1, 2):
            with self.subTest(termo=contador):
                self.assertIn(f'id="wizard-termo-document-menu-{contador}"', html)
                self.assertIn(
                    f'data-overlay-target="wizard-termo-document-menu-{contador}"',
                    html,
                )

    def test_documento_indisponivel_mostra_o_motivo_em_vez_do_visualizador(self):
        """A URL existe sempre; o documento, não.

        `di.oficio.url` é rota revertida e nunca vem vazia, então usá-la como
        `src` fazia o cartão abrir um `<iframe>` para um PDF que não existe — em
        vez de dizer por que ele ainda não foi gerado. É o guarda de
        disponibilidade que o sistema anterior tinha e que a migração quase
        perdeu.
        """
        html = self._html()
        self.assertIn("document-inline-empty", html)
        self.assertNotIn("document-inline-viewer__frame", html)
