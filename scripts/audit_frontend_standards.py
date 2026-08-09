"""
Auditor de padrões frontend — Central de Viagens 3.0
Saída em três níveis:
  ERRO  — violação que deve ser corrigida antes do merge (exit 1)
  AVISO — dívida técnica conhecida, não bloqueia (exit 0)
  EXCEC — desvio documentado como exceção oficial (exit 0, informativo)
"""
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
CSS_DIR = ROOT / "static" / "css"
JS_DIR = ROOT / "static" / "js"

# ---------------------------------------------------------------------------
# Exceções documentadas — chave: caminho relativo ao ROOT (posix)
# ---------------------------------------------------------------------------
TEMPLATE_EXCEPTIONS: dict[str, dict] = {
    "templates/core/dashboard.html": {
        "reason": "Shell dashboard-login-inspired e excecao oficial -- usa 100% CSS vars.",
        "rules": {"legacy_page_header"},
    },
}

CSS_EXCEPTIONS: dict[str, dict] = {
    "static/css/fields/forms.css": {
        "reason": ".roteiro-editor__* permanece como dominio em CSS global; --route-* sao variaveis globais de tema.",
        "rules": {"domain_selector_in_global", "route_token_in_global", "hex_color_outside_tokens"},
    },
    "static/css/lists/cards.css": {
        "reason": ".oficio-card em cards.css: domínio a mover para oficios.css (Prompt 5).",
        "rules": {"domain_selector_in_global"},
    },
    "static/css/base/tokens.css": {
        "reason": "Arquivo de tokens — cores hex são a definição original, permitidas aqui.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/base/theme.css": {
        "reason": "Arquivo de tema — cores hex são a definição original, permitidas aqui.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/base/03-theme-dark.css": {
        "reason": "Official dark-theme token layer; literal values define semantic tokens.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/components/theme-dark-components.css": {
        "reason": "Transitional dark-theme component overrides; literals allowed until dissolved into components.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/pages/auth.css": {
        "reason": "CSS de autenticação — isolado, pode ter cores específicas.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/shell.bundle.css": {
        "reason": "Bundle gerado (NOVO-12) — literais e seletores vêm das fontes; auditar as fontes.",
        "rules": {
            "hex_color_outside_tokens",
            "domain_selector_in_global",
            "route_token_in_global",
            "legacy_page_header_in_css",
        },
    },
}

# ---------------------------------------------------------------------------
# Regras de templates
# ---------------------------------------------------------------------------
TEMPLATE_RULES_ERRO = [
    ("onsubmit_inline", re.compile(r'\bonsubmit='),           'Inline onsubmit event - use addEventListener'),
    ("css_inline",      re.compile(r'\bstyle="'),             'Atributo style="" inline — usar classe CSS'),
    ("onclick_inline",  re.compile(r'\bonclick='),            'Evento onclick inline — usar addEventListener'),
    ("onchange_inline", re.compile(r'\bonchange='),           'Evento onchange inline — usar addEventListener'),
    ("oninput_inline",  re.compile(r'\boninput='),            'Evento oninput inline — usar addEventListener'),
    ("js_void",         re.compile(r'javascript:void'),       'javascript:void — usar href ou button'),
    # `{# #}` do Django é comentário de UMA linha. Aberto numa linha e fechado em
    # outra, o Django não reconhece e devolve o texto VERBATIM para o HTML — como
    # texto visível na página, ou como lixo no meio de uma tag, virando atributos
    # inventados. Achado em produção: 6 linhas de comentário apareciam na etapa
    # Transporte do wizard de ofício. Use `{% comment %}` para várias linhas.
    ("comentario_django_multilinha", re.compile(r'\{#(?![^\n]*#\})'),
     'Comentário {# #} sem fechar na mesma linha — vaza para o HTML; use {% comment %}'),
]

TEMPLATE_RULES_AVISO = [
    ("href_hash",            re.compile(r'\bhref="#"'),                'href="#" — checar se é intencional'),
    ("legacy_page_header",   re.compile(r'class="[^"]*\bpage-header\b'), 'Classe page-header legada — migrar para app-page-hero'),
    ("script_inline",        re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(?!\s*<)'), '<script> inline (sem src) — mover para arquivo .js'),
]

# ---------------------------------------------------------------------------
# Regras de CSS
# ---------------------------------------------------------------------------
# Arquivos que viviam em `static/css/components/` e nunca foram auditados: a
# varredura era rasa (`glob`), e o diretorio estava um nivel abaixo. O `NOVO-66`
# os moveu para pastas por funcao e, de quebra, os traria para dentro da conta —
# somando 114 avisos de divida PREEXISTENTE a uma catraca que so desce, num PR
# que apenas move arquivo.
#
# A cobertura fica adiada para nao misturar as duas coisas. A lacuna esta
# registrada como `NOVO-67`, com o numero ja medido: 240 -> 354.
COBERTURA_ADIADA = {
    "static/css/actions/action-system.css",
    "static/css/feedback/dialog.css",
    "static/css/feedback/document-download-loading.css",
    "static/css/feedback/metric.css",
    "static/css/feedback/notice.css",
    "static/css/feedback/pendencias.css",
    "static/css/feedback/summary-items.css",
    "static/css/fields/date-picker.css",
    "static/css/fields/field.css",
    "static/css/fields/file-picker.css",
    "static/css/fields/form-panel.css",
    "static/css/fields/form-sections.css",
    "static/css/layout/app-shell.css",
    "static/css/lists/content-cards.css",
    "static/css/lists/filter-header.css",
    "static/css/lists/list-header.css",
    "static/css/lists/list-tabs.css",
    "static/css/lists/record-list.css",
    "static/css/pages/document-generation-embedded.css",
    "static/css/pages/document-viewer.css",
}

# Arquivos CSS globais onde seletores de domínio não devem aparecer
GLOBAL_CSS = {
    "static/css/fields/forms.css",
    "static/css/lists/lists.css",
    "static/css/lists/cards.css",
    "static/css/layout/layout.css",
    "static/css/base/base.css",
    "static/css/base/utilities.css",
    "static/css/layout/stages.css",
    "static/css/pages/documents.css",
}

# Seletores de domínio que não devem estar em CSS global
_DOMAIN_SELECTOR_PAT = re.compile(
    r'^\s*\.(?:oficio|motivo|roteiro|diario|prestacao|plano|termo|ordem|justificativa)[_-]'
)
_ROUTE_TOKEN_PAT = re.compile(r'--route-')
_LEGACY_PAGE_HEADER_PAT = re.compile(r'^\s*\.page-header\b')
# Hex color fora de tokens/theme: match #rgb / #rrggbb / #rrggbbaa em valor CSS (não em comentário)
_HEX_COLOR_PAT = re.compile(r'(?<![\w#])#([0-9a-fA-F]{3,8})\b')
_CSS_COMMENT_LINE = re.compile(r'^\s*/\*')
_CSS_VALUE_LINE = re.compile(r':\s*.*#[0-9a-fA-F]{3,8}')

CSS_RULES_ERRO: list[tuple] = [
    # Cores hex em arquivos CSS que não são tokens/theme — devem usar var()
    # (verificado por lógica especial abaixo, não por regex simples)
]

CSS_RULES_AVISO = [
    ("domain_selector_in_global", _DOMAIN_SELECTOR_PAT, "Seletor de domínio em CSS global — mover para css de módulo"),
    ("route_token_in_global",     _ROUTE_TOKEN_PAT,     "Token --route-* em CSS global — mover para roteiros.css"),
    ("legacy_page_header_in_css", _LEGACY_PAGE_HEADER_PAT, "Seletor .page-header legado — encerrar após Prompt 3"),
]

# ---------------------------------------------------------------------------
# Regras de JavaScript
# ---------------------------------------------------------------------------

JS_HTTP_OWNER = "static/js/core/http.js"
JS_UTIL_OWNER = "static/js/core/app.js"
JS_MASKS_OWNER = "static/js/components/masks.js"

# JS-05 — exceções de JavaScript, com TETO por arquivo.
#
# Templates e CSS isentam o par (arquivo, regra) por inteiro; aqui o valor é a
# contagem que existe hoje. Ficar dentro do teto é EXCEC informativo; passar
# dele é ERRO. Assim a lista é catraca de verdade — só desce — e um arquivo
# isento não vira porta de entrada para violação nova.
#
# Baixar um teto quando o número cair é parte do trabalho, não faxina opcional.
JS_EXCEPTIONS: dict[str, dict] = {
    "static/js/pages/roteiros/editor/index.js": {
        "reason": "NOVO-14: classes de campo de tempo como condição, sai com o editor (BE-11, fase 6). NOVO-15: interpola markup de rota já escapado com CV.util.escapeHtml nas linhas vizinhas.",
        "rules": {"css_class_as_logic": 6, "innerhtml_dynamic_without_escape": 2},
    },
    "static/js/components/overlay.js": {
        "reason": "NOVO-14: estado aberto do menu lido pela classe; sai na reconstrução do CSS (fase 7).",
        "rules": {"css_class_as_logic": 1},
    },
    "static/js/components/icon-tooltips.js": {
        "reason": "NOVO-14: distingue o botão de gerenciar pela classe; sai com HT-08 (fase 7).",
        "rules": {"css_class_as_logic": 1},
    },
    "static/js/components/picker-select.js": {
        "reason": "NOVO-14: lê a própria classe de opção selecionada (fase 7). NOVO-15: interpola SVG constante do próprio arquivo.",
        "rules": {"css_class_as_logic": 1, "innerhtml_dynamic_without_escape": 2},
    },
    # NOVO-15 — innerHTML com dado dinâmico sem escapar. Nenhum destes é XSS
    # provado: a maioria interpola constante de ícone do próprio arquivo. Ficam
    # com teto para que nenhum caminho novo entre sem revisão.
    "static/js/components/location-rows.js": {
        "reason": "NOVO-15: markup de linha e opções montado a partir de template do próprio DOM.",
        "rules": {"innerhtml_dynamic_without_escape": 4},
    },
    "static/js/pages/gdrive-config.js": {
        "reason": "NOVO-15: já usa escapeHtml nos dados; a linha marcada monta o invólucro.",
        "rules": {"innerhtml_dynamic_without_escape": 1},
    },
    "static/js/pages/eventos-detalhe.js": {
        "reason": "NOVO-15: interpola constante de ícone do próprio arquivo. JS-02: sem listener global.",
        "rules": {"innerhtml_dynamic_without_escape": 1, "enhancer_without_destroy": 1},
    },
    "static/js/pages/justificativas-index.js": {
        "reason": "NOVO-15: interpola constante de ícone declarada no próprio arquivo.",
        "rules": {"innerhtml_dynamic_without_escape": 1},
    },
    "static/js/pages/termos-form.js": {
        "reason": "NOVO-15: interpola constante de ícone declarada no próprio arquivo.",
        "rules": {"innerhtml_dynamic_without_escape": 1},
    },
    "static/js/pages/ordens-servico-form.js": {
        "reason": "NOVO-15: interpola constante de ícone declarada no próprio arquivo.",
        "rules": {"innerhtml_dynamic_without_escape": 1},
    },
    "static/js/pages/planos-trabalho-wizard.js": {
        "reason": "NOVO-15: html vindo do servidor, já sanitizado na renderização do template.",
        "rules": {"innerhtml_dynamic_without_escape": 1},
    },
    # JS-02 — enhancers sem `destroy` porque não há o que desmontar. A razão de
    # cada um está em core/tests/test_js_registry_lifecycle.py, que fixa a lista.
    "static/js/components/card-toggle.js":          {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/collection.js":           {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/diaria-derivados.js":     {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/document-number-field.js": {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/fields-init.js":          {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/masks.js":                {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/state-toggle.js":         {"reason": "JS-02: sem listener global.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/components/file-picker.js":          {"reason": "JS-02: delegação de página registrada uma vez no módulo.", "rules": {"enhancer_without_destroy": 1}},
    "static/js/core/app.js":                        {"reason": "JS-02: delegação de página com guard de módulo. Higiene: o catch vazio é fallback de JSON.parse de atributo malformado.", "rules": {"enhancer_without_destroy": 1, "empty_catch": 1}},
    # Higiene: `catch` vazio deliberado, com o motivo escrito no próprio código.
    "static/js/components/document-search.js": {
        "reason": "Falha de rede não pode derrubar o campo; o comentário no código explica.",
        "rules": {"empty_catch": 1},
    },
    "static/js/core/theme-shared.js": {
        "reason": "localStorage indisponível (modo privado) não pode quebrar o tema.",
        "rules": {"empty_catch": 1},
    },
}
JS_RULES_ERRO = [
    (
        "raw_fetch",
        re.compile(r"\bfetch\s*\("),
        "fetch() cru — usar CV.http",
        JS_HTTP_OWNER,
    ),
    (
        "duplicated_csrf_header",
        re.compile(r"""["']X-CSRFToken["']"""),
        "Cabeçalho CSRF fora do núcleo — usar CV.http",
        JS_HTTP_OWNER,
    ),
    (
        "duplicated_debounce",
        re.compile(r"\b(?:function\s+debounc\w*\s*\(|(?:const|let|var)\s+debounce\s*=)"),
        "Implementação local de debounce — usar CV.util.debounce",
        JS_UTIL_OWNER,
    ),
    (
        "duplicated_escape_html",
        re.compile(r"\b(?:function\s+(?:escapeHtml|esc)\s*\(|(?:const|let|var)\s+(?:escapeHtml|esc)\s*=)"),
        "Implementação local de escape HTML — usar CV.util.escapeHtml",
        JS_UTIL_OWNER,
    ),
    (
        "duplicated_normalize",
        re.compile(r"""\.normalize\s*\(\s*["']NFD["']\s*\)"""),
        "Implementação local de normalização textual — usar CV.util.normalize",
        JS_UTIL_OWNER,
    ),
    (
        "native_feedback",
        re.compile(r"(?<![\w.])(?:window\.)?(?:alert|confirm)\s*\("),
        "Feedback nativo — usar CV.feedback",
        None,
    ),
    # JS-11 — a duplicação aconteceu porque `onlyDigits` não tinha saída
    # pública em `masks.js`; agora tem, e estas duas regras impedem a volta.
    (
        "duplicated_only_digits",
        re.compile(r"\b(?:function\s+onlyDigits\s*\(|(?:const|let|var)\s+onlyDigits\s*=\s*function)"),
        "Implementação local de onlyDigits — usar CV.masks.onlyDigits",
        JS_MASKS_OWNER,
    ),
    (
        "duplicated_mask_cep",
        re.compile(r"\b(?:function\s+maskCep\s*\(|(?:const|let|var)\s+maskCep\s*=\s*function)"),
        "Máscara de CEP local — usar CV.masks.format(valor, 'cep')",
        JS_MASKS_OWNER,
    ),
]

# JS-05 — regras que travam a regressão de JS-01, JS-02 e JS-06.
#
# O auditor cobria 6 dos ~9 invariantes medidos. Faltavam justamente as três
# que guardam os defeitos irmãos desta etapa: sem elas, os dois commits
# anteriores podiam ser desfeitos com o CI verde. São aplicadas sobre o arquivo
# inteiro, não linha a linha, porque as três atravessam linhas.

# Classe CSS como condição de lógica (trava JS-06). Estado (`is-*`, `has-*`) é
# vocabulário legítimo de comportamento e fica de fora; o que a regra persegue
# é depender do nome de um componente — o que impede renomear o CSS.
_JS_CLASSE_LOGICA = re.compile(
    r"""classList\.contains\(\s*(['"])(?!(?:is|has)-)[^'"]+\1"""
)

# Enhancer sem `destroy` (trava JS-02). O registry aceita o terceiro argumento
# e o MutationObserver o chama; sem ele o componente vaza em silêncio.
_JS_ENHANCER_SEM_DESTROY = re.compile(
    r"""registerEnhancer\(\s*(['"])[^'"]+\1\s*,\s*[A-Za-z_$][\w$.]*\s*\)"""
)

# `catch` que engole o erro sem nem registrar.
_JS_CATCH_VAZIO = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")

_JS_INNERHTML = re.compile(r"\.innerHTML\s*\+?=\s*")

JS_RULES_ARQUIVO = {
    "css_class_as_logic": "Nome de classe CSS como condição de lógica — usar data-* dedicado",
    "enhancer_without_destroy": "registerEnhancer sem `destroy` — o registry chama, o componente ignora",
    "innerhtml_dynamic_without_escape": "innerHTML com dado dinâmico sem CV.util.escapeHtml",
    "empty_catch": "catch vazio — engole o erro sem registrar",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_exception(rel_path: str, rule_name: str, exceptions: dict) -> tuple[bool, str]:
    """Return (is_exception, reason)."""
    exc = exceptions.get(rel_path, {})
    if rule_name in exc.get("rules", set()):
        return True, exc["reason"]
    return False, ""


def js_ceiling(rel_path: str, rule_name: str) -> tuple[int | None, str]:
    """Teto declarado para (arquivo, regra) em JS_EXCEPTIONS, ou (None, "")."""
    exc = JS_EXCEPTIONS.get(rel_path, {})
    rules = exc.get("rules", {})
    if rule_name in rules:
        return rules[rule_name], exc["reason"]
    return None, ""


_JS_COMENTARIO_BLOCO = re.compile(r"/\*.*?\*/", re.S)
_JS_COMENTARIO_LINHA = re.compile(r"//[^\n]*")


def strip_js_comments(source: str) -> str:
    """Apaga comentários preservando o número de linhas.

    Sem isto a regra dispara no comentário que explica por que o padrão saiu —
    é o mesmo erro de método que o NOVO-11 registra no auditor de ORM, que
    conta `.objects` dentro de docstring.
    """
    source = _JS_COMENTARIO_BLOCO.sub(lambda m: "\n" * m.group(0).count("\n"), source)
    return _JS_COMENTARIO_LINHA.sub("", source)


def _linha_de(source: str, pos: int) -> int:
    return source.count("\n", 0, pos) + 1


def _expressao_apos(source: str, inicio: int) -> str:
    """Devolve a expressão atribuída, até o `;` de nível zero (atravessa linhas)."""
    i, profundidade, aspas, saida = inicio, 0, None, []
    while i < len(source):
        c = source[i]
        if aspas:
            if c == "\\":
                saida.append(source[i : i + 2])
                i += 2
                continue
            if c == aspas:
                aspas = None
        elif c in "\"'`":
            aspas = c
        elif c in "([{":
            profundidade += 1
        elif c in ")]}":
            profundidade -= 1
        elif c == ";" and profundidade <= 0:
            break
        saida.append(c)
        i += 1
    return "".join(saida).strip()


def js_file_findings(source: str, raw_source: str) -> list[tuple[str, int, str]]:
    """Regras de arquivo inteiro (JS-05). Devolve [(regra, linha, trecho)].

    `source` vem sem comentários; `raw_source` é o texto original. A diferença
    importa para `empty_catch`: um `catch` cujo corpo é só um comentário está
    documentado — é o contrário do defeito — e só o texto cru sabe disso.
    """
    achados: list[tuple[str, int, str]] = []

    for padrao, regra in (
        (_JS_CLASSE_LOGICA, "css_class_as_logic"),
        (_JS_ENHANCER_SEM_DESTROY, "enhancer_without_destroy"),
    ):
        for m in padrao.finditer(source):
            achados.append((regra, _linha_de(source, m.start()), m.group(0)))

    for m in _JS_CATCH_VAZIO.finditer(raw_source):
        achados.append(("empty_catch", _linha_de(raw_source, m.start()), m.group(0).strip()))

    for m in _JS_INNERHTML.finditer(source):
        expressao = _expressao_apos(source, m.end())
        if expressao in ('""', "''", "``"):
            continue  # limpeza de container, sem dado
        if "escapeHtml" in expressao:
            continue
        dinamico = re.search(r"\$\{|\+|[A-Za-z_$][\w$]*\s*\(|^[A-Za-z_$][\w$.]*$", expressao)
        if not dinamico:
            continue  # literal estático
        achados.append(
            (
                "innerhtml_dynamic_without_escape",
                _linha_de(source, m.start()),
                expressao.replace("\n", " "),
            )
        )

    return achados


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def audit_templates() -> list[tuple]:
    """Return list of (level, rel_path, line_no, rule, message, line_text)."""
    findings = []
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        rp = rel(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="latin-1").splitlines()

        for idx, line in enumerate(lines, start=1):
            for rule_name, pattern, message in TEMPLATE_RULES_ERRO:
                if pattern.search(line):
                    is_exc, reason = check_exception(rp, rule_name, TEMPLATE_EXCEPTIONS)
                    level = "EXCEC" if is_exc else "ERRO"
                    findings.append((level, rp, idx, rule_name, message, line.strip(), reason))

            for rule_name, pattern, message in TEMPLATE_RULES_AVISO:
                if pattern.search(line):
                    is_exc, reason = check_exception(rp, rule_name, TEMPLATE_EXCEPTIONS)
                    level = "EXCEC" if is_exc else "AVISO"
                    findings.append((level, rp, idx, rule_name, message, line.strip(), reason))

    return findings


def audit_css() -> list[tuple]:
    findings = []
    # `rglob`, nao `glob`: o `NOVO-66` moveu 58 arquivos para subpastas, e com a
    # varredura rasa o auditor passou a enxergar 2 arquivos em vez de 60 — os
    # avisos cairiam de 240 para 18 sem nenhuma melhora no codigo. Catraca que
    # desce por cegueira e pior que catraca nenhuma.
    for path in sorted(CSS_DIR.rglob("*.css")):
        rp = rel(path)
        if rp in COBERTURA_ADIADA:
            continue
        # Bundle gerado (NOVO-12): auditar as fontes, não a concatenação.
        if path.name.endswith(".bundle.css"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="latin-1").splitlines()

        is_global = rp in GLOBAL_CSS

        for idx, line in enumerate(lines, start=1):
            # Skip pure comment lines for most rules
            is_comment = _CSS_COMMENT_LINE.match(line) is not None

            if not is_comment:
                # Domain selectors / route tokens — only in global CSS files
                if is_global:
                    for rule_name, pattern, message in CSS_RULES_AVISO:
                        if pattern.search(line):
                            is_exc, reason = check_exception(rp, rule_name, CSS_EXCEPTIONS)
                            level = "EXCEC" if is_exc else "AVISO"
                            findings.append((level, rp, idx, rule_name, message, line.strip(), reason))

                # Hex colors outside tokens/theme — in any CSS file
                if _CSS_VALUE_LINE.search(line):
                    is_exc, reason = check_exception(rp, "hex_color_outside_tokens", CSS_EXCEPTIONS)
                    level = "EXCEC" if is_exc else "AVISO"
                    findings.append((level, rp, idx, "hex_color_outside_tokens",
                                     "Cor hex em valor CSS — usar var() de token",
                                     line.strip(), reason))

    return findings


def audit_js() -> list[tuple]:
    findings = []
    for path in sorted(JS_DIR.rglob("*.js")):
        rp = rel(path)
        # Bundle gerado (NOVO-12): auditar as fontes, não a concatenação.
        if path.name.endswith(".bundle.js"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="latin-1").splitlines()

        for idx, line in enumerate(lines, start=1):
            for rule_name, pattern, message, owner in JS_RULES_ERRO:
                if owner and rp == owner:
                    continue
                if pattern.search(line):
                    findings.append(("ERRO", rp, idx, rule_name, message, line.strip(), ""))

        # JS-05 — regras de arquivo inteiro, com teto por (arquivo, regra).
        bruto = "\n".join(lines)
        por_regra: dict[str, list[tuple[int, str]]] = {}
        for regra, linha, trecho in js_file_findings(strip_js_comments(bruto), bruto):
            por_regra.setdefault(regra, []).append((linha, trecho))

        for regra, ocorrencias in por_regra.items():
            teto, motivo = js_ceiling(rp, regra)
            mensagem = JS_RULES_ARQUIVO[regra]
            if teto is not None and len(ocorrencias) <= teto:
                for linha, trecho in ocorrencias:
                    findings.append(("EXCEC", rp, linha, regra, mensagem, trecho, motivo))
                continue
            if teto is not None:
                mensagem = (
                    f"{mensagem} — teto declarado é {teto}, encontrei {len(ocorrencias)}"
                )
            for linha, trecho in ocorrencias:
                findings.append(("ERRO", rp, linha, regra, mensagem, trecho, ""))

    return findings


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def print_findings(findings: list[tuple]) -> tuple[int, int]:
    """Print grouped findings. Returns counts of errors and warnings."""
    erros   = [f for f in findings if f[0] == "ERRO"]
    avisos  = [f for f in findings if f[0] == "AVISO"]
    excecoes = [f for f in findings if f[0] == "EXCEC"]

    if erros:
        print("\n=== ERROS (devem ser corrigidos) ===")
        for _level, rp, ln, rule, msg, text, _reason in erros:
            print(f"  {rp}:{ln} [{rule}] {msg}")
            print(f"    > {text[:120]}")

    if avisos:
        print("\n=== AVISOS (dívida técnica conhecida) ===")
        for _level, rp, ln, rule, msg, text, _reason in avisos:
            print(f"  {rp}:{ln} [{rule}] {msg}")
            print(f"    > {text[:120]}")

    unique_excecoes: set[str] = set()
    if excecoes:
        print("\n=== EXCECOES documentadas (informativo) ===")
        for _level, rp, _ln, rule, _msg, _text, reason in excecoes:
            key = f"{rp}:{rule}"
            if key not in unique_excecoes:
                print(f"  {rp} [{rule}] -- {reason}")
                unique_excecoes.add(key)

    print(f"\nTotal: {len(erros)} ERROS, {len(avisos)} AVISOS, {len(unique_excecoes)} EXCECOES (arquivo/regra)")

    return len(erros), len(avisos)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-warnings",
        type=int,
        default=None,
        help="Falha se a dívida não bloqueante ultrapassar este limite.",
    )
    args = parser.parse_args()
    print("== Auditoria Frontend Standards — Central de Viagens 3.0 ==")

    template_findings = audit_templates()
    css_findings = audit_css()
    js_findings = audit_js()
    all_findings = template_findings + css_findings + js_findings

    if not all_findings:
        print("Nenhuma suspeita encontrada. ✅")
        sys.exit(0)

    erros, avisos = print_findings(all_findings)
    if args.max_warnings is not None and avisos > args.max_warnings:
        print(
            f"\nERRO: avisos aumentaram para {avisos}; "
            f"a linha de base aceita no máximo {args.max_warnings}."
        )
        erros += 1
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
