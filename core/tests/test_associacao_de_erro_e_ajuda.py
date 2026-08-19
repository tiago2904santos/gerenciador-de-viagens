"""`HT-02` e `HT-12` — o erro e a ajuda de um campo apontam para o controle.

O Django 5.2 já faz **metade** do trabalho sozinho: todo campo com erro sai com
`aria-invalid="true"` e `aria-describedby="id_X_error"`, e todo campo com
`help_text` sai com `aria-describedby="id_X_helptext"`
(`django/forms/boundfield.py:299-310`). O que faltava era o **outro lado** —
nenhum componente deste projeto emitia esses `id`. A mensagem estava na tela e o
ponteiro do navegador apontava para o vazio.

O `HT-12` é o mesmo defeito visto de frente: `field.html` imprimia apenas o
parâmetro `help_text` do `include`, nunca `field.help_text`. Vinte e nove campos
de produção declaram ajuda no form e **nenhum** a exibia — então o
`aria-describedby="id_X_helptext"` que o Django emitia era, nesses casos,
sempre quebrado.

A trava central é `referencias_quebradas()`: ela não afirma quais `id` existem,
ela exige que **todo** `aria-describedby` da página aponte para um elemento que
está lá. Campo novo entra na varredura sozinho, e componente que passe a emitir
ponteiro sem âncora é pego onde ele aparece.
"""

from __future__ import annotations

import re
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

CAMPO = "cotton/ui/forms/field.html"
RAIZ = Path(settings.BASE_DIR)

_ID = re.compile(r'\bid="([^"]+)"')
_DESCRIBEDBY = re.compile(r'aria-describedby="([^"]+)"')


def referencias_quebradas(html: str) -> list[str]:
    """Todo alvo de `aria-describedby` que não tem elemento correspondente."""
    existentes = set(_ID.findall(html))
    quebradas = []
    for grupo in _DESCRIBEDBY.findall(html):
        quebradas.extend(alvo for alvo in grupo.split() if alvo not in existentes)
    return quebradas


class FormularioDeProva(forms.Form):
    """Um campo por caminho de `_field_control.html`, mais os dois de ajuda."""

    texto = forms.CharField(help_text="Só letras.")
    sem_ajuda = forms.CharField()
    escolha = forms.ChoiceField(choices=[("a", "A")], help_text="Escolha uma.")
    varios = forms.MultipleChoiceField(choices=[("a", "A")], help_text="Pode marcar mais de uma.")
    marca = forms.BooleanField(help_text="Confirme antes de seguir.")
    html_na_ajuda = forms.CharField(help_text="<ul><li>Doze caracteres.</li></ul>")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["busca"] = forms.ChoiceField(
            choices=[("a", "A")],
            help_text="Busque e selecione.",
            widget=forms.Select(attrs={"class": "search-picker__native"}),
        )


def renderiza(campo, **extras) -> str:
    return render_to_string(CAMPO, {"field": campo, **extras})


class AjudaDoCampoTests(SimpleTestCase):
    """`HT-12` — o `help_text` do form chega à tela, e com âncora."""

    def test_a_ajuda_declarada_no_form_aparece(self):
        html = renderiza(FormularioDeProva()["texto"])

        self.assertIn("Só letras.", html)

    def test_a_ajuda_leva_o_id_que_o_django_referencia(self):
        campo = FormularioDeProva()["texto"]
        self.assertEqual(campo.aria_describedby, "id_texto_helptext")

        html = renderiza(campo)

        self.assertIn('id="id_texto_helptext"', html)
        self.assertEqual(referencias_quebradas(html), [])

    def test_campo_sem_ajuda_nao_ganha_paragrafo(self):
        """A metade que impede o `<p>` vazio em 125 dos 154 campos."""
        html = renderiza(FormularioDeProva()["sem_ajuda"])

        self.assertNotIn("field-help", html)
        self.assertNotIn("_helptext", html)

    def test_o_parametro_do_include_ainda_vence_o_do_form(self):
        """Dois chamadores trocam a ajuda por uma frase da tela deles."""
        html = renderiza(FormularioDeProva()["texto"], help_text="Frase da tela.")

        self.assertIn("Frase da tela.", html)
        self.assertNotIn("Só letras.", html)

    def test_ajuda_com_html_sai_como_html(self):
        """`UsuarioAreaCreationForm.password1` é `<ul><li>…` — do próprio Django.

        Sem `|safe` a tela do administrador mostraria a marcação como texto. É o
        mesmo `|safe` que `django/forms/div.html` usa.
        """
        html = renderiza(FormularioDeProva()["html_na_ajuda"])

        self.assertIn("<li>Doze caracteres.</li>", html)
        self.assertNotIn("&lt;li&gt;", html)

    def test_a_ajuda_mora_num_elemento_que_aceita_bloco(self):
        """A ajuda saía num `<p>`, e o teste acima passava assim mesmo.

        Lista dentro de parágrafo é HTML inválido: o navegador **fecha o `<p>`
        antes da `<ul>`**. Medido em `/usuarios/` com Chromium — o elemento
        `id="…_helptext"` ficava vazio (`children: 0`, texto vazio) e a `<ul>` era
        irmã dele, a 16px em vez de 14px. O `aria-describedby` apontava para um
        elemento sem texto, que é pior do que não apontar.

        Décima segunda vez nesta etapa que um teste meu passava sem provar o que
        dizia, e a primeira em que quem pegou foi o navegador. **A asserção é sobre
        o nome do elemento de propósito:** o Django emite exatamente o que está
        escrito no template, então nenhuma checagem sobre a string renderizada
        enxerga o fechamento implícito — só o navegador enxerga. O que dá para
        travar aqui é a escolha do container, e é o que está travado.
        """
        html = renderiza(FormularioDeProva()["html_na_ajuda"])

        self.assertRegex(
            html, r'<div class="field-help app-form-help" id="id_html_na_ajuda_helptext">',
            "a ajuda voltou para um elemento que não aceita conteúdo de bloco",
        )

    def test_a_ajuda_do_checkbox_chega_ao_cartao(self):
        """Checkbox sai por `card_toggle.html`, que recebe a ajuda como `description`."""
        html = renderiza(FormularioDeProva()["marca"])

        self.assertIn("Confirme antes de seguir.", html)
        self.assertIn('id="id_marca_helptext"', html)
        self.assertEqual(referencias_quebradas(html), [])

    def test_a_ajuda_do_checkbox_tambem_sai_como_html(self):
        """Os dois caminhos escapam igual, ou a divergência aparece no dia da mudança.

        Nenhum checkbox de produção declara `help_text` com marcação hoje. A trava
        não é para o caso existente: é para o dia em que alguém mover um `help_text`
        de campo de texto para um `BooleanField` e a tela mostrar `&lt;li&gt;`.
        """

        class ComHtml(forms.Form):
            marca = forms.BooleanField(help_text="<b>Leia</b> antes.")

        html = renderiza(ComHtml()["marca"])

        self.assertIn("<b>Leia</b> antes.", html)
        self.assertNotIn("&lt;b&gt;", html)


class ErroDoCampoTests(SimpleTestCase):
    """`HT-02` — o erro é anunciado e está associado ao controle."""

    def campo_com_erro(self, nome: str):
        form = FormularioDeProva(data={})
        form.is_valid()
        return form[nome]

    def test_o_erro_leva_o_id_que_o_django_referencia(self):
        campo = self.campo_com_erro("sem_ajuda")
        self.assertIn("id_sem_ajuda_error", campo.aria_describedby)

        html = renderiza(campo)

        self.assertIn('id="id_sem_ajuda_error"', html)
        self.assertEqual(referencias_quebradas(html), [])

    def test_o_erro_e_anunciado(self):
        html = renderiza(self.campo_com_erro("sem_ajuda"))

        self.assertIn('role="alert"', html)

    def test_o_widget_ja_vem_marcado_como_invalido(self):
        """Metade do Django. Está aqui para pegar quem trocar `as_widget` por HTML à mão."""
        html = renderiza(self.campo_com_erro("sem_ajuda"))

        self.assertIn('aria-invalid="true"', html)

    def test_todo_caminho_de_controle_associa_o_erro(self):
        """Os quatro ramos de `_field_control.html`, mais o checkbox."""
        for nome in ("texto", "escolha", "varios", "busca", "marca"):
            with self.subTest(campo=nome):
                html = renderiza(self.campo_com_erro(nome))
                self.assertEqual(referencias_quebradas(html), [], html)

    def test_o_erro_do_checkbox_sai_pelo_mesmo_componente(self):
        """`card_toggle.html` reescrevia o `<p>` de erro por conta própria.

        A cópia divergiu na primeira tentativa desta correção: ganhou `id` e
        `role`, mas remover qualquer um dos dois **não reprovava teste nenhum** —
        décima e décima primeira vez nesta etapa que uma edição minha não era
        atribuível. A saída não foi cobrir a cópia, foi apagá-la: quem monta erro
        de campo agora é sempre `field_error.html`.
        """
        html = renderiza(self.campo_com_erro("marca"))

        self.assertIn('class="field-error app-form-error"', html)
        self.assertIn('role="alert"', html)
        self.assertIn('id="id_marca_error"', html)

    def test_campo_com_erro_e_ajuda_ancora_os_dois(self):
        campo = self.campo_com_erro("texto")
        self.assertEqual(
            campo.aria_describedby, "id_texto_helptext id_texto_error",
        )

        html = renderiza(campo)

        self.assertEqual(referencias_quebradas(html), [])

    def test_dois_erros_no_mesmo_campo_nao_se_colam(self):
        """`{{ errors|striptags }}` grudava as mensagens: `…possui 3).Só dígitos.`

        `striptags` aplicado ao `<ul>` da `ErrorList` remove as tags e não põe
        nada no lugar. Com dois validadores falhando, as duas frases viravam uma.
        """
        from django.core.validators import MinLengthValidator, RegexValidator

        class Dois(forms.Form):
            x = forms.CharField(
                validators=[MinLengthValidator(10), RegexValidator(r"^\d+$", "Só dígitos.")],
            )

        form = Dois(data={"x": "abc"})
        form.is_valid()
        self.assertEqual(len(form["x"].errors), 2)

        html = renderiza(form["x"])

        self.assertNotIn("3).Só dígitos.", html)
        self.assertIn("3). Só dígitos.", html)


_INCLUDE_DE_ERRO = re.compile(
    r'\{%\s*include\s+"components/ui/feedback/field_error\.html"\s+with\s+(?P<args>[^%]*?)%\}',
)
_COTTON_DE_ERRO = re.compile(
    r'<c-ui\.feedback\.field_error\s+(?P<args>[^>]*?)/>',
)
_ERRORS_ARG = re.compile(r'errors=(?P<valor>"[^"]*"|[^\s]+)')


def _normaliza_args_cotton(args):
    return re.sub(r':([A-Za-z_]\w*)=(["\'])(.*?)\2', r'\1=\3', args)


def chamadores_de_field_error():
    """`(arquivo, linha, expressão de errors, args)` de cada include do componente."""
    for caminho in sorted((RAIZ / "templates").rglob("*.html")):
        texto = caminho.read_text(encoding="utf-8")
        if "feedback/field_error.html" not in texto and "ui.feedback.field_error" not in texto:
            continue
        for padrao, cotton in ((_INCLUDE_DE_ERRO, False), (_COTTON_DE_ERRO, True)):
            for achado in padrao.finditer(texto):
                args = achado.group("args")
                if cotton:
                    args = _normaliza_args_cotton(args)
                valor = _ERRORS_ARG.search(args)
                linha = texto.count("\n", 0, achado.start()) + 1
                yield (
                    caminho.relative_to(RAIZ).as_posix(),
                    linha,
                    valor.group("valor") if valor else None,
                    args,
                )


class ContratoDosChamadoresTests(SimpleTestCase):
    """Os 39 sites que montam o erro à mão, e que nenhum teste de tela alcança.

    O componente sozinho não prova nada: quem escreve o `id` é o chamador, via
    `field_id`. Uma varredura estática é o único jeito de cobrir os 39 de uma vez
    — e ela cobre também o quadragésimo, que ainda não existe.
    """

    def test_todo_erro_de_campo_passa_field_id(self):
        faltando = [
            f"{arquivo}:{linha} — {valor}"
            for arquivo, linha, valor, args in chamadores_de_field_error()
            if valor
            and valor.endswith(".errors")
            and not valor.endswith(("non_field_errors", "non_form_errors"))
            and f"field_id={valor[: -len('.errors')]}.auto_id" not in args
        ]

        self.assertEqual(faltando, [], "erro de campo sem âncora para o aria-describedby")

    def test_erro_de_formulario_inteiro_nao_passa_por_aqui(self):
        """`HT-03`: erro sem campo tem componente próprio, o `form_errors.html`.

        A primeira versão desta regra dizia só "não passe `field_id` em
        `non_field_errors`" — e depois que o `HT-03` tirou os 18 chamadores ela
        ficou **vacuamente verdadeira**: nenhum caso para julgar. Regra que passa
        por falta de assunto é a mesma armadilha do parâmetro inerte. Agora ela
        proíbe o uso, que é o que o `HT-03` de fato estabeleceu.
        """
        indevidos = [
            f"{arquivo}:{linha} — {valor}"
            for arquivo, linha, valor, _ in chamadores_de_field_error()
            if valor and valor.endswith(("non_field_errors", "non_form_errors"))
        ]

        self.assertEqual(indevidos, [], "use <c-ui.feedback.form_errors>")

    def test_ninguem_passa_string_literal_em_errors(self):
        """`join` sobre string separa **caractere por caractere**.

        `striptags` engolia essa diferença; `join` não. O único chamador assim era
        a demonstração do `ui_lab2`, que agora usa um `BoundField` de verdade.
        """
        literais = [
            f"{arquivo}:{linha} — {valor}"
            for arquivo, linha, valor, _ in chamadores_de_field_error()
            if valor and valor.startswith('"')
        ]

        self.assertEqual(literais, [])

    def test_quem_inclui_card_toggle_direto_passa_description(self):
        """O buraco que sobrou, fechado por regra em vez de por fallback inerte.

        `card_toggle.html` é folha: renderiza o que recebe. Quem resolve a ajuda é
        `field.html`. Os três chamadores diretos passam `description` explícita —
        então pôr um `|default:field.help_text` no componente seria código que
        ninguém exercita. O risco real é o **quarto** chamador esquecer: aí o campo
        fica sem descrição, e se ele declarar `help_text` o Django emite um ponteiro
        para um `id` que não foi renderizado.
        """
        diretos = []
        for caminho in sorted((RAIZ / "templates").rglob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            for achado in re.finditer(
                r'(?:\{%\s*include\s+"components/ui/forms/card_toggle\.html"\s+with\s+([^%]*?)%\}'
                r'|<c-ui\.forms\.card_toggle\s+([^>]*?)/>)',
                texto,
            ):
                args = achado.group(1) or achado.group(2)
                if "description=" not in args:
                    linha = texto.count("\n", 0, achado.start()) + 1
                    diretos.append(f"{caminho.relative_to(RAIZ).as_posix()}:{linha}")

        self.assertEqual(diretos, [], "include de card_toggle sem description")

    def test_a_varredura_esta_achando_os_chamadores(self):
        """Sem isto, as regras acima passariam com a varredura vazia.

        Eram 59 chamadores; o `HT-03` levou 18 para o `form_errors.html`. O
        `NOVO-16` substituiu outros 3 chamadores duplicados por um único chamador
        dentro de `related_picker.html`, restando 38 erros de campo nos templates
        de aplicação. O número desce quando um chamador legítimo sai, e é para
        isso que ele está escrito aqui em vez de num comentário.

        2026-08-18: **36**. As telas migradas para o v2 passaram a usar
        `c-v2.form_field`, que embute o erro no próprio campo — o chamador não
        desapareceu, mudou de dono.

        2026-08-18, migração de Ofícios (`NOVO-20260818-213853-fab772ef1b6e`):
        **33**. Saíram os três chamadores da etapa 1 — identificação, finalidade
        e motorista externo —, pelo mesmo motivo: o campo do v2 já traz o erro.

        2026-08-18, migração de Planos de Trabalho
        (`NOVO-20260818-223338-aa3c31f87b9d`): **30**. Saíram os três
        últimos chamadores do app — a linha de efetivo (dois: unidade e
        quantidade) e o campo de atividades do cadastro rápido de modelos. Todos
        passaram ao `c-v2.form_field` ou ao `c-v2.field`, que trazem o erro
        embutido e emitem o `id` que o `aria-describedby` do Django aponta.

        2026-08-19, migração de Prestações de Contas (`NOVO-20260819`): **15**.
        Este é o maior corte de uma etapa só, e pelo mesmo motivo de todos os
        anteriores — Prestações era o app com mais campos escritos à mão, e o
        `c-v2.form_field` absorveu o erro de cada um. Os 15 que sobram estão nos
        apps que ainda não migraram; quando o último sair, este teste vira uma
        trava sobre o componente, não sobre os chamadores.
        """
        achados = list(chamadores_de_field_error())

        self.assertGreaterEqual(len(achados), 15)
        self.assertGreaterEqual(sum(1 for _, _, v, a in achados if "field_id=" in a), 15)


class DicaEscritaAMaoTests(SimpleTestCase):
    """`_dmv_motorista_body.html` escreve a dica à mão, fora de `field.html`.

    O texto já estava na tela; o que faltava era o `id`. Como o parcial não passa
    por `field.html`, nenhuma das travas de componente o alcança — ele é renderizado
    aqui, direto, com o form de verdade.
    """

    def test_a_dica_do_oficio_do_motorista_tem_ancora(self):
        from prestacoes_contas.forms import DiarioMotoristaForm

        form = DiarioMotoristaForm()
        self.assertTrue(
            form.fields["motorista_oficio_referencia"].help_text,
            "o campo perdeu o help_text — a âncora deixou de ser necessária",
        )

        html = render_to_string(
            "prestacoes_contas/partials/_dmv_motorista_body.html", {"form": form},
        )

        self.assertIn('id="id_motorista_oficio_referencia_helptext"', html)
        self.assertEqual(referencias_quebradas(html), [])


class TelaRealTests(TestCase):
    """A prova de que o contrato sobrevive à composição da página.

    Componente correto isolado não é página correta: `field.html` é incluído por
    154 sites e o erro de formulário inteiro entra por outro componente. Aqui a
    varredura é sobre a resposta HTTP.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin_ht02", password="123456", email="a@b.c",
        )
        self.client.force_login(self.user)

    def test_a_tela_de_criar_usuario_nao_tem_ponteiro_solto(self):
        """`password1.help_text` é a lista de regras de senha, com HTML.

        A criação é inline na lista (`usuarios/views.py:82`), com `prefix="usuario"`
        — daí o `auto_id` ser `id_usuario-password1`. É o melhor caso de tela real
        que existe para o `HT-12`: o único `help_text` de produção com marcação.
        """
        resposta = self.client.get(reverse("usuarios:index"))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()

        self.assertIn('id="id_usuario-password1_helptext"', html)
        self.assertIn("<li>Sua senha precisa conter pelo menos 12 caracteres.</li>", html)
        self.assertEqual(referencias_quebradas(html), [])

    def test_a_mesma_tela_com_erro_de_validacao(self):
        resposta = self.client.post(reverse("usuarios:index"), data={})
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()

        self.assertIn('aria-invalid="true"', html)
        self.assertIn('id="id_usuario-username_error"', html)
        self.assertEqual(referencias_quebradas(html), [])
