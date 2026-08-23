"""A cor de um botão é da FUNÇÃO dele, e é a mesma em toda tela.

Regra do dono (2026-08-20): quem varre um menu deve reconhecer "baixar PDF"
pela cor antes de ler o rótulo, e a cor não pode mudar de tela para tela nem de
tema para tema.

O que havia antes não era uma escolha, era o acúmulo: medido no navegador,
quatro das sete funções saíam douradas — `preview` e `edit` nem existiam no CSS
e caíam no accent — e baixar DOCX tinha exatamente a mesma cor de cancelar. A
mesma função também mudava de cor conforme a tela: "Baixar PDF" aparecia com
`icon_tone="late"` em cinco lugares e `icon_tone="pdf"` em quatro.

Estes testes fixam as duas metades da regra: o vocabulário é fechado, e cada
função usa sempre o mesmo tom.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


RAIZ = Path(__file__).resolve().parents[2]
TEMPLATES = RAIZ / "templates"

# O vocabulário canônico. `edit` e `neutral` seguem o accent; `whatsapp` é um
# tom de canal e permanece estável entre temas.
TONS_VALIDOS = {
    "view", "pdf", "docx", "attach", "cancel", "amend", "delete", "edit", "neutral",
    "whatsapp",
}

# Título do item → tom que ele DEVE usar, em qualquer tela.
TOM_POR_FUNCAO = {
    "Visualizar": "view",
    "Baixar PDF": "pdf",
    "Baixar PDFs": "pdf",
    "Relatório técnico": "pdf",
    "Diário de bordo": "pdf",
    "Anexo completo": "pdf",
    "Baixar DOCX": "docx",
    "Baixar DOCXs": "docx",
    "Editar": "edit",
}

_ITEM = re.compile(r'title="([^"]+)"[^>]*?icon_tone="([a-z]+)"', re.S)
_TOM = re.compile(r'icon_tone="([a-z]+)"')


def _itens_dos_templates():
    for caminho in sorted(TEMPLATES.rglob("*.html")):
        texto = caminho.read_text(encoding="utf-8")
        for titulo, tom in _ITEM.findall(texto):
            yield caminho.relative_to(RAIZ).as_posix(), titulo, tom


class CorPorFuncaoTests(SimpleTestCase):
    def test_todo_tom_de_icone_esta_no_vocabulario(self):
        """Nenhum item usa nome do vocabulário ANTIGO, que falava de estado.

        `late`, `progress`, `success`, `warning`, `info`, `preview` e `danger`
        continuam funcionando como apelido no CSS — um esquecido em algum canto
        recebe a cor certa da função em vez de cair no accent em silêncio. Mas
        não podem ser escritos em chamada nova: o nome do tom é o que diz qual é
        a função, e "late" não diz nada sobre baixar um PDF.
        """
        fora = {
            (arquivo, tom)
            for caminho in sorted(TEMPLATES.rglob("*.html"))
            for arquivo in [caminho.relative_to(RAIZ).as_posix()]
            for tom in _TOM.findall(caminho.read_text(encoding="utf-8"))
            if tom not in TONS_VALIDOS
        }
        self.assertEqual(fora, set(), f"tons fora do vocabulário por função: {sorted(fora)}")

    def test_a_mesma_funcao_usa_sempre_o_mesmo_tom(self):
        divergentes = []
        for arquivo, titulo, tom in _itens_dos_templates():
            for prefixo, esperado in TOM_POR_FUNCAO.items():
                if titulo == prefixo or titulo.startswith(prefixo + " "):
                    if tom != esperado:
                        divergentes.append(f"{arquivo}: {titulo!r} usa {tom!r}, deveria usar {esperado!r}")
                    break
        self.assertEqual(divergentes, [], "\n".join(divergentes))

    def test_a_familia_de_cor_por_funcao_existe_e_nao_muda_com_o_tema(self):
        tokens = (RAIZ / "static/css/v2/tokens.css").read_text(encoding="utf-8")
        for nome in ("view", "pdf", "docx", "attach", "cancel", "amend", "delete"):
            self.assertIn(f"--action-{nome}:", tokens)
        # Declaradas UMA vez só: uma segunda declaração dentro do bloco do tema
        # escuro seria a cor mudando com o tema, que é o que a regra proíbe.
        #
        # O corte é no SELETOR do bloco, e não na primeira menção ao tema: o
        # arquivo cita `html[data-theme="dark"]` em comentário bem antes de
        # abrir o bloco, e cortar ali devolvia o arquivo quase inteiro — o
        # teste reprovava dizendo que a cor mudava com o tema quando ela está
        # declarada uma vez só, no `:root`.
        abertura = ':is(html[data-theme="dark"]) {'
        self.assertIn(abertura, tokens)
        bloco_escuro = tokens[tokens.index(abertura):]
        for nome in ("view", "pdf", "docx", "attach", "cancel", "amend", "delete"):
            self.assertNotIn(f"--action-{nome}:", bloco_escuro)
        self.assertEqual(tokens.count("--channel-whatsapp:"), 1)
        self.assertNotIn("--channel-whatsapp:", bloco_escuro)

    def test_excluir_pinta_rotulo_e_icone(self):
        """Vermelho no rótulo é do destrutivo; vermelho no ícone é do PDF.

        Os dois dividem a cor sem ambiguidade porque estão em canais
        diferentes — mas o excluir precisa dos DOIS, senão sai com rótulo
        vermelho e ícone dourado, que foi o que a primeira versão desta mudança
        produziu.
        """
        css = (RAIZ / "static/css/v2/menu.css").read_text(encoding="utf-8")
        corpo = (TEMPLATES / "cotton/v2/menu_body.html").read_text(encoding="utf-8")
        self.assertIn('.menu__item[data-tone="delete"]', css)
        self.assertIn('class="menu__icon" data-tone="delete"', corpo)
        self.assertIn("color: var(--action-delete);", css)
