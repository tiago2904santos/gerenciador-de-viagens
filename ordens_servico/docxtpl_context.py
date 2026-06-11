"""Contexto docxtpl para o modelo de Ordem de Serviço."""

from __future__ import annotations

from datetime import date
from itertools import groupby
from typing import Any

from django.utils import timezone

from cadastros.selectors import build_configuracao_context
from documentos.services.formatters import format_document_display
from oficios.docxtpl_context import _assinatura_nome_cargo, _build_endereco, _build_sede

from .models import OrdemServico

_MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


def _fmt_extenso(d: date) -> str:
    return f"{d.day} de {_MESES[d.month]} de {d.year}"


def _periodo_extenso(inicio: date | None, fim: date | None) -> str:
    if not inicio:
        return ""
    if not fim or fim == inicio:
        return f"no dia {_fmt_extenso(inicio)}"
    if inicio.month == fim.month and inicio.year == fim.year:
        return f"nos dias {inicio.day} a {fim.day} de {_MESES[inicio.month]} de {inicio.year}"
    return f"nos dias {_fmt_extenso(inicio)} a {_fmt_extenso(fim)}"


def _destinos_display(ordem: OrdemServico) -> str:
    destinos = list(ordem.destinos.select_related("estado").order_by("nome"))
    if not destinos:
        return ""
    parts = [
        f"{d.nome}/{d.estado.sigla}" if d.estado_id else d.nome
        for d in destinos
    ]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} e {parts[1]}"
    *primeiros, ultimo = parts
    return f"{', '.join(primeiros)} e {ultimo}"


def _is_acronym(word: str) -> bool:
    """ADM, DPC, PC etc. — all-uppercase ASCII short word."""
    clean = "".join(c for c in word if c.isalpha())
    return bool(clean) and clean.isascii() and clean.isupper() and len(clean) <= 5


def _pluralize_pt(word: str) -> str:
    """Simple Portuguese pluralization for first substantive (expects lowercase input)."""
    if not word:
        return word
    if word.endswith("ão"):
        return word[:-2] + "ões"
    last = word[-1]
    if last in "aeiouáéíóúàâêîôûãõ":
        return word + "s"
    if last == "l" and len(word) >= 2:
        prev = word[-2]
        return word[:-1] + ("is" if prev in "aeiouáéíóúàâêîôûãõ" else "eis")
    if last in ("r", "z", "n"):
        return word + "es"
    if last == "m":
        return word[:-1] + "ns"
    if last == "s":
        return word
    return word + "s"


def _cargo_display(nome: str, *, plural: bool) -> str:
    """'AGENTE DE POLICIA' -> 'agentes de policia' (plural) or 'agente de policia' (singular)."""
    tokens = nome.split()
    result = []
    for i, tok in enumerate(tokens):
        if _is_acronym(tok):
            result.append(tok)
        elif i == 0 and plural:
            result.append(_pluralize_pt(tok.lower()))
        else:
            result.append(tok.lower())
    return " ".join(result)


def _equipe_deslocamento(ordem: OrdemServico) -> str:
    servidores = list(
        ordem.servidores.select_related("cargo").order_by("cargo__nome", "nome")
    )
    if not servidores:
        return "da equipe"

    _SEM_CARGO = "\xff"

    def cargo_key(s):
        return s.cargo.nome if s.cargo_id else _SEM_CARGO

    partes = []
    for cargo_nome, grupo in groupby(sorted(servidores, key=cargo_key), key=cargo_key):
        membros = list(grupo)
        nomes = [format_document_display(s.nome) or str(s.nome) for s in membros]
        n = len(nomes)
        lista = ", ".join(nomes[:-1]) + f" e {nomes[-1]}" if n > 1 else nomes[0]

        is_first = not partes

        if cargo_nome == _SEM_CARGO:
            partes.append(lista)
            continue

        if n == 1:
            cargo_txt = _cargo_display(cargo_nome, plural=False)
            # primeiro grupo usa contração "do", demais usam "o"
            artigo = "do" if is_first else "o"
            partes.append(f"{artigo} {cargo_txt} {nomes[0]}")
        else:
            cargo_txt = _cargo_display(cargo_nome, plural=True)
            # primeiro grupo usa contração "dos", demais usam "os"
            artigo = "dos" if is_first else "os"
            partes.append(f"{artigo} {cargo_txt} {lista}")

    if not partes:
        return "da equipe"
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + f" e {partes[-1]}"


def build_os_docxtpl_context(ordem: OrdemServico) -> dict[str, Any]:
    inst = build_configuracao_context()

    def _txt(v: object) -> str:
        return str(v or "").strip()

    sigla = _txt(inst.get("sigla_orgao"))
    unidade_campo = _txt(inst.get("unidade"))
    nome_orgao = _txt(inst.get("nome_orgao"))
    divisao = _txt(inst.get("divisao"))
    unidade = unidade_campo or nome_orgao or sigla

    nome_chefia, cargo_chefia = _assinatura_nome_cargo(inst, "ORDEM_SERVICO")

    numero_str = (
        f"{ordem.numero:03d}/{ordem.ano}"
        if ordem.numero and ordem.ano
        else str(ordem.pk or "—")
    )

    return {
        "ordem_de_servico": numero_str,
        "unidade_abreviado": sigla or unidade,
        "nome_chefia": format_document_display(nome_chefia) if nome_chefia else "",
        "cargo_chefia": format_document_display(cargo_chefia) if cargo_chefia else "",
        "divisao_capitalize": format_document_display(divisao).title() if divisao else "",
        # UPPERCASE diretamente do banco — sem format_document_display:
        "divisao": divisao,
        "unidade": unidade,
        "unidade_rodape": unidade,
        "destino": _destinos_display(ordem),
        "data_extenso": _periodo_extenso(ordem.data_evento_inicio, ordem.data_evento_fim),
        "motivo": format_document_display(_txt(ordem.motivo)) if _txt(ordem.motivo) else "",
        "equipe_deslocamento": _equipe_deslocamento(ordem),
        "sede": _build_sede(inst),
        "data_atual_extenso": _fmt_extenso(timezone.localdate()),
        "endereco": _build_endereco(inst),
        "telefone": _txt(inst.get("telefone_formatado") or inst.get("telefone")),
        "email": (_txt(inst.get("email")) or "").lower(),
    }
