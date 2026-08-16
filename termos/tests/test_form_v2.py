"""O cadastro de termo no v2 continua salvando — e continua ligado ao script.

A tela trocou de casca inteira: saiu `flow_base` + `c-form.card` + cinco folhas
de página, entrou `header` + `panel` + `form_block` do v2. Nada disso pode ter
mexido em duas coisas:

1. os NOMES dos campos que o `TermoAutorizacaoForm` lê no POST — se um mudar, a
   tela salva pela metade e ninguém vê erro;
2. os IDs e `data-*` que `js/pages/termos-form.js` procura para copiar destino,
   período, equipe e viatura do ofício vinculado — se um sumir, a cópia para de
   acontecer em silêncio, e a página fica idêntica.
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cidade, Estado
from termos.models import TermoAutorizacao
from usuarios.models import AreaTrabalho, VinculoUsuarioArea

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "termos" / "form.html"
SCRIPT = ROOT / "static" / "js" / "pages" / "termos-form.js"


class FormularioV2Tests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área", sigla="AR")
        user = get_user_model().objects.create_user(username="t_v2", password="123456")
        VinculoUsuarioArea.objects.create(usuario=user, area=self.area, ativo=True, area_padrao=True)
        self.client.force_login(user)
        self.estado = Estado.objects.create(nome="Paraná", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")

    def _html(self, url):
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    def test_a_pagina_nao_carrega_folha_de_pagina(self):
        """Cinco folhas saíram daqui; tudo o que desenha vem do `ui.bundle.css`."""
        fonte = TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("css/pages/", fonte)
        self.assertNotIn("css/lists/", fonte)
        # A checagem é na linha do `extends`, não no arquivo inteiro: o nome do
        # casco antigo aparece no comentário que registra a troca.
        self.assertIn('{% extends "base.html" %}', fonte)
        self.assertNotIn("{% extends \"cotton/page/flow_base.html\" %}", fonte)

    def test_os_campos_do_post_continuam_os_mesmos(self):
        html = self._html(reverse("termos:novo"))
        for nome in (
            'name="destino_estado"',
            'name="destino_cidade"',
            'name="data_evento_inicio"',
            'name="data_evento_fim"',
            'name="servidores"',
            'name="viatura"',
            'name="oficio"',
        ):
            self.assertIn(nome, html)

    def test_os_ganchos_do_script_da_pagina_continuam_na_tela(self):
        """Cada um é um `querySelector` literal em `termos-form.js`."""
        html = self._html(reverse("termos:novo"))
        script = SCRIPT.read_text(encoding="utf-8")
        for gancho in (
            "termo-evento-date-picker",
            "termo-evento-destinos",
            "id_oficio_busca",
            "termo-oficio-lista",
        ):
            self.assertIn(gancho, html, f"{gancho} sumiu da tela")
            self.assertIn(gancho, script, f"{gancho} não é mais procurado pelo script")
        # Fronteira exata: `assertIn("data-termo-form")` também casa com
        # `data-termo-form-x`, e a primeira versão deste teste passava com o
        # gancho renomeado.
        self.assertRegex(html, r"data-termo-form[\s>]")
        self.assertRegex(html, r'data-api-cidades-url="[^"]+"')

    def test_o_calendario_escreve_nos_campos_do_formulario(self):
        """Sem `start_field`/`end_field` o calendário vira enfeite: mostra a data
        na tela e não manda nada no POST."""
        html = self._html(reverse("termos:novo"))
        self.assertIn("data-cv-date-picker-start-value", html)
        self.assertIn("data-cv-date-picker-end-value", html)

    def test_os_campos_sao_pickers_do_v2(self):
        """A marca vai no `<select>`: o motor o transplanta e ele perde os pais.

        A verificação é por CAMPO, e não por contagem: a seção de destinos
        sozinha já emite quatro marcas, então um total bastava mesmo depois de
        equipe, viatura e ofício perderem a delas.
        """
        html = self._html(reverse("termos:novo"))
        for campo in ("servidores", "viatura", "oficio"):
            trecho = html[: html.index(f'name="{campo}"')]
            abertura = trecho.rindex("<select")
            self.assertIn(
                "data-picker-v2",
                html[abertura : html.index(">", html.index(f'name="{campo}"'))],
                f"o campo {campo} não é um picker do v2",
            )

    def test_cadastra_pelo_post(self):
        antes = TermoAutorizacao.objects.count()
        resposta = self.client.post(
            reverse("termos:novo"),
            {
                "destino_estado": self.estado.pk,
                "destino_cidade": self.cidade.pk,
                "data_evento_inicio": "2026-09-01",
                "data_evento_fim": "2026-09-03",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(TermoAutorizacao.objects.count(), antes + 1)

    def test_a_edicao_nasce_preenchida(self):
        """`data-picker-initial-value` é o que o `picker.js` lê para mostrar o
        rótulo. Sem ele o `<option selected>` continua certo no POST, mas o campo
        aparece vazio — e a pessoa reescolhe o que já estava lá."""
        # Cidade nova, com pk diferente do estado: com os dois em 1, a marca da
        # cidade satisfazia a asserção do estado e o teste nascia cego.
        cidade = Cidade.objects.create(nome="Londrina", estado=self.estado, uf="PR")
        termo = TermoAutorizacao.objects.create(
            area=self.area,
            destino_estado=self.estado,
            destino_cidade=cidade,
            data_evento_inicio="2026-09-01",
            data_evento_fim="2026-09-03",
        )
        html = self._html(reverse("termos:editar", args=[termo.pk]))
        self.assertNotEqual(self.estado.pk, cidade.pk)
        estado_sel = html[html.index("data-location-state") :]
        estado_sel = estado_sel[: estado_sel.index(">")]
        cidade_sel = html[html.index("data-location-city") :]
        cidade_sel = cidade_sel[: cidade_sel.index(">")]
        self.assertIn(f'data-picker-initial-value="{self.estado.pk}"', estado_sel)
        self.assertIn(f'data-picker-initial-value="{cidade.pk}"', cidade_sel)
        self.assertIn(f'<option value="{cidade.pk}" selected>', html)

    def test_o_bloco_de_documentos_so_existe_em_termo_salvo(self):
        self.assertNotIn(
            "Documentos para conferência", self._html(reverse("termos:novo"))
        )
