"""UI-03: token global nasce em dois arquivos, e só em dois.

Antes da E7 havia três arquivos definindo token global — `base/tokens.css`,
`base/theme.css` e `base/03-theme-dark.css` — mais `layout/page-shell.css`. Um
token podia nascer em qualquer um deles, e nascia: `--color-primary-dark` era
`#062847` em tokens.css e `var(--color-primary-strong)` em theme.css, e só a
ordem de carga dizia qual valia. `theme.css` foi dissolvido; este teste impede
que a terceira camada volte.

**O que a regra alcança, e o que não.** Ela vale para definição no escopo raiz —
`:root` e `html[data-theme=…]` —, que é a que muda a página inteira. Re-ligar um
token dentro de um seletor de componente continua permitido, e é permitido de
propósito: 45 regras globais leem `var(--color-input-bg)` e 10 leem
`var(--color-focus)`; um container que re-liga o nome dirige todas elas sem que
nenhuma precise conhecê-lo. Proibir isso obrigaria a duplicar as 55 regras sob
seletor de container, subindo especificidade — que é a dívida que a Fase 7 veio
pagar, não contrair.

Os quatro sites que exerciam essa permissão morreram em 2026-08-20, com os
cartões do wizard do sistema antigo. A permissão continua valendo; quando um
site voltar, ele mora no arquivo do componente que o exerce.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
CSS = ROOT / "static" / "css"

# As duas camadas oficiais: valor (e o claro) em tokens.css, a troca do escuro
# em 03-theme-dark.css.
CAMADAS = ("base/tokens.css", "base/03-theme-dark.css")

# Famílias globais. As demais (--stepper-*, --chip-*, --btn-*…) são de
# componente e seguem morando no arquivo do componente — esse padrão está certo
# e não é alvo do UI-03.
FAMILIAS = ("--color-", "--theme-")

COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
DEFINICAO = re.compile(r"^\s*(--[\w-]+)\s*:", re.M)


def _blocos(texto: str):
    """(seletor, corpo) de cada bloco de primeiro nível, comentários já fora."""
    texto = COMENTARIO.sub("", texto)
    profundidade = 0
    inicio = 0
    seletor = ""
    for i, ch in enumerate(texto):
        if ch == "{":
            if profundidade == 0:
                seletor = texto[inicio:i].strip()
            profundidade += 1
        elif ch == "}":
            profundidade -= 1
            if profundidade == 0:
                yield seletor, texto[texto.index("{", inicio) + 1 : i]
                inicio = i + 1


def _e_escopo_raiz(seletor: str) -> bool:
    """`:root` ou `html[data-theme=…]`, isolados ou numa lista de seletores."""
    for parte in seletor.split(","):
        parte = parte.strip().replace("'", '"')
        if parte == ":root" or re.fullmatch(r'html\[data-theme="[^"]+"\]', parte):
            return True
    return False


def _fontes() -> list[Path]:
    return sorted(
        p
        for p in CSS.rglob("*.css")
        if "bundle" not in p.name and p.parent != CSS / "profiles"
    )


class TokenGlobalMoraEmDuasCamadasTests(SimpleTestCase):
    def test_nenhum_arquivo_fora_das_duas_camadas_define_token_global(self):
        infratores = []
        for arquivo in _fontes():
            relativo = arquivo.relative_to(CSS).as_posix()
            if relativo in CAMADAS:
                continue
            texto = arquivo.read_text(encoding="utf-8")
            for seletor, corpo in _blocos(texto):
                if not _e_escopo_raiz(seletor):
                    continue
                for nome in DEFINICAO.findall(corpo):
                    if nome.startswith(FAMILIAS):
                        infratores.append(f"{relativo}: {nome} sob {seletor.strip()[:40]}")
        self.assertEqual(
            infratores,
            [],
            "token global fora de tokens.css/03-theme-dark.css — ver UI-03",
        )

    def test_as_duas_camadas_existem_e_o_theme_css_nao_voltou(self):
        for camada in CAMADAS:
            self.assertTrue((CSS / camada).is_file(), f"camada sumiu: {camada}")
        self.assertFalse(
            (CSS / "base" / "theme.css").exists(),
            "base/theme.css voltou — era a terceira camada que a E7 dissolveu",
        )

    def test_a_re_ligacao_com_escopo_so_acontece_em_componente(self):
        """A regra é sobre escopo raiz, não sobre o prefixo do nome.

        Re-ligar um token global dentro de um seletor de COMPONENTE continua
        permitido — é assim que um container dirige as 55 regras globais que
        leem `--color-input-bg` e `--color-focus` sem que nenhuma delas precise
        conhecê-lo.

        2026-08-20: os quatro sites que exerciam a permissão morreram junto com
        os cartões do wizard do sistema antigo (`.travel-document-card` e
        irmãos), que nenhum template emitia mais. A permissão fica; o que este
        teste guarda é o LUGAR dela — quando um site voltar, ele tem de estar no
        arquivo de um componente, nunca numa das duas camadas de token.
        """
        fora_de_lugar = []
        for arquivo in _fontes():
            relativo = arquivo.relative_to(CSS).as_posix()
            for seletor, corpo in _blocos(arquivo.read_text(encoding="utf-8")):
                if _e_escopo_raiz(seletor):
                    continue
                for nome in DEFINICAO.findall(corpo):
                    if nome.startswith(FAMILIAS) and relativo in CAMADAS:
                        fora_de_lugar.append(f"{relativo}: {nome} sob {seletor.strip()[:40]}")
        self.assertEqual(
            fora_de_lugar,
            [],
            "re-ligação de token global dentro de uma camada de token — ver UI-03",
        )

    def test_o_bloco_escuro_herdado_ficou_antes_do_bloco_proprio(self):
        """Ordem, não conteúdo — e é o detalhe que mudaria cor em silêncio.

        O bloco escuro que veio do `theme.css` carregava ANTES do
        `03-theme-dark.css`. Apender no fim do arquivo inverteria a disputa: as
        declarações herdadas passariam a vencer as próprias, mudando cor sem
        mudar valor nenhum.
        """
        texto = (CSS / "base" / "03-theme-dark.css").read_text(encoding="utf-8")
        herdado = texto.index("tema escuro oficial")
        proprio = texto.index("color-scheme: dark")
        self.assertLess(
            herdado,
            proprio,
            "o bloco herdado do theme.css tem que vir ANTES do bloco próprio",
        )
