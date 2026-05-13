"""
Auditor de padrões frontend — Central de Viagens 3.0
Saída em três níveis:
  ERRO  — violação que deve ser corrigida antes do merge (exit 1)
  AVISO — dívida técnica conhecida, não bloqueia (exit 0)
  EXCEC — desvio documentado como exceção oficial (exit 0, informativo)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
CSS_DIR = ROOT / "static" / "css"

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
        "reason": ".roteiro-editor__* sao joint selectors de .app-form-shell -- pareados, nao removiveis sem refactor. --route-* tokens sao variaveis globais de tema.",
        "rules": {"domain_selector_in_global", "route_token_in_global", "hex_color_outside_tokens"},
    },
    "static/css/app-page.css": {
        "reason": ".roteiro-detail/* em app-page.css: domínio a mover para roteiros.css (Prompt 6).",
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
    "static/css/auth.css": {
        "reason": "CSS de autenticação — isolado, pode ter cores específicas.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/dashboard.css": {
        "reason": "Dashboard e excecao oficial -- hex restantes sao fallbacks de var() no botao do hero.",
        "rules": {"hex_color_outside_tokens"},
    },
    "static/css/buttons.css": {
        "reason": "Gradientes de botão danger sem token equivalente — dívida de token a criar.",
        "rules": {"hex_color_outside_tokens"},
    },
}

# ---------------------------------------------------------------------------
# Regras de templates
# ---------------------------------------------------------------------------
TEMPLATE_RULES_ERRO = [
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
    "static/css/buttons.css",
    "static/css/app-ui.css",
    "static/css/app-page.css",
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


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def print_findings(findings: list[tuple]) -> int:
    """Print grouped findings. Returns count of ERROs."""
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

    return len(erros)


def main() -> None:
    print("== Auditoria Frontend Standards — Central de Viagens 3.0 ==")

    template_findings = audit_templates()
    css_findings = audit_css()
    all_findings = template_findings + css_findings

    if not all_findings:
        print("Nenhuma suspeita encontrada. ✅")
        sys.exit(0)

    erros = print_findings(all_findings)
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
