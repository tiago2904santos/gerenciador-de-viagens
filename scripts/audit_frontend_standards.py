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
# Vazio de proposito. A unica entrada que existia dispensava
# `templates/core/dashboard.html` de `legacy_page_header` — e o dashboard nao
# escreve `page-header` em lugar nenhum desde a reescrita. A dispensa sobrevivia
# a um defeito da regra, nao a um uso real (NOVO-39). Excecao de ARQUIVO esconde
# divida: se a regra esta certa, o codigo se ajusta; se esta errada, corrige-se a
# regra. Foi a decisao da fase 4 para o CSS, e vale igual aqui.
TEMPLATE_EXCEPTIONS: dict[str, dict] = {}

# A camada de token e o unico lugar do sistema onde uma cor pode ser escrita a
# mao — nao e "excecao", e a definicao da regra. Carrega-la como dispensa era o
# auditor nao conhecer a propria arquitetura (NOVO-30 fase 4).
CAMADA_DE_TOKEN = frozenset({
    "static/css/00-palette.css",
    "static/css/01-tokens.css",
})

CSS_EXCEPTIONS: dict[str, dict] = {
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
    # Nao basta olhar `href="#"` escrito a mao: a ancora vazia tambem chega ao
    # HTML por PARAMETRO de componente — `secondary_url="#"`, `back_url="#"`,
    # `primary_action_url="#"`. Eram 19 ocorrencias invisiveis para a regra
    # anterior, contra 10 visiveis (NOVO-40).
    ("href_hash",            re.compile(r'\b[a-z_]*(?:href|url|link)[a-z_]*=(["\'])#\1'),
     'Âncora vazia — link que só pula a página para o topo; usar URL real ou <button>'),
    # Ver `_LEGACY_PAGE_HEADER_PAT`: o alvo e a classe CRUA `page-header`, nao a
    # familia `page-header-band`/`-stack`/`-rail`, que e o componente canonico.
    ("legacy_page_header",   re.compile(r'class="[^"]*\bpage-header(?![-\w])'),
     'Classe page-header crua — o componente é templates/components/ui/headers/page_header.html'),
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
# `\b` trata o hifen como fronteira, entao `\.page-header\b` casava a familia
# CANONICA inteira — `.page-header-band`, `.page-header-stack`, `.page-header-rail`
# — e nao a classe crua que a regra existe para pegar. Sao 60 linhas de CSS e 92
# de template de puro falso positivo (NOVO-39). O `(?![-\w])` fecha isso.
_LEGACY_PAGE_HEADER_PAT = re.compile(r'^\s*\.page-header(?![-\w])')
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


def audit_css() -> list[tuple]:
    findings = []
    for path in sorted(CSS_DIR.glob("*.css")):
        rp = rel(path)
        # Bundle gerado (NOVO-12): auditar as fontes, não a concatenação.
        if path.name.endswith(".bundle.css"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="latin-1").splitlines()

        is_global = rp in GLOBAL_CSS

        # Comentario de BLOCO: `_CSS_COMMENT_LINE` so reconhece a linha que
        # ABRE o comentario. As linhas de dentro passavam por codigo — e um
        # cabecalho que citava `.oficio-stepper-*` em prosa era acusado de
        # seletor de dominio em CSS global (NOVO-41). Aqui o estado do bloco e
        # levado de uma linha para a outra.
        dentro_de_bloco = False

        for idx, line in enumerate(lines, start=1):
            abre = line.count("/*")
            fecha = line.count("*/")
            comeca_dentro = dentro_de_bloco
            if abre or fecha:
                dentro_de_bloco = abre > fecha if abre != fecha else dentro_de_bloco
                if abre and not fecha:
                    dentro_de_bloco = True
                elif fecha and not abre:
                    dentro_de_bloco = False

            is_comment = comeca_dentro or _CSS_COMMENT_LINE.match(line) is not None

            if not is_comment:
                # Domain selectors / route tokens — only in global CSS files
                if is_global:
                    for rule_name, pattern, message in CSS_RULES_AVISO:
                        if pattern.search(line):
                            is_exc, reason = check_exception(rp, rule_name, CSS_EXCEPTIONS)
                            level = "EXCEC" if is_exc else "AVISO"
                            findings.append((level, rp, idx, rule_name, message, line.strip(), reason))

                # Hex colors outside tokens/theme — em qualquer CSS que NAO
                # seja a camada de token (onde as sementes moram por definicao).
                if _CSS_VALUE_LINE.search(line) and rp not in CAMADA_DE_TOKEN:
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
