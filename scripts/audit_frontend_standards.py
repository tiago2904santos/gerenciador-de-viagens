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
    "static/css/forms.css": {
        "reason": ".roteiro-editor__* permanece como dominio em CSS global; --route-* sao variaveis globais de tema.",
        "rules": {"domain_selector_in_global", "route_token_in_global", "hex_color_outside_tokens"},
    },
    "static/css/cards.css": {
        "reason": ".oficio-card em cards.css: domínio a mover para oficios.css (Prompt 5).",
        "rules": {"domain_selector_in_global"},
    },
    "static/css/tokens.css": {
        "reason": "Arquivo de tokens — cores hex são a definição original, permitidas aqui.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/theme.css": {
        "reason": "Arquivo de tema — cores hex são a definição original, permitidas aqui.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/dark-redesign.css": {
        "reason": "Official dark-theme layer; literal values define its tokens and theme-only finishes.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/auth.css": {
        "reason": "CSS de autenticação — isolado, pode ter cores específicas.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/dashboard.css": {
        "reason": "Dashboard e excecao oficial -- hex restantes sao fallbacks de var() no botao do hero.",
        "rules": {"hex_color_outside_tokens"},
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
]

TEMPLATE_RULES_AVISO = [
    ("href_hash",            re.compile(r'\bhref="#"'),                'href="#" — checar se é intencional'),
    ("legacy_page_header",   re.compile(r'class="[^"]*\bpage-header\b'), 'Classe page-header legada — migrar para app-page-hero'),
    ("script_inline",        re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(?!\s*<)'), '<script> inline (sem src) — mover para arquivo .js'),
]

# ---------------------------------------------------------------------------
# Regras de CSS
# ---------------------------------------------------------------------------
# Arquivos CSS globais onde seletores de domínio não devem aparecer
GLOBAL_CSS = {
    "static/css/forms.css",
    "static/css/lists.css",
    "static/css/cards.css",
    "static/css/layout.css",
    "static/css/base.css",
    "static/css/utilities.css",
    "static/css/stages.css",
    "static/css/documents.css",
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
]

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


# ---------------------------------------------------------------------------
# Contadores de acessibilidade (H-06 / H-10)
#
# Estes dois não entram em `audit_templates()` porque não são regra de linha: um
# `aria-expanded` e o `aria-controls` que o acompanha moram na mesma **tag**, que
# quase sempre ocupa várias linhas. Medir linha a linha daria falso positivo em
# todo componente formatado com um atributo por linha.
# ---------------------------------------------------------------------------

_TAG_COM_ARIA_EXPANDED = re.compile(r"<[a-zA-Z][^>]*aria-expanded[^>]*>", re.S)
_TAG_LABEL = re.compile(r"<label\b[^>]*>", re.S)
# O laboratório de UI é bancada de protótipo, não tela de produção: não entra na
# catraca (mas continua sujeito às regras de linha de `audit_templates`).
_DIRS_FORA_DA_CATRACA = {"ui_lab", "ui_lab2", "dev"}

# Gatilhos cujo `aria-controls` é escrito pelo enhancer, não pelo template: o
# painel que eles abrem não tem id fixo porque o componente pode aparecer várias
# vezes na mesma página, e no caso do date picker o painel ainda é movido para
# `document.body` em runtime (`cv-date-picker.js`). O par gatilho/painel desses
# quatro é garantido por teste estrutural sobre o JS, não por grep de template.
ARIA_CONTROLS_VIA_ENHANCER = {
    "templates/components/ui/forms/date_picker.html":
        "cv-date-picker.js gera o id e move o painel para document.body",
    "templates/components/ui/forms/dropdown.html":
        "cv-select.js gera o id do menu flutuante",
    "templates/components/ui/forms/file_picker.html":
        "file-picker.js gera o id do painel de seleção",
    "templates/roteiros/partials/roteiro/_bate_volta_date_controls.html":
        "reusa os gatilhos do cv-date-picker",
}


def _templates_de_producao():
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        if _DIRS_FORA_DA_CATRACA & set(path.parts):
            continue
        yield path


def _ocorrencias_de_tag(
    pattern: re.Pattern,
    ausente: str,
    isentos: dict[str, str] | None = None,
) -> list[tuple[str, int, str]]:
    achados = []
    for path in _templates_de_producao():
        rp = rel(path)
        if isentos and rp in isentos:
            continue
        try:
            texto = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            texto = path.read_text(encoding="latin-1")
        for match in pattern.finditer(texto):
            if ausente in match.group(0):
                continue
            linha = texto[: match.start()].count("\n") + 1
            achados.append((rp, linha, " ".join(match.group(0).split())[:110]))
    return achados


def aria_expanded_sem_controls() -> list[tuple[str, int, str]]:
    """`aria-expanded` sem `aria-controls` — o leitor de tela não sabe o que abriu."""
    return _ocorrencias_de_tag(
        _TAG_COM_ARIA_EXPANDED, "aria-controls", ARIA_CONTROLS_VIA_ENHANCER
    )


def label_sem_for() -> list[tuple[str, int, str]]:
    """`<label>` sem `for` — clicar no rótulo não foca o campo quando ele é irmão."""
    return _ocorrencias_de_tag(_TAG_LABEL, "for=")


def audit_css() -> list[tuple]:
    findings = []
    for path in sorted(CSS_DIR.glob("*.css")):
        rp = rel(path)
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
        for level, rp, ln, rule, msg, text, reason in erros:
            print(f"  {rp}:{ln} [{rule}] {msg}")
            print(f"    > {text[:120]}")

    if avisos:
        print("\n=== AVISOS (dívida técnica conhecida) ===")
        for level, rp, ln, rule, msg, text, reason in avisos:
            print(f"  {rp}:{ln} [{rule}] {msg}")
            print(f"    > {text[:120]}")

    unique_excecoes: set[str] = set()
    if excecoes:
        print("\n=== EXCECOES documentadas (informativo) ===")
        for level, rp, ln, rule, msg, text, reason in excecoes:
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
    parser.add_argument(
        "--max-aria-expanded-sem-controls",
        type=int,
        default=None,
        help="Falha se houver mais `aria-expanded` sem `aria-controls` que este número (H-06).",
    )
    parser.add_argument(
        "--max-label-sem-for",
        type=int,
        default=None,
        help="Falha se houver mais `<label>` sem `for` que este número (H-10).",
    )
    args = parser.parse_args()
    print("== Auditoria Frontend Standards — Central de Viagens 3.0 ==")

    template_findings = audit_templates()
    css_findings = audit_css()
    js_findings = audit_js()
    all_findings = template_findings + css_findings + js_findings

    erros, avisos = 0, 0
    if all_findings:
        erros, avisos = print_findings(all_findings)
        if args.max_warnings is not None and avisos > args.max_warnings:
            print(
                f"\nERRO: avisos aumentaram para {avisos}; "
                f"a linha de base aceita no máximo {args.max_warnings}."
            )
            erros += 1
    else:
        print("Nenhuma suspeita de regra de linha encontrada. ✅")

    erros += _catraca(
        "aria-expanded sem aria-controls (H-06)",
        aria_expanded_sem_controls(),
        args.max_aria_expanded_sem_controls,
        ARIA_CONTROLS_VIA_ENHANCER,
    )
    erros += _catraca(
        "<label> sem for (H-10)",
        label_sem_for(),
        args.max_label_sem_for,
    )

    sys.exit(1 if erros else 0)


def _catraca(
    titulo: str,
    achados: list[tuple[str, int, str]],
    maximo: int | None,
    isentos: dict[str, str] | None = None,
) -> int:
    """Imprime uma catraca e devolve 1 se ela estourou. A catraca só desce."""
    print(f"\n=== {titulo} ===")
    for rp, linha, trecho in achados:
        print(f"  {rp}:{linha} {trecho}")
    for rp, motivo in sorted((isentos or {}).items()):
        print(f"  ISENTO {rp} -- {motivo}")
    print(f"Total: {len(achados)}")
    if maximo is not None and len(achados) > maximo:
        print(f"\nERRO: {len(achados)} ocorrências, acima da catraca de {maximo}.")
        return 1
    return 0


if __name__ == "__main__":
    main()
