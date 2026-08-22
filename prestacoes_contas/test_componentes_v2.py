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
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase
from django.test import TestCase

from prestacoes_contas.forms import DiarioBordoTrechoForm


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
    def test_campos_de_km_do_diario_usam_input_v2(self):
        form = DiarioBordoTrechoForm()

        self.assertEqual(form.fields["km_inicial"].widget.attrs["class"], "input__control")
        self.assertEqual(form.fields["km_final"].widget.attrs["class"], "input__control")

    def test_documentos_da_prestacao_usam_componentes_globais_v2(self):
        equipe = marcacao(PRESTACOES / "partials" / "_docs_equipe_body.html")
        documento = marcacao(PRESTACOES / "partials" / "_docs_attach_card.html")

        self.assertIn("<c-v2.person_row", equipe)
        self.assertIn(":field=\"servidor.form.numero_solicitacao\"", equipe)
        self.assertIn(":input=\"True\"", equipe)
        self.assertNotIn("oficio-documentos-traveller", equipe)
        self.assertNotIn("oficio-documentos-fact", equipe)

        self.assertIn("<c-v2.document_inline", documento)
        self.assertIn("<c-v2.attach_signed_button", documento)
        self.assertNotIn("icon-btn--sign", documento)
        self.assertNotIn("oficio-documentos-traveller", documento)

    def test_identificacao_administrativa_usa_fatos_globais_v2(self):
        source = marcacao(PRESTACOES / "partials" / "_rt_identificacao_body.html")

        self.assertIn(
            'class="fact-list fact-list--band-4 prestacao-identificacao-facts"',
            source,
        )
        self.assertEqual(source.count("<c-v2.form_block"), 4)
        self.assertEqual(source.count('surface="rail"'), 4)
        self.assertEqual(source.count("<c-v2.fact"), 4)
        self.assertNotIn("oficio-documentos-admin-facts", source)
        self.assertNotIn("oficio-documentos-facts", source)
        self.assertNotIn("oficio-documentos-fact", source)

    def test_resumo_do_motorista_usa_fatos_globais_v2(self):
        source = marcacao(PRESTACOES / "partials" / "_diario_motorista_body.html")
        wizard = marcacao(PRESTACOES / "partials" / "_diario_wizard_body.html")

        self.assertIn('class="fact-list fact-list--band-2 diario-motorista-facts"', source)
        self.assertEqual(source.count("<c-v2.form_block"), 2)
        self.assertEqual(source.count('surface="rail"'), 2)
        self.assertIn('<c-v2.fact label="Motorista"', source)
        self.assertIn('<c-v2.fact label="Origem do motorista"', source)
        self.assertIn('title="Motorista" description="Motorista efetivo deste diário"', wizard)
        self.assertIn('label="Alterado" tone="warning"', source)
        self.assertNotIn("oficio-documentos-admin-facts", source)
        self.assertNotIn("oficio-documentos-facts", source)
        self.assertNotIn('class="diario-motorista-fact"', source)

    def test_trechos_do_diario_reutilizam_a_composicao_v2_do_roteiro(self):
        corpo = marcacao(PRESTACOES / "partials" / "_diario_trecho_body.html")
        wizard = marcacao(PRESTACOES / "partials" / "_diario_wizard_body.html")

        self.assertIn('extra_class="roteiro-trecho-card route-leg diario-trecho-block"', wizard)
        self.assertIn(':description="d.rota"', wizard)
        self.assertIn('class="route-return__legs"', corpo)
        self.assertEqual(corpo.count('class="route-return__leg"'), 2)
        self.assertIn('<span class="route-return__leg-title">Saída</span>', corpo)
        self.assertIn('label="Cidade de saída"', corpo)
        self.assertIn('label="Cidade de chegada"', corpo)
        self.assertIn('class="route-return__times"', corpo)
        self.assertIn(':field="form.km_inicial"', corpo)
        self.assertIn(':field="form.km_final"', corpo)
        self.assertIn(':field="form.abastecimento"', corpo)
        self.assertNotIn("cv-field", corpo)
        self.assertNotIn("roteiro-trecho-card__route-row", corpo)

    def test_footer_do_relatorio_usa_rodape_global_sem_divisor(self):
        source = marcacao(PRESTACOES / "partials" / "_rt_downloads_footer.html")

        self.assertIn("<c-v2.card_footer>", source)
        self.assertNotIn("card-footer-section", source)
        self.assertNotIn("card-footer-section__divider", source)

    def test_preview_do_relatorio_nao_expoe_ajuste_manual_de_diaria(self):
        source = marcacao(PRESTACOES / "partials" / "_rt_downloads_body.html")

        self.assertNotIn("diaria_form", source)
        self.assertNotIn("diaria_valor_override", source)
        self.assertNotIn("rt-diaria-override-field", source)

    def test_textareas_do_relatorio_usam_controle_global_v2(self):
        from prestacoes_contas.forms import CAMPOS_COM_MODELO
        from prestacoes_contas.forms import RelatorioTecnicoForm

        source = marcacao(PRESTACOES / "_campo_com_modelo.html")
        form = RelatorioTecnicoForm()

        self.assertIn(':field="c.textarea" :label="c.label" :input="True"', source)
        for campo, _label in CAMPOS_COM_MODELO:
            classes = form.fields[campo].widget.attrs.get("class", "").split()
            self.assertIn("input__control", classes)
            self.assertIn("input__control--textarea", classes)
            self.assertNotIn("cv-field__control--textarea", classes)

    def test_inputs_de_custeio_do_relatorio_usam_controle_global_v2(self):
        from prestacoes_contas.forms import RelatorioTecnicoForm

        form = RelatorioTecnicoForm()
        for campo in ("diaria", "translado_outro", "combustivel_outro", "passagem_outro"):
            classes = form.fields[campo].widget.attrs.get("class", "").split()
            self.assertEqual(classes, ["input__control"])
            self.assertNotIn("form-control", classes)
            self.assertNotIn("cv-field__control", classes)

    def test_inputs_condicionais_de_custeio_nao_repetem_rotulo_visual(self):
        source = marcacao(PRESTACOES / "partials" / "_rt_custeio_body.html")

        self.assertIn(
            ':field="item.other" :label="cotton_attr_label" :input="True" :hide_label="True"',
            source,
        )

    def test_modelos_do_relatorio_usam_select_com_acao_v2(self):
        campo = marcacao(PRESTACOES / "_campo_com_modelo.html")
        wizard = marcacao(PRESTACOES / "partials" / "_rt_wizard_body.html")

        self.assertIn(':action_url="c.manage_url"', campo)
        self.assertIn('action_label="Gerenciar modelos"', campo)
        self.assertIn(':hide_label="True"', campo)
        self.assertNotIn("Nenhum modelo cadastrado para este campo", campo)
        self.assertNotIn("Cadastrar modelo", campo)
        self.assertNotIn('action_label="Gerenciar modelos"', wizard)

    def test_custeios_do_relatorio_usam_controles_globais_v2(self):
        source = marcacao(PRESTACOES / "partials" / "_rt_custeio_body.html")

        self.assertIn(':select="True"', source)
        self.assertIn(':input="True"', source)
        self.assertNotIn(':label="item.label" only', source)

    def test_equipe_do_relatorio_usa_linhas_de_pessoa_v2(self):
        source = marcacao(PRESTACOES / "partials" / "_rt_equipe_body.html")

        self.assertIn('class="person-list"', source)
        self.assertIn("<c-v2.person_row", source)
        self.assertNotIn("oficio-documentos-traveller-tile", source)
        self.assertNotIn("oficio-documentos-travellers-grid", source)
        self.assertNotIn("oficio-documentos-card--travellers", source)

    def test_periodo_do_resumo_omite_o_ano_repetido_na_data_inicial(self):
        from prestacoes_contas.view_common import _periodo_display

        oficio = SimpleNamespace(
            roteiro=SimpleNamespace(
                saida_dt=datetime(2026, 8, 17, 8),
                retorno_chegada_dt=datetime(2026, 8, 23, 15, 45),
            )
        )

        self.assertEqual(_periodo_display(oficio), "17/08 a 23/08/2026")

    def test_card_edita_periodo_em_calendario_compacto_com_autosave(self):
        source = marcacao(TEMPLATES / "cotton" / "v2" / "prestacao_card.html")

        inicio_form = source.index('class="prestacao-row__form"')
        fim_form = source.index("</form>", inicio_form)
        formulario_operacional = source[inicio_form:fim_form]

        self.assertNotIn("prestacao-row__period-form", source)
        self.assertIn("prestacao-row__solicitacao", formulario_operacional)
        self.assertIn('<c-v2.date_picker', formulario_operacional)
        self.assertIn('<c-v2.date_picker', source)
        self.assertIn('mode="range"', source)
        self.assertIn('button_label="Período"', source)
        self.assertIn('start_hidden_name="ps-{{ servidor.ps_pk }}-data_liberacao_diarias"', source)
        self.assertIn('end_hidden_name="ps-{{ servidor.ps_pk }}-prazo_limite_saque"', source)
        self.assertNotIn("prestacao-periodo-modal", source)

    def test_placa_e_modelo_usam_a_mesma_composicao_de_fato(self):
        source = marcacao(TEMPLATES / "cotton" / "v2" / "prestacao_card.html")

        self.assertIn('<c-v2.fact label="Placa" :value="card.veiculo_placa" />', source)
        self.assertIn('<c-v2.fact label="Modelo" :value="card.veiculo_modelo" />', source)
        self.assertNotIn(':note="card.veiculo_modelo"', source)

    def test_card_exibe_quantidade_de_diarias_no_bloco_financeiro(self):
        source = marcacao(TEMPLATES / "cotton" / "v2" / "prestacao_card.html")

        self.assertIn(
            '<c-v2.fact label="Quantidade de diárias" :value="card.quantidade_diarias_display" />',
            source,
        )

    def test_solicitacao_e_periodo_usam_a_superficie_rail(self):
        css = (ROOT / "static" / "css" / "v2" / "record.css").read_text(encoding="utf-8")
        regra = css[css.index(".prestacao-row__solicitacao") :]
        regra = regra[: regra.index("}")]
        date_picker_css = (ROOT / "static" / "css" / "v2" / "date-picker.css").read_text(encoding="utf-8")
        regra_periodo = date_picker_css[date_picker_css.index(".prestacao-row__form") :]
        regra_periodo = regra_periodo[: regra_periodo.index("}")]

        self.assertIn("background: var(--surface-rail);", regra)
        self.assertIn("flex: 0 1 120px;", regra)
        self.assertIn("max-width: 120px;", regra)
        self.assertNotIn("background: var(--surface-field);", regra)
        self.assertIn("background: var(--surface-rail);", regra_periodo)

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
        # A folha de `<symbol>` dos ícones era a ÚNICA exceção desta varredura:
        # enquanto morava em `<c-ui.icons._sprite />`, casava com o namespace
        # legado sem ser peça visual, e precisava ser descontada antes da
        # contagem. Ela passou a ser `<c-v2.sprite />` (PF-01), que não casa com
        # nenhum prefixo da lista acima — a exceção deixou de existir e a
        # varredura voltou a ser direta.
        offenders = {}
        for template in sorted(PRESTACOES.rglob("*.html")):
            source = marcacao(template)
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
        self.assertIn("<c-v2.sprite", source)

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
        permitidos = {
            "prestacoes_contas/assinatura/base_publico.html",
            # `flow_base.html` voltou a carregar `pages/prestacoes_contas.css` em
            # 2026-08-19, e o próprio template explica por quê: 18 classes que as
            # quatro etapas AINDA emitem ficaram sem desenho nenhum quando a
            # folha saiu — as caixas dos wizards, o vazio dos trechos, a faixa de
            # removidos e o campo "outro" do custeio. Foi medido. Carregá-la uma
            # vez no casco é melhor do que repeti-la em cinco telas, e ela sai de
            # vez quando as 18 virarem componente.
            "prestacoes_contas/flow_base.html",
        }
        offenders = {}
        for template in sorted(PRESTACOES.rglob("*.html")):
            # `as_posix()`, e não `str()`: no Windows o caminho sai com `\` e
            # nenhum nome do conjunto acima casa — o teste reprovava só nesta
            # plataforma, apontando um arquivo que ele mesmo permite.
            relative = template.relative_to(TEMPLATES).as_posix()
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
            "prestacoes_contas/partials/_docs_attach_trigger.html",
            "prestacoes_contas/partials/_prestacao_card_body.html",
            "prestacoes_contas/partials/_prestacao_card_footer.html",
            "prestacoes_contas/partials/prestacao_list_card.html",
            # Substituídos pelo `c-v2.document_inline` e pelo `c-v2.file_list`.
            "prestacoes_contas/partials/documento_preview.html",
            "prestacoes_contas/partials/_documento_preview_body.html",
            "prestacoes_contas/partials/documento_anexos.html",
        )
        # AINDA VIVAS, cada uma incluída por uma tela real — a lista acima só
        # pode crescer quando a tela correspondente deixar de incluí-la. Medido
        # em 2026-08-20, com o arquivo que ainda a chama ao lado:
        #
        #   _consolidado_footer   consolidado.html
        #   _diario_footer        diario_bordo_form.html
        #   _docs_footer          documentos_form.html
        #   _rt_downloads_footer  relatorio_tecnico_form.html
        #   _dmv_viatura_footer   diario_motorista_form.html
        #   _modelos_grupo_actions / _modelos_grupo_body   modelos_texto/index.html
        #
        # Elas estavam nesta tupla antes de as telas migrarem, e a catraca
        # reprovava um estado que ninguém tinha alcançado ainda. Apagá-las para
        # o teste passar quebraria as seis telas; o caminho é migrar a tela e
        # então mover o nome para cima.
        pendentes = (
            "prestacoes_contas/partials/_consolidado_footer.html",
            "prestacoes_contas/partials/_diario_footer.html",
            "prestacoes_contas/partials/_docs_footer.html",
            "prestacoes_contas/partials/_rt_downloads_footer.html",
            "prestacoes_contas/partials/_dmv_viatura_footer.html",
            "prestacoes_contas/partials/_modelos_grupo_actions.html",
            "prestacoes_contas/partials/_modelos_grupo_body.html",
        )
        existentes = [relative for relative in removidas if (TEMPLATES / relative).exists()]
        self.assertEqual(existentes, [])
        # A conta só desce: se uma pendente sumiu, ela tem de subir para
        # `removidas`, senão a catraca deixa de vigiar aquele nome.
        ainda_la = [relative for relative in pendentes if (TEMPLATES / relative).exists()]
        self.assertEqual(
            ainda_la,
            list(pendentes),
            "parcial pendente sumiu — mova o nome para `removidas`",
        )

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
