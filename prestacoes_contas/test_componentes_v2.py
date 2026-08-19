"""NOVO-20260819: conclusão das telas de Prestações de Contas no v2.

Espelha `oficios/tests/test_componentes_v2.py`. O guarda principal é o
primeiro: nenhum template de Prestações pode chamar um componente de namespace
anterior ao v2. Ele é a trava que impede a migração de voltar por partes — que
foi como o sistema antigo acumulou seis vocabulários visuais.

A app tem uma particularidade que Ofícios não tinha: um fluxo PÚBLICO, servido
sem barra lateral e sem login para o signatário externo. Ele migrou junto, por
decisão do dono, e por isso está aqui — a casca continua sendo dele, o
vocabulário de dentro passou a ser o do sistema.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.test import TestCase


ROOT = Path(settings.BASE_DIR)
TEMPLATES = ROOT / "templates"
PRESTACOES = TEMPLATES / "prestacoes_contas"

#: `{% comment %} … {% endcomment %}`, que é onde a documentação do template
#: mora. As varreduras abaixo olham a MARCAÇÃO: um comentário que explica por
#: que uma classe saiu não pode contar como a classe tendo voltado.
COMENTARIO = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.DOTALL)


def marcacao(template: Path) -> str:
    return COMENTARIO.sub("", template.read_text(encoding="utf-8"))


class ComponentesPrestacoesV2SourceTests(SimpleTestCase):
    def test_prestacoes_nao_chamam_componentes_visuais_anteriores_ao_v2(self):
        namespaces_legados = (
            "<c-ui.",
            "<c-cards.",
            "<c-feedback.",
            "<c-form.",
            "<c-lists.",
            "<c-travel.",
            "<c-documents.",
            "<c-page.",
        )
        # A ÚNICA exceção, e ela não é visual: `<c-ui.icons._sprite />` é a folha
        # de `<symbol>` dos ícones do sistema. Os ícones são `<use href="#cv-icon-…">`,
        # então sem os símbolos na página cada `<use>` aponta para o nada. O
        # `base.html` a inclui para todo o resto do sistema; a casca pública, que
        # é a única tela que não estende o `base.html`, precisa declará-la. Não
        # há par no v2 porque não é peça do v2 — é a fonte dos desenhos.
        sprite = "<c-ui.icons._sprite"
        offenders = {}
        for template in sorted(PRESTACOES.rglob("*.html")):
            source = marcacao(template).replace(sprite, "")
            encontrados = [tag for tag in namespaces_legados if tag in source]
            if encontrados:
                offenders[str(template.relative_to(TEMPLATES))] = encontrados

        self.assertEqual(offenders, {})

    def test_a_casca_publica_traz_a_folha_de_simbolos(self):
        """Sem ela, todo ícone da tela pública é um espaço em branco.

        Não é hipótese: foi medido no navegador. Os `<use href="#cv-icon-edit">`
        de "Criar assinatura" e dos dois botões de página do visualizador
        renderizavam caixas vazias — o `<svg>` tinha 16×16 e nenhum desenho
        dentro. O `base.html` inclui a folha; esta casca não o estende.
        """
        source = marcacao(PRESTACOES / "assinatura" / "base_publico.html")
        self.assertIn("<c-ui.icons._sprite", source)

    def test_as_quatro_etapas_do_fluxo_partem_da_mesma_casca(self):
        """Uma casca só, e ela é o `c-v2.wizard_page`.

        Antes cada etapa estendia `cotton/page/flow_base.html` e remontava o
        cabeçalho com os seus parâmetros; a casca nova declara o passo, o rótulo
        de estado e o "voltar" uma vez. Se uma etapa deixar de estender a base,
        ela volta a desenhar a própria casca sem que nada quebre.
        """
        base = marcacao(PRESTACOES / "flow_base.html")
        self.assertIn("<c-v2.wizard_page", base)
        self.assertIn('{% extends "base.html" %}', base)

        for nome in (
            "relatorio_tecnico_form.html",
            "diario_bordo_form.html",
            "diario_motorista_form.html",
            "documentos_form.html",
            "consolidado.html",
        ):
            with self.subTest(etapa=nome):
                source = marcacao(PRESTACOES / nome)
                self.assertIn(
                    '{% extends "prestacoes_contas/flow_base.html" %}', source
                )

    def test_so_a_tela_publica_carrega_folha_de_pagina(self):
        """As folhas de `css/pages/` saíram: tudo vem do bundle do v2.

        A exceção é a casca pública, que não passa pelo `base.html` e por isso
        carrega o bundle do sistema por conta própria — mais o resto da folha de
        assinatura, que é o visualizador de PDF em canvas e a folha de criação
        arrastável. Nenhum dos dois tem par no sistema; as fontes, que tinham,
        viraram `static/css/v2/signature-fonts.css`.
        """
        permitidos = {"prestacoes_contas/assinatura/base_publico.html"}
        offenders = {}
        for template in sorted(PRESTACOES.rglob("*.html")):
            relative = str(template.relative_to(TEMPLATES))
            if relative in permitidos:
                continue
            source = marcacao(template)
            folhas = [
                linha.strip()
                for linha in source.splitlines()
                if "css/pages/" in linha or "css/base/" in linha
            ]
            if folhas:
                offenders[relative] = folhas

        self.assertEqual(offenders, {})

    def test_a_casca_publica_veste_os_componentes_do_sistema(self):
        """Sem `ui.bundle.css` a tela pública fica com componentes nus.

        Ela não estende `base.html` — é `<!doctype>` próprio, porque não tem
        barra lateral nem sessão. O preço é que o CSS do sistema não chega por
        herança: ou ele está declarado aqui, ou o `c-v2.panel` da tela do
        signatário sai sem caixa.
        """
        source = marcacao(PRESTACOES / "assinatura" / "base_publico.html")
        self.assertIn("css/ui.bundle.css", source)
        # As duas folhas de base do sistema anterior saíram: os tokens vêm do v2.
        self.assertNotIn("css/style.css", source)
        self.assertNotIn("css/shell.bundle.css", source)

    def test_parciais_substituidas_pela_composicao_v2_foram_removidas(self):
        """Rodapé, cartão e corpo de card viraram composição onde são usados.

        Cada um destes era um arquivo de uma ou duas linhas, que existia só
        porque o `c-form.card` cobrava um slot por peça. No v2 o rodapé são dois
        botões dentro do `card_footer`, escritos onde os rótulos mudam.
        """
        removidas = (
            "prestacoes_contas/partials/_consolidado_footer.html",
            "prestacoes_contas/partials/_diario_footer.html",
            "prestacoes_contas/partials/_docs_footer.html",
            "prestacoes_contas/partials/_rt_downloads_footer.html",
            "prestacoes_contas/partials/_dmv_viatura_footer.html",
            "prestacoes_contas/partials/_docs_attach_trigger.html",
            "prestacoes_contas/partials/_modelos_grupo_actions.html",
            "prestacoes_contas/partials/_modelos_grupo_body.html",
            "prestacoes_contas/partials/_prestacao_card_body.html",
            "prestacoes_contas/partials/_prestacao_card_footer.html",
            "prestacoes_contas/partials/prestacao_list_card.html",
            # Substituídos pelo `c-v2.document_inline` e pelo `c-v2.file_list`.
            "prestacoes_contas/partials/documento_preview.html",
            "prestacoes_contas/partials/_documento_preview_body.html",
            "prestacoes_contas/partials/documento_anexos.html",
        )
        existentes = [relative for relative in removidas if (TEMPLATES / relative).exists()]
        self.assertEqual(existentes, [])

    def test_a_tela_publica_nao_escreve_botao_cru(self):
        """Fechada a saída que sobra depois de o `c-ui.` ser proibido.

        A tela do signatário tinha ONZE botões, e nenhum deles era do sistema:
        eram `c-ui.buttons.plain_button` — o componente-válvula que aceita
        qualquer classe e qualquer atributo, e por isso não impõe desenho
        nenhum. Foi assim que aquela tela acabou com uma família de botões só
        dela (`asgn-btn--primary`, `--ghost`, `--sm`, `--block`).

        Os onze viraram `c-v2.button`, com `element_id` para o script continuar
        achando cada um. A trava de namespace acima já barra o `c-ui.`; esta
        barra o atalho seguinte, que é escrever `<button>` na mão. Botão cru só
        dentro de `templates/cotton/` — é o que `test_raw_button_component`
        cobra do repositório inteiro, e as fontes de assinatura são justamente
        um componente por causa disso.
        """
        offenders = {}
        for template in sorted((PRESTACOES / "assinatura").rglob("*.html")):
            source = marcacao(template)
            if "<button" in source:
                offenders[str(template.relative_to(TEMPLATES))] = "<button"

        self.assertEqual(offenders, {})


class ConferenciaDaTelaPublicaTests(TestCase):
    """Os quatro defeitos que só o navegador pegou.

    Nenhum deles levanta erro: o Django renderiza, a página abre, e o que falha
    é o que a pessoa vê ou consegue fazer. É por isso que estão aqui como
    asserção sobre a resposta, e não como leitura de arquivo.
    """

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from cadastros.models import Cargo
        from cadastros.models import Servidor
        from core.testing import area_de_teste
        from oficios.models import Oficio
        from prestacoes_contas.models import AssinaturaDocumento
        from prestacoes_contas.models import PrestacaoContas

        area = area_de_teste()
        cargo = Cargo.objects.create(area=area, nome="AGENTE")
        servidor = Servidor.objects.create(
            area=area, nome="ADEMAR SCHONS", cargo=cargo, cpf="12345678901"
        )
        oficio = Oficio.objects.create(
            area=area, numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC
        )
        # A prestação e a linha do servidor nascem por sinal quando o ofício
        # ganha equipe — criá-las à mão bate na `unique` de `oficio_id`.
        oficio.servidores.add(servidor)
        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        ps = prestacao.servidores_prestacao.get(servidor=servidor)

        self.token = "token-de-teste-publico"
        self.doc = AssinaturaDocumento.objects.create(
            prestacao=prestacao,
            servidor_prestacao=ps,
            tipo=AssinaturaDocumento.TIPO_RT,
            signer=servidor,
            nome_esperado=servidor.nome,
            link_token=self.token,
            link_criado_em=timezone.now(),
            link_expira_em=timezone.now() + timedelta(days=7),
        )

    def _url(self, nome, *args):
        from django.urls import reverse

        return reverse(f"prestacoes_contas:{nome}", args=args)

    def test_a_contagem_de_documentos_chega_inteira_na_frase(self):
        """`"texto"|add:<int>` devolve string VAZIA, sem erro.

        O filtro tenta `int(esquerda) + int(direita)`, falha no texto, tenta
        `esquerda + direita`, e somar `str` com `int` falha de novo — `add` cai
        no `except`. Com o `stringformat` DEPOIS do `add`, ele formatava o vazio,
        e a frase chegava ao signatário como " documento(s) para assinar.".
        """
        html = self.client.get(self._url("assinatura_landing", self.token)).content.decode()

        self.assertIn("Você recebeu 1 documento(s) para assinar.", html)

    def test_a_sigla_do_documento_e_a_marca_da_linha(self):
        html = self.client.get(self._url("assinatura_landing", self.token)).content.decode()

        self.assertIn("RT", html)
        self.assertIn("Relatório Técnico", html)

    def test_a_confirmacao_de_identidade_aceita_o_valor_do_cartao_de_escolha(self):
        """O cartão de escolha manda `1`; a view exigia o literal `"on"`.

        `"on"` é o que o navegador manda quando o `<input type="checkbox">` NÃO
        declara `value` — o caso da caixa escrita à mão que existia aqui antes.
        O `c-v2.choice_card` declara `value="1"`, porque o widget de checkbox do
        Django lê `""` como FALSO. Com a comparação literal, quem marcava a
        confirmação recebia "Confirme que o nome exibido é o seu para continuar"
        e não saía do lugar.
        """
        resposta = self.client.post(
            self._url("assinatura_identidade", self.token, "rt"),
            {"confirma_nome": "1", "cpf": "123.456.789-01"},
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/assinar/", resposta["Location"])

    def test_sem_confirmacao_a_identidade_continua_barrada(self):
        """A trava do teste acima não pode ter virado "aceita qualquer POST"."""
        resposta = self.client.post(
            self._url("assinatura_identidade", self.token, "rt"),
            {"cpf": "123.456.789-01"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Confirme que o nome exibido", resposta.content.decode())

    def test_os_botoes_de_pagina_do_visualizador_tem_id(self):
        """`element_id` não estava declarado no `c-v2.icon_button`.

        O Cotton DESCARTA calado o atributo que o componente não declara: os dois
        botões saíam sem `id`, `js/pages/prestacoes-assinatura.js` achava `null`
        e a página inteira morria no primeiro `addEventListener` — sem ícone,
        sem visualizador, sem folha de assinatura. Medido no navegador.
        """
        self.client.post(
            self._url("assinatura_identidade", self.token, "rt"),
            {"confirma_nome": "1", "cpf": "123.456.789-01"},
        )
        html = self.client.get(self._url("assinatura_assinar", self.token, "rt")).content.decode()

        for element_id in ("asgn-prev", "asgn-next", "asgn-open-builder", "asgn-submit"):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', html)

    def test_a_aba_escolhida_se_marca_pelo_aria_pressed(self):
        """A folha do toggle v2 pinta `[aria-pressed="true"]`, não `.is-active`.

        Enquanto o script trocava a classe, as duas abas ficavam com a mesma cara
        o tempo todo — trocar de aba funcionava e não se via.
        """
        self.client.post(
            self._url("assinatura_identidade", self.token, "rt"),
            {"confirma_nome": "1", "cpf": "123.456.789-01"},
        )
        html = self.client.get(self._url("assinatura_assinar", self.token, "rt")).content.decode()

        self.assertIn('data-tab="fonte"', html)
        self.assertIn('aria-pressed="true"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertNotIn("is-active", html)

    def test_o_selo_de_progresso_traz_os_dois_numeros(self):
        self.client.post(
            self._url("assinatura_identidade", self.token, "rt"),
            {"confirma_nome": "1", "cpf": "123.456.789-01"},
        )
        html = self.client.get(self._url("assinatura_assinar", self.token, "rt")).content.decode()

        self.assertIn("1 de 1", html)
