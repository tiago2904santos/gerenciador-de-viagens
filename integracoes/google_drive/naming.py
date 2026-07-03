"""Construção de nomes "bonitos" de pastas e arquivos para o Google Drive.

Os nomes são calculados a partir dos objetos do domínio (Ofício, Evento,
Servidor, Prestação…) e NÃO do nome do ``FileField`` armazenado localmente.
Decisões de formatação acordadas com o usuário:

- A barra ``/`` é trocada por hífen (ex.: ``Ofício 01/2026`` → ``Ofício 01-2026``).
- Mantemos acentos, espaços, parênteses e hífens (o Drive aceita).
- Nomes de servidores aparecem pelo primeiro nome em *Title Case*
  (``TIAGO SANTOS`` → ``Tiago``), pois ``Servidor.nome`` é salvo em maiúsculas.
"""

from __future__ import annotations

import re

from core.utils.masks import format_protocolo

# Nomes fixos de pastas da árvore.
PASTA_EVENTOS = "Eventos"
PASTA_TERMOS = "Termos"
PASTA_PRESTACAO = "Prestação de contas"
# Pasta global (no topo) que agrega TODAS as prestações de contas.
PASTA_PRESTACOES_GLOBAL = "Prestações de contas"

# Pastas globais por tipo de documento (no topo, fora de "Eventos"). Usadas como
# destino canônico quando o documento não tem evento e como agregadoras (atalhos)
# quando tem.
PASTA_TIPO_PLURAL = {
    "oficio": "Ofícios",
    "plano_trabalho": "Planos de trabalho",
    "ordem_servico": "Ordens de serviço",
    "termo_autorizacao": "Termos",
    "justificativa": "Justificativas",
}


def pasta_tipo(tipo: str) -> str:
    """Pasta global do tipo de documento (ex.: 'Planos de trabalho')."""
    return PASTA_TIPO_PLURAL.get(tipo or "", "Documentos")

_MESES_ABREV = [
    "",
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]

# Barra (vira hífen) e caracteres realmente problemáticos no Drive/sincronização.
_BARRA_RE = re.compile(r"[\\/]+")
_INVALIDOS_RE = re.compile(r'[<>:"|?*\x00-\x1f]')
_ESPACOS_RE = re.compile(r"\s+")


def sanitize_drive_name(value: str) -> str:
    """Sanea um nome para uso seguro como pasta/arquivo no Drive."""
    text = (value or "").strip()
    text = _BARRA_RE.sub("-", text)
    text = _INVALIDOS_RE.sub("", text)
    text = _ESPACOS_RE.sub(" ", text).strip()
    text = text.strip(" .")
    return text or "documento"


def extensao(filename: str | None) -> str:
    """Extensão (sem ponto, minúscula) extraída de um nome/caminho de arquivo."""
    nome = (filename or "").rsplit("/", 1)[-1]
    if "." in nome:
        return nome.rsplit(".", 1)[-1].lower()
    return ""


def _arquivo(base: str, ext: str | None) -> str:
    ext = (ext or "pdf").lower().lstrip(".")
    return f"{sanitize_drive_name(base)}.{ext}"


def _suf_cidade(cidade: str | None) -> str:
    cidade = (cidade or "").strip()
    return f" ({cidade})" if cidade else ""


def num_doc(numero, ano, *, width: int = 2) -> str:
    """``01-2026`` (ou vazio se não numerado). ``width`` controla os dígitos."""
    if numero and ano:
        return f"{int(numero):0{width}d}-{int(ano)}"
    return ""


def primeiro_nome(servidor) -> str:
    nome = (getattr(servidor, "nome", "") or "").strip()
    if not nome:
        return ""
    return nome.split()[0].capitalize()


def nomes_servidores(servidores) -> str:
    """``Tiago``; ``Tiago e Janine``; ``Tiago, Janine e Ana``."""
    nomes: list[str] = []
    for s in servidores or []:
        pn = primeiro_nome(s)
        if pn and pn not in nomes:
            nomes.append(pn)
    if not nomes:
        return ""
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def protocolo_fmt(oficio) -> str:
    return format_protocolo(getattr(oficio, "protocolo", "") or "")


def cidade_evento(evento=None, oficio=None) -> str:
    if evento is not None:
        cidade = (getattr(evento, "destino_cidade", "") or "").strip()
        if cidade:
            return cidade
    if oficio is not None and getattr(oficio, "evento", None) is not None:
        cidade = (getattr(oficio.evento, "destino_cidade", "") or "").strip()
        if cidade:
            return cidade
    return ""


def periodo_pasta(evento) -> str:
    di = getattr(evento, "data_inicio", None)
    df = getattr(evento, "data_fim", None)
    if not di and not df:
        return ""
    if di and df and di != df:
        if di.month == df.month and di.year == df.year:
            return f"{di.day} a {df.day} {_MESES_ABREV[di.month]} {di.year}"
        if di.year == df.year:
            return (
                f"{di.day} {_MESES_ABREV[di.month]} a "
                f"{df.day} {_MESES_ABREV[df.month]} {di.year}"
            )
        return (
            f"{di.day} {_MESES_ABREV[di.month]} {di.year} a "
            f"{df.day} {_MESES_ABREV[df.month]} {df.year}"
        )
    d = di or df
    return f"{d.day} {_MESES_ABREV[d.month]} {d.year}"


def tipo_evento_label(evento) -> str:
    # Usa ", " (nao "/") porque sanitize_drive_name troca barra por hifen, o
    # que confundiria o separador com o hifen que junta tipo/cidade/periodo.
    tipos = getattr(evento, "tipos", None)
    if tipos is not None and getattr(evento, "pk", None):
        nomes = list(tipos.values_list("nome", flat=True))
        if nomes:
            return ", ".join(nomes)
    return (getattr(evento, "titulo", "") or "").strip() or "Evento"


# ---------------------------------------------------------------------------
# Pastas
# ---------------------------------------------------------------------------

def pasta_evento(evento) -> str:
    partes = [tipo_evento_label(evento), cidade_evento(evento), periodo_pasta(evento)]
    base = " - ".join(p for p in partes if p)
    if not base:
        base = (getattr(evento, "titulo", "") or "").strip() or f"Evento {evento.pk}"
    return sanitize_drive_name(base)


def pasta_oficio(oficio, servidores) -> str:
    num = f"{oficio.numero:02d}" if getattr(oficio, "numero", None) else f"#{oficio.pk}"
    proto = protocolo_fmt(oficio)
    nomes = nomes_servidores(servidores)
    partes = [f"Ofício {num}"]
    if proto:
        partes.append(f"protocolo {proto}")
    if nomes:
        partes.append(nomes)
    return sanitize_drive_name(" ".join(partes))


def pasta_prestacao_servidor(servidor) -> str:
    nome = primeiro_nome(servidor)
    return sanitize_drive_name(f"Prestação {nome}" if nome else "Prestação")


# ---------------------------------------------------------------------------
# Arquivos
# ---------------------------------------------------------------------------

def nome_oficio(oficio, servidores, cidade, formato="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    proto = protocolo_fmt(oficio)
    nomes = nomes_servidores(servidores)
    partes = [f"Ofício {nd}".strip()]
    if proto:
        partes.append(f"protocolo {proto}")
    if nomes:
        partes.append(nomes)
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), formato)


def nome_termo(oficio, servidor, cidade, formato="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    proto = protocolo_fmt(oficio)
    nome = primeiro_nome(servidor)
    partes = [f"Termo de autorização {nd}".strip()]
    if proto:
        partes.append(f"protocolo {proto}")
    if nome:
        partes.append(nome)
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), formato)


def nome_os(oficio, servidores, cidade, formato="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano, width=3)
    proto = protocolo_fmt(oficio)
    nomes = nomes_servidores(servidores)
    partes = [f"Ordem de serviço {nd}".strip()]
    if proto:
        partes.append(f"protocolo {proto}")
    if nomes:
        partes.append(nomes)
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), formato)


def nome_plano(plano, cidade, *, oficio=None, formato="pdf") -> str:
    """Nome do plano usando a numeração do PRÓPRIO plano (não do ofício)."""
    nd = num_doc(getattr(plano, "numero", None), getattr(plano, "ano", None))
    proto = protocolo_fmt(oficio) if oficio is not None else ""
    base = "Plano de trabalho"
    partes = [f"{base} {nd}".strip()]
    if proto:
        partes.append(f"protocolo {proto}")
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), formato)


def nome_atalho_prestacao(oficio, servidor, cidade) -> str:
    """Nome do atalho de pasta na agregadora global de prestações."""
    nome = primeiro_nome(servidor)
    nd = num_doc(oficio.numero, oficio.ano) if oficio is not None else ""
    partes = [f"Prestação {nome}".strip() if nome else "Prestação"]
    if nd:
        partes.append(f"- Ofício {nd}")
    return sanitize_drive_name(" ".join(partes) + _suf_cidade(cidade))


def nome_justificativa(oficio, cidade, formato="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    proto = protocolo_fmt(oficio)
    partes = [f"Justificativa {nd}".strip()]
    if proto:
        partes.append(f"protocolo {proto}")
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), formato)


def nome_convite(cidade, ext="pdf", titulo="") -> str:
    titulo = (titulo or "").strip()
    base = f"Convite - {titulo}" if titulo else "Convite"
    return _arquivo(base + _suf_cidade(cidade), ext)


def nome_anexo_solicitacao(oficio, servidor, numero_solicitacao, cidade, ext="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    proto = protocolo_fmt(oficio)
    nome = primeiro_nome(servidor)
    partes = ["Anexo solicitação"]
    if numero_solicitacao:
        partes.append(str(numero_solicitacao).strip())
    partes.append(f"Ofício {nd}".strip())
    if proto:
        partes.append(f"protocolo {proto}")
    if nome:
        partes.append(nome)
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), ext)


def nome_relatorio_tecnico(oficio, servidor, cidade, ext="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    nome = primeiro_nome(servidor)
    partes = ["Relatório técnico"]
    if nome:
        partes.append(nome)
    partes.append(f"Ofício {nd}".strip())
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), ext)


def nome_diario_bordo(oficio, servidor, cidade, ext="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    nome = primeiro_nome(servidor)
    partes = ["Diário de bordo"]
    if nome:
        partes.append(nome)
    partes.append(f"Ofício {nd}".strip())
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), ext)


def nome_despacho(oficio, servidor, cidade, ext="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    nome = primeiro_nome(servidor)
    partes = [f"Despacho Ofício {nd}".strip()]
    if nome:
        partes.append(nome)
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), ext)


def nome_comprovante(oficio, servidor, cidade, ext="pdf") -> str:
    nd = num_doc(oficio.numero, oficio.ano)
    nome = primeiro_nome(servidor)
    partes = ["Comprovante de saque"]
    if nome:
        partes.append(nome)
    partes.append(f"Ofício {nd}".strip())
    return _arquivo(" ".join(partes) + _suf_cidade(cidade), ext)
