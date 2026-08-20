"""A folha de símbolos de ícone tem que estar onde os ícones estão (`PF-01`).

`icon.html` deixou de desenhar o ícone: ele aponta para um `<symbol>` de
`cotton/ui/icons/_sprite.html`. O ganho é grande — na lista de Ofícios, 380
ícones caíram de 192,6 KB para 59,0 KB, e a página de 450,4 KB para 315,3 KB —
mas o modo de falha mudou de lugar, e piorou:

* **Antes**, um nome de ícone errado caía no `{% templatetag openblock %}else{% templatetag closeblock %}`
  da cadeia de condições e desenhava uma interrogação. **Agora**, um `href`
  apontando para `id` inexistente não desenha nada e não levanta erro.
* **Antes**, o desenho vinha junto com a inclusão. **Agora**, se a folha não
  estiver na página, *nenhum* ícone desenha — e, de novo, sem erro.

Nenhuma das duas falhas é visível em teste de status 200. Estas são as redes.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import SimpleTestCase

from core.templatetags.icones import APELIDOS
from core.templatetags.icones import DESCONHECIDO
from core.templatetags.icones import ICONES
from core.templatetags.icones import nome_de_icone

RAIZ = Path(settings.BASE_DIR) / "templates"
FOLHA = RAIZ / "cotton/v2/sprite.html"
#: O ícone é uma TAG desde 2026-08-19 — o componente Cotton que fazia o mesmo
#: trabalho foi apagado com o resto do legado. O que se procura num template
#: para saber se ele desenha ícone é a chamada da tag.
ICONE_TAG = "{% icone_svg"
FOLHA_REL = "cotton/v2/sprite.html"

SIMBOLO = re.compile(r'<symbol id="cv-icon-([^"]+)"')
REFERENCIA = re.compile(r'{%\s*(?:include|extends)\s+"([^"]+)"')
COTTON_REFERENCIA = re.compile(r"<c-([\w.-]+)")
# `include ... with icon="edit"`, e também o `icon="edit"` de um `with` de bloco.
ICONE_LITERAL = re.compile(r'(?<!:)\bicon=(?:"([a-z0-9-]+)"|\'([a-z0-9-]+)\')')


def _templates() -> dict[str, str]:
    return {
        str(p.relative_to(RAIZ)).replace("\\", "/"): p.read_text(encoding="utf-8-sig")
        for p in RAIZ.rglob("*.html")
    }


def _sem_comentarios(texto: str) -> str:
    """O texto sem o corpo dos `{% comment %}`.

    A galeria de tipografia EXPLICA que o provador reescreve `--font-sans` no
    `<html>`, e a palavra dentro do comentário fazia o fragmento passar por raiz
    de documento (2026-08-19). Raiz é quem TEM a tag, não quem a menciona.
    """
    return re.sub(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", "", texto, flags=re.S)


def _alcance(raiz: str, textos: dict[str, str]) -> set[str]:
    """Tudo que participa da renderização de uma raiz de documento.

    Desce pelos `include` e sobe pelos `extends`: um filho que estende `base.html`
    injeta o conteúdo dele *dentro* da página da base, então os `include` do filho
    contam para o alcance da base.
    """
    estende: dict[str, list[str]] = {}
    for nome, texto in textos.items():
        for alvo in REFERENCIA.findall(texto):
            if re.search(r'{%\s*extends\s+"' + re.escape(alvo) + '"', texto):
                estende.setdefault(alvo, []).append(nome)

    visto = {raiz}
    fila = [raiz]
    while fila:
        atual = fila.pop()
        texto = textos.get(atual, "")
        cotton = [
            "cotton/" + nome.replace(".", "/").replace("-", "_") + ".html"
            for nome in COTTON_REFERENCIA.findall(texto)
            if nome not in {"vars", "slot"}
        ]
        vizinhos = REFERENCIA.findall(texto) + cotton + estende.get(atual, [])
        for vizinho in vizinhos:
            if vizinho in textos and vizinho not in visto:
                visto.add(vizinho)
                fila.append(vizinho)
    return visto


class FolhaDeIconesTests(SimpleTestCase):
    def test_a_folha_e_a_tupla_dizem_a_mesma_coisa(self):
        simbolos = set(SIMBOLO.findall(FOLHA.read_text(encoding="utf-8")))
        esperados = set(ICONES) | {DESCONHECIDO}

        self.assertEqual(
            simbolos - esperados, set(), "símbolo na folha que a tupla não conhece"
        )
        self.assertEqual(
            esperados - simbolos, set(), "nome na tupla sem símbolo na folha"
        )

    def test_todo_apelido_aponta_para_um_nome_canonico(self):
        for apelido, canonico in APELIDOS.items():
            with self.subTest(apelido=apelido):
                self.assertIn(canonico, ICONES)
                self.assertNotIn(apelido, ICONES, "apelido e canônico ao mesmo tempo")

    def test_nome_desconhecido_vira_interrogacao_e_nao_buraco(self):
        for entrada in ("naoexiste", "", None, "  "):
            with self.subTest(entrada=entrada):
                self.assertEqual(nome_de_icone(entrada), DESCONHECIDO)

    def test_a_tag_passa_pelo_filtro(self):
        saida = engines["django"].from_string(
            '{% load icones %}{% icone_svg "nao-existe" %}'
        ).render()

        self.assertIn(f'href="#cv-icon-{DESCONHECIDO}"', saida)
        self.assertNotIn("cv-icon-nao-existe", saida)

    def test_a_tag_emite_o_invólucro_do_sistema(self):
        """O `<svg class="icon">` com `use` — a forma que as folhas dimensionam."""
        saida = engines["django"].from_string(
            '{% load icones %}{% icone_svg "delete" %}'
        ).render()

        self.assertHTMLEqual(
            saida,
            '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" '
            'focusable="false"><use href="#cv-icon-trash"></use></svg>',
        )

    def test_todo_nome_literal_usado_em_template_tem_simbolo(self):
        orfaos = []
        for nome, texto in _templates().items():
            if nome == FOLHA_REL:
                continue
            for grupo in ICONE_LITERAL.findall(texto):
                literal = grupo[0] or grupo[1]
                if nome_de_icone(literal) == DESCONHECIDO and literal != DESCONHECIDO:
                    orfaos.append(f"{nome}: icon={literal!r}")

        self.assertEqual(orfaos, [], "nome de ícone que não desenha nada")

    def test_toda_raiz_de_documento_que_usa_icone_carrega_a_folha(self):
        """A rede que importa: faltar a folha não levanta erro, só apaga o ícone.

        Três raízes desenham ícone: `base.html`, o login — que tem casca própria,
        sem sidebar — e a página de espera da geração documental, servida dentro
        de um iframe e por isso fora da base. As três incluem a folha; a quarta
        que aparecer nasce muda se alguém esquecer o include.

        O login entrou nesta lista em 2026-08-19: ele sempre desenhou ícone, mas
        a busca anterior olhava só quem alcançava o COMPONENTE `icon.html`, e o
        login já usava a tag.

        A casca pública da assinatura entrou em 2026-08-20, e é a QUARTA: ela
        não estende `base.html` porque quem a abre é o signatário externo, sem
        login e sem barra lateral. Ela passou a desenhar ícone quando a tela
        migrou para os componentes do v2, e declara `<c-v2.sprite />` no topo do
        `<body>` — conferido antes de entrar aqui, que é o que a mensagem do
        assert abaixo manda fazer.
        """
        textos = _templates()
        raizes = [
            nome
            for nome, texto in textos.items()
            if "<html" in _sem_comentarios(texto).lower()
            and not re.search(r"{%\s*extends", texto)
        ]
        self.assertTrue(raizes, "nenhuma raiz de documento encontrada")

        sem_folha = []
        com_icone = []
        for raiz in raizes:
            alcance = _alcance(raiz, textos)
            if not any(ICONE_TAG in textos.get(nome, "") for nome in alcance):
                continue
            com_icone.append(raiz)
            if FOLHA_REL not in alcance:
                sem_folha.append(raiz)

        self.assertEqual(sem_folha, [], "raiz de documento com ícone e sem a folha")
        self.assertEqual(
            sorted(com_icone),
            [
                "base.html",
                "core/login.html",
                "documentos/geracao_aguarde_embedded.html",
                "prestacoes_contas/assinatura/base_publico.html",
            ],
            "mudou o conjunto de raízes que usam ícone; confira se a nova carrega "
            "a folha antes de atualizar esta lista",
        )
