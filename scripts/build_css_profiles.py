#!/usr/bin/env python3
"""Gera perfis de CSS do shell a partir da cobertura multiestado do PF-02.

O manifesto guarda apenas hashes de regras observadas. As regras continuam
editáveis nas fontes canônicas e os perfis preservam a ordem da cascata do
bundle completo. ``--capture`` recalibra o manifesto com relatórios produzidos
por ``medir_css_por_rota.py --include-matched-css``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import tinycss2

ROOT = Path(__file__).resolve().parents[1]
STATIC_CSS = ROOT / "static" / "css"
MANIFEST = ROOT / "scripts" / "css_profiles_manifest.json"
OUTPUT_DIR = STATIC_CSS / "profiles"

PROFILE_ROUTES: dict[str, tuple[str, ...]] = {
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


def _declares_custom_property(rule) -> bool:
    """A regra declara pelo menos um token (`--x: valor`).

    A cobertura do CDP mede *casamento de seletor*, numa passagem só, no tema
    claro. Nenhuma regra dentro de `html[data-theme="dark"]` casa nessa
    passagem, então o bloco de tokens do tema escuro era podado dos 15 perfis e
    as 42 rotas com perfil serviam o vocabulário CLARO com `data-theme="dark"`
    aplicado (`NOVO-20260820-211943-6a686a695549`). Medido: `--color-bg` saía
    `#f7fbff` no lugar de `#0d1725`.

    Nada disso aparece na paridade perfil/bundle: podar uma DECLARAÇÃO de token
    não muda pixel algum até alguém lê-la, e no tema claro ninguém lia a versão
    escura. Só quebra quando o usuário troca o tema.

    Bloco de token entra sempre, pelo mesmo motivo que `@font-face`,
    `@property` e `@import` já entram em `_render_rules`: a régua da cobertura
    não sabe medi-los. O critério é "declara token", não "só declara token" — o
    bloco raiz do tema escuro traz 236 declarações e uma delas é `color-scheme`,
    que é justamente o que veste barra de rolagem e controle nativo. E regra que
    declara token junto com pintura tem de entrar inteira: podá-la tiraria o
    token dos descendentes.
    """
    return any(
        item.type == "declaration" and item.name.startswith("--")
        for item in tinycss2.parse_blocks_contents(
            rule.content, skip_comments=True, skip_whitespace=True
        )
    )


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


def _with_dom_families(
    rules, selected: set[str], dom_classes: set[str]
) -> set[str]:
    qualified = list(_qualified_rules(rules))
    result = set(selected)
    for rule in qualified:
        selector = _selector(rule)
        classes = set(_CLASS.findall(selector))
        structural_classes = {
            class_name for class_name in classes if not _STATE_CLASS.match(class_name)
        }
        # Regras normais presentes no DOM ja entram pelos fragmentos medidos do
        # manifesto. A expansao por familia existe somente para estados que o
        # CDP nao casa sem interacao (hover/focus/checked etc.). Classes de
        # estado como ``is-open`` so aparecem depois da interacao e, portanto,
        # nao podem ser exigidas no retrato inicial do DOM.
        if (
            structural_classes
            and structural_classes.issubset(dom_classes)
            and _INTERACTIVE_STATE.search(selector)
        ):
            result.add(_rule_id(rule))
        elif _INTERACTIVE_STATE.search(selector) and not classes and re.search(
            r"\b(?:a|button|input|select|textarea):", selector
        ):
            result.add(_rule_id(rule))
    return result


def _shell_sheet(route: dict) -> dict:
    candidates = [
        sheet
        for sheet in route["stylesheet_usage"]
        if sheet["source_url"].endswith("/shell.bundle.css")
        or sheet["source_url"].endswith("/shell.form-components.bundle.css")
    ]
    if len(candidates) != 1:
        raise ValueError("a rota não possui exatamente um bundle de shell")
    return candidates[0]


def _expanded_source(source_name: str) -> str:
    text = (STATIC_CSS / source_name).read_text(encoding="utf-8")

    def replace(match) -> str:
        relative = match.group(1)
        if relative.startswith(("http://", "https://")):
            return match.group(0)
        imported = (STATIC_CSS / relative).resolve()
        if not imported.is_relative_to(STATIC_CSS.resolve()):
            raise ValueError(f"import CSS fora de static/css: {relative}")
        return imported.read_text(encoding="utf-8")

    return _IMPORT.sub(replace, text)


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
        source_names = {
            _shell_sheet(routes[slug])["source_url"].rsplit("/", 1)[-1]
            for routes in loaded
            for slug in slugs
            if slug in routes
        }
        if len(source_names) != 1:
            raise ValueError(f"perfil mistura variantes de shell: {profile}={source_names}")
        source = source_names.pop()
        suffixes = tuple(f"/static/css/{item}" for item in _source_sheet_suffixes(source))
        for routes in loaded:
            for slug in slugs:
                route = routes.get(slug)
                if not route:
                    continue
                dom_classes.update(route.get("dom_classes", []))
                for sheet in route["stylesheet_usage"]:
                    if sheet["source_url"].endswith(suffixes):
                        for fragment in sheet.get("matched_fragments", []):
                            rule_ids.update(_fragment_rule_ids(fragment))
        if not rule_ids:
            raise ValueError(f"perfil sem cobertura: {profile}")
        profiles[profile] = {
            "source": source,
            "routes": list(slugs),
            "rule_ids": sorted(rule_ids),
            "dom_classes": sorted(dom_classes),
        }
    return {"schema_version": 1, "profiles": profiles}


def _render_rules(rules, selected: set[str], used_keyframes: set[str]) -> str:
    chunks: list[str] = []
    for rule in rules:
        if rule.type == "qualified-rule":
            if _rule_id(rule) in selected or _declares_custom_property(rule):
                chunks.append(_serialized(rule))
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
        body = _render_rules(nested, selected, used_keyframes)
        if body:
            prelude = tinycss2.serialize(rule.prelude).strip()
            chunks.append(f"@{rule.at_keyword} {prelude} {{\n{body}\n}}")
    return "\n".join(chunks)


def build(manifest: dict) -> dict[Path, str]:
    outputs = {}
    banner = "/* AUTO-GENERATED by scripts/build_css_profiles.py — do not edit. */\n"
    for profile, config in manifest["profiles"].items():
        rules = tinycss2.parse_stylesheet(
            _expanded_source(config["source"]),
            skip_comments=True,
            skip_whitespace=True,
        )
        selected = _with_dom_families(
            rules,
            set(config["rule_ids"]),
            set(config.get("dom_classes", [])),
        )
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
        body = _render_rules(rules, selected, keyframe_names)
        outputs[OUTPUT_DIR / f"{profile}.css"] = banner + body + "\n"
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
