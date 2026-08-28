#!/usr/bin/env python3
"""Gera perfis de CSS por família de rota a partir da cobertura multiestado do PF-02.

Duas entregas por família, porque são dois `<link>` no `<head>` e o orçamento do
`NOVO-12` é de dois arquivos:

- ``<família>.css`` — poda de `shell.bundle.css` (ou da variante com componentes
  de formulário). Existe desde o `PF-02`.
- ``<família>.ui.css`` — poda de `ui.bundle.css`, o bundle do v2. Novo em
  ``NOVO-20260820-171008-7afb74d82d2c``.

O v2 ficava FORA da poda de propósito, e o custo disso foi medido: `ui.bundle.css`
entrega 553 KB em toda rota e casa 9,0% deles. Era ele, sozinho, que derrubava o
uso médio das 43 rotas de 48,9% para 13,6% e deixava o gate do `NOVO-70` vermelho.

As duas entregas leem chaves separadas do manifesto (`rule_ids`/`dom_classes` para
a casca, `ui_rule_ids`/`ui_dom_classes` para o v2) de propósito: a captura do
`PF-02` é um dado histórico — 629 das classes dela são marcação legada que não
existe mais no DOM — e sobrescrevê-la aqui mudaria os 15 perfis de casca num PR
que não é sobre eles. Enquanto a captura da casca não for refeita por inteiro, as
duas convivem; um `--capture` completo grava as duas com o mesmo conteúdo.

O manifesto guarda apenas hashes de regras observadas. As regras continuam
editáveis nas fontes canônicas e os perfis preservam a ordem da cascata do
bundle completo. ``--capture`` recalibra o manifesto com relatórios produzidos
por ``medir_css_por_rota.py --include-matched-css``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path

import tinycss2

ROOT = Path(__file__).resolve().parents[1]
STATIC_CSS = ROOT / "static" / "css"
MANIFEST = ROOT / "scripts" / "css_profiles_manifest.json"
OUTPUT_DIR = STATIC_CSS / "profiles"

PROFILE_ROUTES: dict[str, tuple[str, ...]] = {
    # `login` não tem bundle de shell — a tela é uma casca própria, fora do
    # `base.html`. Entra aqui só pela poda do v2, e é justamente a rota onde o
    # bundle inteiro doía mais: 4,2% de uso.
    "login": ("login",),
    "dashboard": ("dashboard",),
    "entity-lists": (
        "oficios-lista",
        "roteiros-lista",
        "prestacoes-contas-lista",
        "termos-lista",
        "planos-trabalho-lista",
        "ordens-servico-lista",
    ),
    "eventos-list": ("eventos-lista",),
    "justificativas-list": ("justificativas-lista",),
    "catalog-lists": (
        "oficios-modelos-motivo-lista",
        "servidores-lista",
        "viaturas-lista",
        "unidades-lista",
        "cargos-lista",
        "combustiveis-lista",
    ),
    "oficio-new": ("oficios-novo",),
    "termo-preview": ("termos-preview-oficio",),
    "model-forms": (
        "oficios-modelos-motivo-novo",
        "oficios-modelos-motivo-editar",
        "justificativas-novo",
        "justificativas-editar",
        "unidade-nova",
        "unidade-editar",
        "cargo-novo",
        "cargo-editar",
        "combustivel-novo",
        "combustivel-editar",
    ),
    "oficio-core": (
        "oficios-detalhe",
        "oficios-editar",
        "oficios-wizard-dados-viajantes",
    ),
    "oficio-transport": ("oficios-wizard-transporte",),
    "oficio-route": ("oficios-wizard-roteiro",),
    "oficio-justification": ("oficios-wizard-justificativa",),
    "oficio-documents": (
        "oficios-wizard-resumo",
        "oficios-wizard-documentos",
    ),
    "roteiro-form": ("roteiros-novo", "roteiros-editar"),
    "admin-form": (
        "configuracao",
        "servidor-novo",
        "servidor-editar",
        "viatura-nova",
        "viatura-editar",
    ),
}

_CLASS = re.compile(r"\.(-?[_a-zA-Z]+[_a-zA-Z0-9-]*)")
_INTERACTIVE_STATE = re.compile(
    r":(?:hover|focus(?:-visible|-within)?|active|checked|disabled|enabled|open)\b"
    r"|\.(?:is|has)-[\w-]+|\[(?:aria-(?:expanded|selected|pressed|checked)|open)="
)
_STATE_CLASS = re.compile(r"^(?:is|has)-")
_MODIFICADOR_BEM = re.compile(r"--[\w-]+$")


def _nasce_de(class_name: str, presentes: set[str]) -> bool:
    """A classe é uma VARIANTE ou PARTE de algo que a captura viu?

    Metade do que o `date-picker` e o `download-picker` desenham só existe no DOM
    depois de uma interação: `date-picker__day--selected` nasce no clique,
    `download-picker__queue-item` nasce quando o download começa. Nenhum aparece
    numa captura, por mais estados que ela abra, e exigir a classe exata apagava
    o dia selecionado e a fila de downloads de telas que usam esses componentes o
    tempo todo.

    O critério é o prefixo até um traço: `download-picker__queue-item` entra
    porque `download-picker__queue` foi visto; `date-picker__day--selected`
    entra porque `date-picker__day` foi visto. Deliberadamente NÃO vale para o
    `__`: `search-picker__option` não entra só porque a página tem
    `search-picker`, senão a poda deixaria de podar — medido, isso levava o uso
    de `justificativas-lista` de 39% para 25%.
    """
    if class_name in presentes:
        return True
    for visto in presentes:
        # Variante: `date-picker__day--selected` nasce de `date-picker__day`.
        if class_name.startswith(f"{visto}--"):
            return True
        # Parte de um ELEMENTO visto: `download-picker__queue-item` nasce de
        # `download-picker__queue`. Exigir o `__` no que foi visto é o que
        # impede um nome curto de arrastar vizinho alheio — sem isso, `button`
        # casaria `button-group` de outro componente, e o `login` (28 KB, onde
        # cada regra a mais pesa) caía de 39,8% para 34,5% de uso.
        if "__" in visto and class_name.startswith(f"{visto}-"):
            return True
    return False
# `:is(...)`/`:where(...)` são ALTERNATIVAS, não conjunção. Extrair classe de
# dentro deles e exigir todas junto reprova o seletor inteiro por causa de um
# ramo que a família não usa — `:is(.picker, .destination-row, .field)
# .search-picker__clear` some de uma tela que tem `.picker` só porque não tem
# `.destination-row`. Para o critério de presença, o grupo vira coringa.
_IS_WHERE = re.compile(r":(?:is|where)\((?:[^()]|\([^()]*\))*\)")
_IMPORT = re.compile(r'@import\s+url\(["\']?([^"\')]+)["\']?\)\s*;')

def _serialized(rule) -> str:
    return tinycss2.serialize([rule]).strip()


def _rule_id(rule) -> str:
    return hashlib.sha256(_serialized(rule).encode("utf-8")).hexdigest()


def _fragment_rule_ids(fragment: str) -> set[str]:
    return {
        _rule_id(rule)
        for rule in tinycss2.parse_rule_list(
            fragment, skip_comments=True, skip_whitespace=True
        )
        if rule.type in {"qualified-rule", "at-rule"}
    }


def _selector(rule) -> str:
    return tinycss2.serialize(rule.prelude).strip()


def _qualified_rules(rules):
    for rule in rules:
        if rule.type == "qualified-rule":
            yield rule
        elif rule.type == "at-rule" and rule.content is not None and rule.lower_at_keyword in {
            "media",
            "supports",
            "container",
            "layer",
            "scope",
        }:
            yield from _qualified_rules(
                tinycss2.parse_rule_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
            )


# Seletor de RAIZ: `:root`, `html[data-theme="dark"]`, `html[data-theme]`, e as
# variações embrulhadas em `:is(...)`. Não entra nada com classe, descendente ou
# combinador — só o elemento raiz, que é onde vivem os tokens.
_ROOT_SELECTOR = re.compile(
    r'^(?::is\()?\s*(?::root|html)(?:\[data-theme(?:="[^"]*")?\])?\s*\)?$'
)


def _is_root_rule(rule) -> bool:
    """Rule aplicada ao ELEMENTO RAIZ — `:root`, `html`, `html[data-theme=…]`.

    Só o próprio raiz: qualquer descendente, classe ou combinador reprova, e é
    por isso que `:is(html[data-theme]) .rail` (a forma de quase todo componente
    daqui) não entra.
    """
    partes = [parte.strip() for parte in _selector(rule).split(",") if parte.strip()]
    return bool(partes) and all(_ROOT_SELECTOR.match(parte) for parte in partes)


def _token_rule_ids(rules) -> set[str]:
    """Blocos de raiz, que NUNCA podem ser podados por cobertura.

    A cobertura do CDP é medida com UM tema aplicado por vez, e um bloco
    `html[data-theme="dark"]` simplesmente não casa enquanto a medição roda no
    claro. Podar por cobertura, portanto, apaga a definição do OUTRO tema — foi
    assim que o bloco escuro inteiro sumiu de todos os perfis, levando junto
    `--app-body-bg`, e as telas com perfil passaram a mostrar no tema escuro o
    gradiente claro. O bundle completo, sem perfil, continuava certo, o que
    escondeu o defeito.

    O critério é o SELETOR e não o conteúdo: o bloco escuro dos tokens declara
    `color-scheme: dark` no meio das custom properties, e exigir "só custom
    property" deixava justamente ele de fora. Regra de raiz é definição de tema,
    mede-se em centenas de bytes, e não tem por que ser podada.
    """
    return {_rule_id(rule) for rule in _qualified_rules(rules) if _is_root_rule(rule)}


def _ramos_do_seletor(selector: str) -> list[str]:
    """Divide `a, b` no nível de cima, respeitando `:is(a, b)` e afins.

    Vírgula em CSS é ALTERNATIVA: `.nav:hover, .legado:hover` vale para as duas.
    Avaliar a união das classes dos dois ramos deixa um ramo morto derrubar o
    vivo — e o seletor inteiro some da tela que usa só o primeiro.
    """
    ramos: list[str] = []
    profundidade = 0
    atual: list[str] = []
    for caractere in selector:
        if caractere == "(":
            profundidade += 1
        elif caractere == ")":
            profundidade -= 1
        if caractere == "," and profundidade == 0:
            ramos.append("".join(atual))
            atual = []
            continue
        atual.append(caractere)
    ramos.append("".join(atual))
    return [ramo.strip() for ramo in ramos if ramo.strip()]


def _with_dom_families(
    rules,
    selected: set[str],
    dom_classes: set[str],
    *,
    incluir_base: bool = False,
    manter_sem_classe: bool = False,
) -> set[str]:
    """Acrescenta ao medido o que a cobertura do CDP não sabe ver.

    `incluir_base` troca o critério de "o CDP viu casar" por "a família tem essas
    classes no DOM". É o que o v2 usa, e existe porque a cobertura não enxerga
    estado que o próprio CSS esconde: `li.file-picker__row` nasce `display:none`
    por regra, não por atributo, então `--reveal` não o descobre e o podador
    apagava a família inteira do `file-picker` — 39 elementos por tema, medidos.
    A casca continua no critério antigo: o manifesto dela é a captura do PF-02, e
    trocar o critério mudaria os 15 perfis num PR que não é sobre eles.
    """
    qualified = list(_qualified_rules(rules))
    result = set(selected)
    aplicaveis: dict[str, list[str]] = {}
    for rule in qualified:
        selector = _selector(rule)
        # Vírgula é alternativa: basta UM ramo aplicável para a regra entrar.
        # Só no caminho do v2. A casca tem o MESMO defeito, e ele está registrado
        # em `NOVO-20260826-124840-50a3e47836ae` — consertá-lo aqui mudaria os 15
        # perfis do PF-02 num PR que promete não tocá-los, e sem a recaptura que
        # a casca precisa de qualquer jeito.
        ramos = _ramos_do_seletor(selector) if incluir_base else [selector]
        vivos = [
            ramo
            for ramo in ramos
            if _ramo_aplicavel(
                ramo,
                dom_classes,
                incluir_base=incluir_base,
                manter_sem_classe=manter_sem_classe,
            )
        ]
        if vivos:
            rid = _rule_id(rule)
            result.add(rid)
            aplicaveis[rid] = vivos
    return result, aplicaveis


def _ramo_aplicavel(
    ramo: str,
    dom_classes: set[str],
    *,
    incluir_base: bool,
    manter_sem_classe: bool = False,
) -> bool:
    classes = set(_CLASS.findall(ramo))
    fonte_de_classes = _IS_WHERE.sub(" ", ramo) if incluir_base else ramo
    structural_classes = {
        class_name
        for class_name in _CLASS.findall(fonte_de_classes)
        if not _STATE_CLASS.match(class_name)
    }
    if incluir_base and not structural_classes and classes:
        # Ramo cujas classes vivem TODAS dentro de um `:is(...)`. Sem nada fora
        # do grupo não há o que conferir; entra, que é o lado seguro.
        return True
    # Regras normais presentes no DOM ja entram pelos fragmentos medidos do
    # manifesto. A expansao por familia existe somente para estados que o
    # CDP nao casa sem interacao (hover/focus/checked etc.). Classes de
    # estado como ``is-open`` so aparecem depois da interacao e, portanto,
    # nao podem ser exigidas no retrato inicial do DOM.
    if incluir_base:
        cobertas = all(_nasce_de(nome, dom_classes) for nome in structural_classes)
    else:
        cobertas = structural_classes.issubset(dom_classes)
    if (
        structural_classes
        and cobertas
        and (incluir_base or _INTERACTIVE_STATE.search(ramo))
    ):
        return True
    if manter_sem_classe and not classes:
        # Seletor SEM classe nenhuma não é podável por predicado de classe: ou é
        # global (`:root`, `html`), ou é dirigido por atributo que o JS põe em
        # runtime — `:is(html[data-theme]) [data-document-download-active]` é o
        # guarda de `pointer-events` que impede o segundo clique disparar uma
        # segunda geração de documento. São 14 regras em 1.596 no `ui.bundle.css`.
        #
        # `manter_sem_classe` é falso onde não há casca: quem dirige esses
        # atributos é o JS do shell, que o `login` não carrega. As regras de raiz
        # (`:root`, `html[data-theme]`) chegam lá por `_token_rule_ids` de
        # qualquer forma. Sem esse recorte o `login` cai a 34,5% de uso, abaixo
        # do aceite do PF-02.
        return True
    # Regra de ESTADO em elemento, sem classe: `button:focus-visible`. É o
    # critério original do PF-02 e continua valendo para a casca — tirá-lo
    # apagava o piso de foco de teclado dos 15 perfis.
    return bool(
        _INTERACTIVE_STATE.search(ramo)
        and not classes
        and re.search(r"\b(?:a|button|input|select|textarea):", ramo)
    )


UI_SOURCE = "ui.bundle.css"

# Marcação que só existe DEPOIS de uma requisição malsucedida, e que por isso
# nenhuma captura por GET enxerga — nem com `--reveal`, porque o elemento não
# está escondido: ele não existe. Senha errada no login renderia o bloco de erro
# sem estilo nenhum, e é justamente o momento em que a tela não pode falhar.
#
# São os nomes exatos porque `_nasce_de` não cobre o `__`: `form-errors__title`
# não "nasce de" `form-errors` pelo critério de traço, de propósito.
#
# Conserto de fundo, fora desta etapa: derivar as classes dos TEMPLATES que cada
# rota renderiza (`response.templates` do test client) em vez de só do DOM
# capturado, que resolve toda marcação condicional de uma vez.
STATIC_JS = ROOT / "static" / "js"
# Espelha `SHELL_JS` do `build_shell_bundles.py`: o JS que TODA tela carrega.
_JS_GLOBAL: tuple[str, ...] = (
    "js/theme-toggle.js",
    "js/core/http.js",
    "js/core/app.js",
    "js/core/component-loader.js",
    "js/autosave.js",
    "js/components/sidebar.js",
    "js/components/masks.js",
    "js/components/state-toggle.js",
    "js/components/collection.js",
    "js/components/icon-tooltips.js",
    "js/components/overlay.js",
    "js/components/fields-init.js",
    "js/components/document-download.js",
    "js/components/fit-text.js",
    "js/components/notice-auto-dismiss.js",
    "js/components/server-filter.js",
)
# `className = "x"` e `class="x"` dentro de string de template no JS: as classes
# que o JavaScript CRIA. Toggle (`classList.add`) não entra — esse mexe em
# elemento que já está no DOM, e `_nasce_de` mais `_INTERACTIVE_STATE` já cobrem.
_CLASSE_EM_JS = re.compile(r'(?:className\s*=\s*"([^"]+)"|class="([^"{]+)")')


def classes_criadas_por_js() -> frozenset[str]:
    """Raízes de componente que o JS monta e nenhuma captura enxerga.

    O caso que obrigou isto: `icon-tooltips.js` cria `<div class="global-tooltip">`
    no primeiro hover. O `static/css/v2/tooltip.css` documenta, no topo do
    arquivo, que esse desenho foi PARA o `ui.bundle.css` justamente porque "o
    `ui.bundle.css` não é podado" — quando ele morava numa folha podada, sobrava
    só a regra que desliga o tooltip de `::after`, o `<div>` caía no fim do corpo
    com `position: static` e o texto aparecia solto embaixo da página.

    Este PR passou a podar o `ui.bundle.css`, ou seja, quebrou a premissa daquele
    comentário. Ler as classes do JS é o que devolve a garantia sem depender de
    lista escrita à mão: componente novo criado por JS entra sozinho.

    Só o JS do SHELL, que carrega em toda tela. O JS por página cria classes
    próprias (`folder-row`, `pdf-viewer__thumb`, `route-destinos-trechos__*`) e
    pôr todas em todo perfil custa caro onde dói: o `login` saltaria de 30 KB
    para 44 KB e o uso dele cairia de 35,4% para ~24%, abaixo do aceite do
    PF-02. Mapear JS de página para família de rota é o passo seguinte, e está
    em `NOVO-20260826-124840-50a3e47836ae`.
    """
    encontradas: set[str] = set()
    for relativo in _JS_GLOBAL:
        arquivo = ROOT / "static" / relativo
        for grupo in _CLASSE_EM_JS.findall(arquivo.read_text(encoding="utf-8")):
            for trecho in grupo:
                encontradas.update(
                    nome for nome in trecho.split() if re.fullmatch(r"[a-z][\w-]*", nome)
                )
    return frozenset(encontradas)


CLASSES_DE_FEEDBACK = frozenset(
    {
        "alert",
        # A pilha de mensagens do Django: `templates/cotton/v2/alert.html` só
        # desenha o embrulho quando há mensagem, ou seja, depois de um redirect
        # que carregue uma. Sem ela os alertas perdem o espaçamento, o gap da
        # grade e a transição de auto-dismiss de `static/css/v2/alert.css`.
        "alert-stack",
        "form-errors",
        "form-errors__title",
        "form-errors__list",
        "field__error",
        "field--invalid",
        "notice",
    }
)


PERFIS_SEM_SHELL = frozenset({"login"})


def _shell_sheet(route: dict) -> dict | None:
    candidates = [
        sheet
        for sheet in route["stylesheet_usage"]
        if sheet["source_url"].endswith("/shell.bundle.css")
        or sheet["source_url"].endswith("/shell.form-components.bundle.css")
    ]
    if not candidates:
        # `login` é assim: casca própria, sem shell. Perfil só do v2. Qualquer
        # OUTRA rota sem folha de shell é relatório malformado — a página ou o
        # asset não carregou —, e devolver `None` ali faria `capture()` gravar
        # `source: null`, parar de emitir aquele perfil e deixar o arquivo velho
        # no disco, que o context processor continuaria servindo.
        return None

    if len(candidates) != 1:
        raise ValueError("a rota possui mais de um bundle de shell")
    return candidates[0]


# `url(...)` relativa, ignorando `data:`, absoluta e externa — mesma forma que o
# `build_shell_bundles.py` usa para reancorar folha que muda de diretório.
_CSS_URL = re.compile(
    r"url\((?P<quote>['\"])(?P<path>(?!data:|https?:|/|#)[^'\"]+)(?P=quote)\)"
)


def _reancorar(text: str, origem_rel: str) -> str:
    """Reescreve `url(...)` de uma folha em `origem_rel` para `css/profiles/`.

    `NOVO-70`: o perfil é escrito em `static/css/profiles/`, um nível abaixo de
    onde o `ui.bundle.css` mora, e as `@font-face` dele apontam para
    `../vendor/fonts/…`. Copiadas sem reancorar, viram `css/vendor/fonts/…` e o
    `collectstatic` com o storage de manifesto do WhiteNoise reprova o deploy —
    foi assim que a CI pegou. As folhas do shell não mudam de profundidade
    (`css/base/` e `css/profiles/` estão no mesmo nível), então para elas isto é
    identidade e os 15 perfis de casca continuam byte a byte iguais.
    """
    origem_dir = posixpath.dirname(origem_rel)
    destino_dir = OUTPUT_DIR.relative_to(STATIC_CSS.parent).as_posix()
    if origem_dir == destino_dir:
        return text

    def replace(match) -> str:
        alvo = posixpath.normpath(posixpath.join(origem_dir, match.group("path")))
        aspas = match.group("quote")
        return f"url({aspas}{posixpath.relpath(alvo, destino_dir)}{aspas})"

    return _CSS_URL.sub(replace, text)


def _expanded_source(source_name: str) -> str:
    text = (STATIC_CSS / source_name).read_text(encoding="utf-8")
    importados: list[str] = []

    def guardar(match) -> str:
        relative = match.group(1)
        if relative.startswith(("http://", "https://")):
            return match.group(0)
        imported = (STATIC_CSS / relative).resolve()
        if not imported.is_relative_to(STATIC_CSS.resolve()):
            raise ValueError(f"import CSS fora de static/css: {relative}")
        # Cada folha importada tem o SEU diretório como âncora, e não o do
        # bundle: `base/fonts.css` escreve `../../vendor/…` a partir de si mesma.
        # Guardar num marcador é o que impede a reancoragem de rodar duas vezes
        # sobre o mesmo texto — foi esse duplo passe que somou um `../` a mais
        # nas fontes dos perfis de casca na primeira tentativa.
        importados.append(
            _reancorar(
                imported.read_text(encoding="utf-8"),
                posixpath.join("css", relative.removeprefix("./")),
            )
        )
        return f"/*__IMPORT_{len(importados) - 1}__*/"

    marcado = _reancorar(_IMPORT.sub(guardar, text), posixpath.join("css", source_name))
    for indice, conteudo in enumerate(importados):
        marcado = marcado.replace(f"/*__IMPORT_{indice}__*/", conteudo)
    return marcado


def _source_sheet_suffixes(source_name: str) -> tuple[str, ...]:
    text = (STATIC_CSS / source_name).read_text(encoding="utf-8")
    imports = [match.group(1).removeprefix("./") for match in _IMPORT.finditer(text)]
    return (source_name, *imports)


def capture(reports: list[Path]) -> dict:
    loaded = [json.loads(path.read_text(encoding="utf-8"))["routes"] for path in reports]
    profiles = {}
    for profile, slugs in PROFILE_ROUTES.items():
        rule_ids: set[str] = set()
        dom_classes: set[str] = set()
        ui_rule_ids: set[str] = set()
        ui_dom_classes: set[str] = set()
        source_names = {
            folha["source_url"].rsplit("/", 1)[-1]
            for routes in loaded
            for slug in slugs
            if slug in routes
            for folha in [_shell_sheet(routes[slug])]
            if folha is not None
        }
        if len(source_names) > 1:
            raise ValueError(f"perfil mistura variantes de shell: {profile}={source_names}")
        source = source_names.pop() if source_names else None
        suffixes = (
            tuple(f"/static/css/{item}" for item in _source_sheet_suffixes(source))
            if source
            else ()
        )
        ui_suffixes = tuple(
            f"/static/css/{item}" for item in _source_sheet_suffixes(UI_SOURCE)
        )
        for routes in loaded:
            for slug in slugs:
                route = routes.get(slug)
                if not route:
                    continue
                if _shell_sheet(route) is None and profile not in PERFIS_SEM_SHELL:
                    raise ValueError(
                        f"perfil {profile}: a rota {slug} veio sem folha de shell "
                        "no relatório — recapture; só o `login` não tem casca"
                    )
                dom_classes.update(route.get("dom_classes", []))
                ui_dom_classes.update(route.get("dom_classes", []))
                for sheet in route["stylesheet_usage"]:
                    if suffixes and sheet["source_url"].endswith(suffixes):
                        for fragment in sheet.get("matched_fragments", []):
                            rule_ids.update(_fragment_rule_ids(fragment))
                    elif sheet["source_url"].endswith(ui_suffixes):
                        for fragment in sheet.get("matched_fragments", []):
                            ui_rule_ids.update(_fragment_rule_ids(fragment))
        if source and not rule_ids:
            raise ValueError(f"perfil sem cobertura de shell: {profile}")
        vistas = {
            slug
            for routes in loaded
            for slug in slugs
            if slug in routes
        }
        faltando = [slug for slug in slugs if slug not in vistas]
        if faltando:
            # `--include-matched-css` exige `--route`, então conjunto incompleto
            # de relatórios é entrada plausível — e a família compartilha UM
            # arquivo. Sem esta trava, um relatório só de `oficios-lista`
            # produziria um `entity-lists.ui.css` válido, servido a Termos sem
            # nenhuma classe de Termos.
            raise ValueError(
                f"perfil {profile}: faltam rotas na captura ({', '.join(faltando)}). "
                "A família inteira precisa estar nos relatórios — o perfil é um "
                "arquivo só para todas elas."
            )
        if not ui_rule_ids:
            raise ValueError(
                f"perfil sem cobertura do v2: {profile}. A causa quase certa é a "
                "captura ter rodado contra um servidor com CSS_ROUTE_PROFILES_ENABLED "
                "ligado (o padrão): aí a rota entrega `css/profiles/<família>.ui.css` "
                "e não `css/ui.bundle.css`, e não há bundle para medir. Suba o "
                "servidor com CSS_ROUTE_PROFILES_ENABLED=false e recapture."
            )
        profiles[profile] = {
            "source": source,
            "routes": list(slugs),
            "rule_ids": sorted(rule_ids),
            "ui_rule_ids": sorted(ui_rule_ids),
            "dom_classes": sorted(dom_classes),
            "ui_dom_classes": sorted(ui_dom_classes),
        }
    return {"schema_version": 1, "profiles": profiles}


def _reescrever(rule, ramos: list[str]) -> str:
    """A regra com SÓ os ramos aplicáveis: `a, b { x }` vira `a { x }`.

    Vírgula é alternativa, então basta um ramo aplicável para a regra entrar —
    mas emitir a regra inteira arrasta o texto dos outros ramos junto. Medido: o
    perfil do `login` carregava seletor de `oficio-documentos-*`, `search-picker`
    e `rail` — componentes que uma tela de login não tem — só porque dividiam a
    regra com algo que ela tem.

    Podar ramo é o MESMO julgamento que podar a regra inteira, uma casa abaixo: o
    ramo cujas classes a família não tem não pode casar ali. Não mexe em
    especificidade nem em ordem de cascata dos ramos que ficam.
    """
    return f"{', '.join(ramos)} {{{tinycss2.serialize(rule.content)}}}"


def _render_rules(
    rules,
    selected: set[str],
    used_keyframes: set[str],
    ramos_por_regra: dict[str, list[str]] | None = None,
) -> str:
    chunks: list[str] = []
    for rule in rules:
        if rule.type == "qualified-rule":
            if _rule_id(rule) in selected:
                ramos = (ramos_por_regra or {}).get(_rule_id(rule))
                todos = _ramos_do_seletor(_selector(rule))
                chunks.append(
                    _reescrever(rule, ramos)
                    if ramos and len(ramos) < len(todos)
                    else _serialized(rule)
                )
            continue
        if rule.type != "at-rule":
            continue
        keyword = rule.lower_at_keyword
        if keyword == "import" or keyword in {"font-face", "font-feature-values", "property"}:
            chunks.append(_serialized(rule))
            continue
        if keyword.endswith("keyframes"):
            name = tinycss2.serialize(rule.prelude).strip()
            if name in used_keyframes:
                chunks.append(_serialized(rule))
            continue
        if rule.content is None:
            continue
        if keyword not in {"media", "supports", "container", "layer", "scope"}:
            continue
        nested = tinycss2.parse_rule_list(
            rule.content, skip_comments=True, skip_whitespace=True
        )
        body = _render_rules(nested, selected, used_keyframes, ramos_por_regra)
        if body:
            prelude = tinycss2.serialize(rule.prelude).strip()
            chunks.append(f"@{rule.at_keyword} {prelude} {{\n{body}\n}}")
    return "\n".join(chunks)


def _podar(
    source_name: str,
    rule_ids: list[str],
    dom_classes: set[str],
    *,
    incluir_base: bool = False,
    manter_sem_classe: bool = False,
) -> str:
    """Corpo do perfil: as regras casadas, mais o que a cobertura não enxerga.

    O que entra além do medido, e por quê, está em `_token_rule_ids` (tema) e
    `_with_dom_families` (estados de interação). Os dois existem porque a
    cobertura do CDP é um retrato: mede um tema por vez e sem hover.
    """
    rules = tinycss2.parse_stylesheet(
        _expanded_source(source_name), skip_comments=True, skip_whitespace=True
    )
    selected, ramos_por_regra = _with_dom_families(
        rules,
        set(rule_ids) | _token_rule_ids(rules),
        dom_classes,
        incluir_base=incluir_base,
        manter_sem_classe=manter_sem_classe,
    )
    if not incluir_base:
        # A casca não reescreve ramo: os 15 perfis do PF-02 saem byte a byte.
        ramos_por_regra = {}
    selected_css = "\n".join(
        _serialized(rule)
        for rule in _qualified_rules(rules)
        if _rule_id(rule) in selected
    )
    keyframe_names = {
        tinycss2.serialize(rule.prelude).strip()
        for rule in rules
        if rule.type == "at-rule" and rule.lower_at_keyword.endswith("keyframes")
        and tinycss2.serialize(rule.prelude).strip() in selected_css
    }
    return _render_rules(rules, selected, keyframe_names, ramos_por_regra)


def build(manifest: dict) -> dict[Path, str]:
    outputs = {}
    banner = "/* AUTO-GENERATED by scripts/build_css_profiles.py — do not edit. */\n"
    for profile, config in manifest["profiles"].items():
        dom_classes = set(config.get("dom_classes", []))
        if config.get("source"):
            body = _podar(config["source"], config["rule_ids"], dom_classes)
            outputs[OUTPUT_DIR / f"{profile}.css"] = banner + body + "\n"
        ui_body = _podar(
            UI_SOURCE,
            config.get("ui_rule_ids", []),
            set(config.get("ui_dom_classes", config.get("dom_classes", [])))
            | CLASSES_DE_FEEDBACK
            # O `login` não carrega `shell.bundle.js` — só `theme-shared.js` e
            # `theme-init.js` —, então nada do JS do shell roda ali e nenhuma
            # dessas classes pode existir naquela tela. É a mesma razão de ele não
            # ter perfil de casca: ele não tem casca. Incluí-las custava 2 pontos
            # percentuais de uso numa rota que entrega 21 KB.
            | (frozenset() if profile in PERFIS_SEM_SHELL else classes_criadas_por_js()),
            incluir_base=True,
            manter_sem_classe=profile not in PERFIS_SEM_SHELL,
        )
        outputs[OUTPUT_DIR / f"{profile}.ui.css"] = banner + ui_body + "\n"
    return outputs


def _write_or_check(outputs: dict[Path, str], *, check: bool) -> int:
    stale = []
    for path, expected in outputs.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
    if stale:
        print("Perfis CSS desatualizados: " + ", ".join(stale))
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.capture:
        payload = capture(args.capture)
        MANIFEST.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if not MANIFEST.exists():
        parser.error("manifesto ausente; use --capture com os relatórios de cobertura")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return _write_or_check(build(manifest), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
