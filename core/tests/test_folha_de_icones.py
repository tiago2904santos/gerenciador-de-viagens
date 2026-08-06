"""A folha de símbolos de ícone tem que estar onde os ícones estão (`PF-01`).

`icon.html` deixou de desenhar o ícone: ele aponta para um `<symbol>` de
`components/ui/icons/_sprite.html`. O ganho é grande — na lista de Ofícios, 380
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
FOLHA = RAIZ / "components/ui/icons/_sprite.html"
ICONE = "components/ui/icons/icon.html"
FOLHA_REL = "components/ui/icons/_sprite.html"

SIMBOLO = re.compile(r'<symbol id="cv-icon-([^"]+)"')
REFERENCIA = re.compile(r'{%\s*(?:include|extends)\s+"([^"]+)"')
# `include ... with icon="edit"`, e também o `icon="edit"` de um `with` de bloco.
ICONE_LITERAL = re.compile(r'\bicon=(?:"([a-z0-9-]+)"|\'([a-z0-9-]+)\')')


def _templates() -> dict[str, str]:
    return {
        str(p.relative_to(RAIZ)).replace("\\", "/"): p.read_text(encoding="utf-8-sig")
        for p in RAIZ.rglob("*.html")
    }


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
        vizinhos = REFERENCIA.findall(textos.get(atual, "")) + estende.get(atual, [])
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

    def test_o_template_do_icone_passa_pelo_filtro(self):
        saida = engines["django"].get_template(ICONE).render({"icon": "nao-existe"})

        self.assertIn(f'href="#cv-icon-{DESCONHECIDO}"', saida)
        self.assertNotIn("cv-icon-nao-existe", saida)

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

        Existem 9 raízes de documento no projeto (`<html>` próprio, sem `extends`).
        Duas alcançam `icon.html`: `base.html` e a página de espera da geração
        documental, que é servida dentro de um iframe e por isso não passa pela
        base. Uma terceira raiz nasce muda se alguém esquecer o include.
        """
        textos = _templates()
        raizes = [
            nome
            for nome, texto in textos.items()
            if "<html" in texto.lower() and not re.search(r"{%\s*extends", texto)
        ]
        self.assertTrue(raizes, "nenhuma raiz de documento encontrada")

        sem_folha = []
        com_icone = []
        for raiz in raizes:
            alcance = _alcance(raiz, textos)
            if ICONE not in alcance:
                continue
            com_icone.append(raiz)
            if not any(FOLHA_REL in textos[t] for t in alcance):
                sem_folha.append(raiz)

        self.assertEqual(sem_folha, [], "raiz de documento com ícone e sem a folha")
        self.assertEqual(
            sorted(com_icone),
            ["base.html", "documentos/geracao_aguarde_embedded.html"],
            "mudou o conjunto de raízes que usam ícone; confira se a nova carrega "
            "a folha antes de atualizar esta lista",
        )
