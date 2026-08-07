"""`HT-06` — nenhum componente de `templates/components/` fica sem quem o renderize.

**As duas auditorias contaram 10 e 14 de 96 porque usavam critérios diferentes**, e a
divergência era exatamente sobre o laboratório: uma contava como vivo o componente
alcançável sob `DEBUG`, a outra não. A medição por arquivo (`AGENTS.md` §3.6)
separou os casos e mostrou que existem **três** situações, não duas:

| situação | quantos | o que foi feito |
|---|---:|---|
| nenhum citador em lugar nenhum | 5 | apagados |
| citado só por um teste que afirma a **ausência** dele | 1 | apagado |
| órfão **em cascata**, revelado pelos anteriores | 1 | apagado |
| alcançável a partir do UI Lab, sob `DEBUG` | 7 | **mantidos** — ver abaixo |

A cascata é a razão de a regra valer mais que a lista: `lists/list_filters.html` só
era citado por `lists/main_list_card.html`, e virou órfão no instante em que o outro
saiu. Quem contasse uma vez e apagasse a lista deixaria este para trás — quem roda a
regra depois de apagar, não.

Os 7 do laboratório não são decisão desta etapa. Apagá-los é decidir para que serve
o UI Lab, e existem **dois** labs concorrentes sem regra de qual é o vigente — é o
`BE-17`. Ficam listados aqui, nominalmente, para que a decisão seja de um passo.

A trava é sobre a **regra**, não sobre a lista: componente novo que ninguém renderiza
reprova aqui, e componente que perde o último consumidor também.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
COMPONENTES = RAIZ / "templates/components"

#: Onde procurar por quem renderiza um componente. `templates/` e `static/` pegam
#: include e JS; os pacotes Python pegam `render()`, `render_to_string()` e o
#: template passado por variável (`body_template`, `card_template`).
ONDE_PROCURAR = [
    "templates", "static", "core", "cadastros", "oficios", "roteiros", "eventos",
    "termos", "justificativas", "planos_trabalho", "ordens_servico",
    "prestacoes_contas", "usuarios", "documentos", "google_drive",
    "config", "scripts",
]

#: Vazio desde 07/08, e o vazio é o ponto.
#:
#: O `HT-06` criou esta lista com sete componentes que só o laboratório renderizava,
#: e disse que sair daqui exigia decidir qual dos dois labs era o vigente — decisão
#: do `BE-17`, não um grep.
#:
#: A decisão veio, e foi apagar os dois labs. Com eles, os sete ficaram sem nenhum
#: renderizador e foram apagados também. A lista fica aqui, vazia, porque o dia em
#: que alguém precisar reabri-la é o dia em que um componente voltou a existir sem
#: quem o renderize — e é bom que isso doa.
SO_NO_LABORATORIO: dict[str, str] = {}


def citadores(rel_templates: str) -> list[str]:
    """Arquivos que mencionam o caminho do componente, tirando ele mesmo."""
    saida = subprocess.run(
        ["grep", "-rl", "--", rel_templates, *ONDE_PROCURAR],
        capture_output=True, text=True, cwd=RAIZ,
    ).stdout.split()
    return sorted(
        x for x in saida
        if not x.endswith(rel_templates)
        and "__pycache__" not in x
        and "bundle" not in x
    )


def e_teste(caminho: str) -> bool:
    return "/tests/" in caminho or Path(caminho).name.startswith("test_")


class NenhumComponenteOrfaoTests(SimpleTestCase):
    def componentes(self) -> list[str]:
        return sorted(
            p.relative_to(COMPONENTES).as_posix() for p in COMPONENTES.rglob("*.html")
        )

    def test_todo_componente_tem_quem_o_renderize(self):
        """Órfão de verdade: ninguém cita, nem produção, nem lab, nem teste."""
        orfaos = [
            rel for rel in self.componentes()
            if not citadores(f"components/{rel}")
        ]

        self.assertEqual(orfaos, [], "componente que ninguém renderiza")

    def test_nenhum_componente_vive_so_de_teste(self):
        """`main_list_card.html` era isto, e o teste afirmava a **ausência** dele.

        Um componente cujo único vestígio no repositório é um teste não está em uso:
        está sendo mantido vivo pela própria prova de que não é usado.
        """
        so_de_teste = [
            rel for rel in self.componentes()
            if (cit := citadores(f"components/{rel}")) and all(e_teste(x) for x in cit)
        ]

        self.assertEqual(so_de_teste, [], "componente citado só por teste")

    def test_a_lista_do_laboratorio_esta_correta(self):
        """Exceção que ninguém confere vira permissão.

        Se um destes ganhar consumidor de produção, sai da lista; se perder o do lab,
        vira órfão e cai na primeira regra. Nos dois casos, a lista mente antes de
        alguém perceber — a não ser que ela seja conferida, que é o que isto faz.
        """
        for rel in sorted(SO_NO_LABORATORIO):
            with self.subTest(componente=rel):
                caminho = COMPONENTES / rel
                self.assertTrue(caminho.exists(), "componente da lista não existe mais")

                cit = citadores(f"components/{rel}")
                self.assertTrue(cit, "perdeu o último citador — vire órfão ou saia da lista")

                de_producao = [
                    x for x in cit
                    if not e_teste(x)
                    and "dev/ui_lab" not in x
                    and "ui_lab2" not in x
                ]
                self.assertEqual(
                    de_producao, [],
                    "ganhou consumidor de produção — tire da lista do laboratório",
                )

    def test_os_apagados_do_HT06_nao_voltaram(self):
        """Sete arquivos, com a prova por arquivo que o `AGENTS.md` §3.6 exige."""
        apagados = [
            "perfil/gdrive_card.html",
            "perfil/partials/_gdrive_card_header_meta.html",
            "ui/filters/advanced_filters.html",
            "ui/filters/search_input.html",
            "ui/lists/list_card_actions.html",
            "lists/main_list_card.html",
            "lists/list_filters.html",  # órfão em cascata do anterior
        ]

        for rel in apagados:
            with self.subTest(componente=rel):
                self.assertFalse((COMPONENTES / rel).exists())

    def test_a_varredura_esta_achando_os_componentes(self):
        """Sem isto, as regras acima passariam com a pasta vazia.

        Piso de 85 para 83 em 07/08: a remoção dos dois UI Labs deixou sete
        componentes sem renderizador, e `cards/document_card.html` em cascata —
        o único que o renderizava era `lists/list_grid.html`, um dos sete.
        """
        self.assertGreaterEqual(len(self.componentes()), 83)
