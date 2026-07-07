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
PASTA_EVENTOS_CANCELADOS = "Eventos cancelados"
PASTA_TERMOS = "Termos"
PASTA_PRESTACAO = "Prestação de contas"
# Pasta global (no topo) que agrega TODAS as prestações de contas.
PASTA_PRESTACOES_GLOBAL = "Prestações de contas"

# Nome fixo do arquivo com o motivo do cancelamento, dentro da pasta do evento.
NOME_MOTIVO_CANCELAMENTO = "Motivo do cancelamento.txt"

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

_MESES_EXTENSO = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

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


def com_sufixo_cancelado(nome: str) -> str:
    """Insere ``" (cancelado)"`` antes da extensão. Idempotente: reorganizar de
    novo um documento que já tem o sufixo (ou reverter um cancelamento, o que
    faz o próximo reorganize recalcular sem o sufixo) nunca duplica."""
    if not nome:
        return nome
    if nome.endswith(" (cancelado)") or " (cancelado)." in nome:
        return nome
    if "." in nome:
        base, ext = nome.rsplit(".", 1)
        return f"{base} (cancelado).{ext}"
    return f"{nome} (cancelado)"


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


def capitalizar_cidade(cidade: str | None) -> str:
    """Nome de cidade em capitalização legível PT-BR (``MARINGÁ`` → ``Maringá``).

    Usa o formatador de documentos para tratar partículas ("dos", "de") e
    siglas, evitando o ``str.title()`` cego.
    """
    from documentos.services.formatters import format_document_display

    return format_document_display((cidade or "").strip())


def cidade_evento(evento=None, oficio=None) -> str:
    if evento is not None:
        cidade = (getattr(evento, "destino_cidade", "") or "").strip()
        if cidade:
            return capitalizar_cidade(cidade)
    if oficio is not None and getattr(oficio, "evento", None) is not None:
        cidade = (getattr(oficio.evento, "destino_cidade", "") or "").strip()
        if cidade:
            return capitalizar_cidade(cidade)
    return ""


def periodo_curto(di, df) -> str:
    """``22 a 23 jul 2026``; ``22 jul 2026`` se só uma data."""
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


def periodo_pasta(evento) -> str:
    return periodo_curto(getattr(evento, "data_inicio", None), getattr(evento, "data_fim", None))


def periodo_extenso(di, df) -> str:
    """``21 a 27 de julho de 2026``; ``21 de julho de 2026`` se só uma data."""
    if not di and not df:
        return ""
    if di and df and di != df:
        if di.month == df.month and di.year == df.year:
            return f"{di.day} a {df.day} de {_MESES_EXTENSO[di.month]} de {di.year}"
        if di.year == df.year:
            return (
                f"{di.day} de {_MESES_EXTENSO[di.month]} a "
                f"{df.day} de {_MESES_EXTENSO[df.month]} de {di.year}"
            )
        return (
            f"{di.day} de {_MESES_EXTENSO[di.month]} de {di.year} a "
            f"{df.day} de {_MESES_EXTENSO[df.month]} de {df.year}"
        )
    d = di or df
    return f"{d.day} de {_MESES_EXTENSO[d.month]} de {d.year}"


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


def pasta_oficio(oficio, servidores, cidade="") -> str:
    num = f"{oficio.numero:02d}" if getattr(oficio, "numero", None) else f"#{oficio.pk}"
    proto = protocolo_fmt(oficio)
    nomes = nomes_servidores(servidores)
    partes = [f"Ofício {num}"]
    if proto:
        partes.append(f"protocolo {proto}")
    if nomes:
        partes.append(nomes)
    return sanitize_drive_name(" ".join(partes) + _suf_cidade(cidade))


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


def destinos_os(ordem) -> str:
    if not getattr(ordem, "pk", None):
        return ""
    cidades = list(ordem.destinos.select_related("estado").order_by("nome"))
    if not cidades:
        return ""
    return ", ".join(
        f"{capitalizar_cidade(c.nome)}/{c.estado.sigla}" if c.estado_id else capitalizar_cidade(c.nome)
        for c in cidades
    )


def nome_os(ordem, formato="pdf") -> str:
    """Nome do arquivo da Ordem de Serviço — usa os dados da PRÓPRIA OS
    (número, destinos, período, servidores), nunca do ofício "âncora": uma OS
    pode cobrir vários ofícios com participantes/período/destino diferentes
    do dela (ex.: OS única pra 2 ofícios de cidades/datas distintas).

    Formato acordado com o usuário: ``Ordem de Serviço 007-2026 - Ivaiporã/PR
    - 21 a 27 de julho de 2026 - Nome1, Nome2 e Nome3``. Separador " - " (não
    "*"): asterisco é caractere inválido em nomes de arquivo no Windows e
    seria removido pelo sanitizador — quebraria a sincronização local do
    Drive Desktop.
    """
    nd = num_doc(ordem.numero, ordem.ano, width=3)
    destino = destinos_os(ordem)
    periodo = periodo_extenso(ordem.data_evento_inicio, ordem.data_evento_fim)
    nomes = nomes_servidores(list(ordem.servidores.all()) if ordem.pk else [])
    partes = [p for p in (f"Ordem de Serviço {nd}".strip(), destino, periodo, nomes) if p]
    return _arquivo(" - ".join(partes), formato)


def destinos_plano(plano) -> str:
    if not getattr(plano, "pk", None):
        return ""
    destinos = list(
        plano.destinos.filter(evento__isnull=True)
        .select_related("cidade", "estado")
        .order_by("ordem", "pk")
    )
    cidades = [d.cidade for d in destinos if d.cidade_id]
    if cidades:
        return ", ".join(f"{capitalizar_cidade(c.nome)}/{c.uf}" for c in cidades)
    if plano.destino_cidade_id:
        c = plano.destino_cidade
        return f"{capitalizar_cidade(c.nome)}/{c.uf}"
    return ""


def nome_plano(plano, formato="pdf") -> str:
    """Nome do arquivo do Plano de Trabalho — usa os dados do PRÓPRIO plano
    (número, destino, período do evento). Sem ofício/protocolo: um plano
    pertence ao evento, não a um ofício específico (um evento pode ter vários
    ofícios, e a associação com "o primeiro" seria arbitrária).

    Formato acordado com o usuário: ``Plano de Trabalho 07-2026 - Ivaiporã/PR
    - 21 a 27 de julho de 2026``.
    """
    nd = num_doc(getattr(plano, "numero", None), getattr(plano, "ano", None))
    destino = destinos_plano(plano)
    periodo = periodo_extenso(
        getattr(plano, "data_evento_inicio", None), getattr(plano, "data_evento_fim", None)
    )
    partes = [p for p in (f"Plano de Trabalho {nd}".strip(), destino, periodo) if p]
    return _arquivo(" - ".join(partes), formato)


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
