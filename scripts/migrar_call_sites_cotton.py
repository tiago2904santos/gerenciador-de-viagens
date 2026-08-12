"""Migra includes estáticos de ``templates/components`` para tags Cotton.

A E5 de ``docs/PLANO_RECONSTRUCAO_FRONT_2026-08.md`` exige commits por app.
Por isso o comando recebe um ou mais escopos explícitos e só escreve neles::

    python scripts/migrar_call_sites_cotton.py --write templates/oficios
    python scripts/migrar_call_sites_cotton.py --check templates

Includes dinâmicos e partials de aplicação não são adivinhados. Um include cujo
alvo não é uma string literal de ``components/`` permanece intacto; se o texto
indicar que pretendia alcançar esse namespace, o comando falha para exigir uma
decisão explícita.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from pathlib import Path

from django.utils.text import smart_split


COMPONENT_PREFIX = "components/"
INCLUDE_RE = re.compile(r"{%\s*include\s+.*?%}", re.DOTALL)
EXTENDS_RE = re.compile(r"{%\s*extends\s+.*?%}", re.DOTALL)
QUOTED_RE = re.compile(r"^(?P<quote>['\"])(?P<value>.*)(?P=quote)$", re.DOTALL)
LEGACY_PATH_RE = re.compile(
    r"(?P<quote>['\"])components/(?P<path>[A-Za-z0-9_./-]+\.html)(?P=quote)"
)


def _literal(token: str) -> str | None:
    match = QUOTED_RE.fullmatch(token)
    return match.group("value") if match else None


def _atributo_dinamico(nome: str, expressao: str) -> str:
    if '"' not in expressao:
        return f':{nome}="{expressao}"'
    if "'" not in expressao:
        return f":{nome}='{expressao}'"
    if not any(char.isspace() for char in expressao):
        return f":{nome}={expressao}"
    raise ValueError(
        f"expressão dinâmica não pode ser citada com segurança: {nome}={expressao}"
    )


def converter_include(tag: str) -> str:
    conteudo = tag[2:-2].strip()
    tokens = list(smart_split(conteudo))
    if len(tokens) < 2 or tokens[0] != "include":
        return tag

    alvo = _literal(tokens[1])
    if alvo is None:
        if COMPONENT_PREFIX in tag:
            raise ValueError(f"include de componente não suportado: {tag}")
        return tag
    if not alvo.startswith(COMPONENT_PREFIX):
        return tag
    if not alvo.endswith(".html"):
        raise ValueError(f"componente sem sufixo .html: {alvo}")

    restante = tokens[2:]
    somente = False
    atributos: list[str] = []
    aliases: list[str] = []
    if restante:
        if restante[0] == "with":
            restante = restante[1:]
        elif restante[0] != "only":
            raise ValueError(f"include de componente não suportado: {tag}")

    for token in restante:
        if token == "only":
            somente = True
            continue
        if "=" not in token:
            raise ValueError(f"argumento sem nome em include de componente: {token}")
        nome, expressao = token.split("=", 1)
        valor_literal = _literal(expressao)
        if valor_literal is not None:
            atributos.append(f"{nome}={expressao}")
        elif "|" in expressao:
            alias = f"cotton_attr_{nome}"
            aliases.append(f"{alias}={expressao}")
            atributos.append(f':{nome}="{alias}"')
        else:
            atributos.append(_atributo_dinamico(nome, expressao))

    nome_componente = alvo.removeprefix(COMPONENT_PREFIX).removesuffix(".html")
    nome_componente = nome_componente.replace("/", ".")
    partes = [f"<c-{nome_componente}", *atributos]
    if somente:
        partes.append("only")
    componente = " ".join(partes) + " />"
    if aliases:
        return f"{{% with {' '.join(aliases)} %}}{componente}{{% endwith %}}"
    return componente


def converter_extends(tag: str) -> str:
    conteudo = tag[2:-2].strip()
    tokens = list(smart_split(conteudo))
    if len(tokens) != 2 or tokens[0] != "extends":
        return tag
    alvo = _literal(tokens[1])
    if not alvo or not alvo.startswith(COMPONENT_PREFIX):
        return tag
    canonico = "cotton/" + alvo.removeprefix(COMPONENT_PREFIX)
    quote = tokens[1][0]
    return f"{{% extends {quote}{canonico}{quote} %}}"


def converter_texto(texto: str) -> tuple[str, int]:
    alterados = 0

    def substituir(match: re.Match[str]) -> str:
        nonlocal alterados
        original = match.group(0)
        convertido = converter_include(original)
        if convertido != original:
            alterados += 1
        return convertido

    convertido = INCLUDE_RE.sub(substituir, texto)

    def substituir_extends(match: re.Match[str]) -> str:
        nonlocal alterados
        original = match.group(0)
        novo = converter_extends(original)
        if novo != original:
            alterados += 1
        return novo

    convertido = EXTENDS_RE.sub(substituir_extends, convertido)

    def substituir_caminho(match: re.Match[str]) -> str:
        nonlocal alterados
        alterados += 1
        quote = match.group("quote")
        return f"{quote}cotton/{match.group('path')}{quote}"

    return LEGACY_PATH_RE.sub(substituir_caminho, convertido), alterados


def iterar_templates(escopos: Iterable[Path]) -> Iterable[Path]:
    vistos: set[Path] = set()
    for escopo in escopos:
        candidatos = [escopo] if escopo.is_file() else escopo.rglob("*.html")
        for caminho in candidatos:
            resolvido = caminho.resolve()
            if resolvido not in vistos:
                vistos.add(resolvido)
                yield caminho


def executar(escopos: list[Path], *, escrever: bool) -> int:
    total = 0
    alteracoes: list[tuple[Path, str, int]] = []
    for caminho in iterar_templates(escopos):
        original = caminho.read_text(encoding="utf-8")
        convertido, quantidade = converter_texto(original)
        if not quantidade:
            continue
        total += quantidade
        alteracoes.append((caminho, convertido, quantidade))

    for caminho, convertido, quantidade in alteracoes:
        print(f"{caminho}: {quantidade}")
        if escrever:
            caminho.write_text(convertido, encoding="utf-8", newline="")

    acao = "migradas" if escrever else "pendentes"
    print(f"{total} referência(s) {acao} em {len(alteracoes)} arquivo(s)")
    return 0 if escrever or total == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--write", action="store_true", help="reescreve os escopos")
    modo.add_argument("--check", action="store_true", help="falha se houver includes pendentes")
    parser.add_argument("scopes", nargs="+", type=Path, help="arquivos ou diretórios explícitos")
    args = parser.parse_args()
    return executar(args.scopes, escrever=args.write)


if __name__ == "__main__":
    raise SystemExit(main())
