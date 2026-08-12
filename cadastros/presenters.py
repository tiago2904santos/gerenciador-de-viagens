import json

from core.utils.masks import format_cpf as _format_cpf_masked
from core.utils.masks import format_placa as _format_placa_masked
from core.utils.masks import format_rg_display as _format_rg_masked
from core.utils.masks import format_telefone as _format_telefone_masked
from core.presenters.actions import build_delete_action
from core.presenters.actions import build_edit_action
from core.presenters.badges import build_badge
from core.presenters.meta import build_meta


def _actions(edit_url=None, delete_url=None):
    actions = [build_edit_action(edit_url), build_delete_action(delete_url)]
    return [action for action in actions if action]


def _format_cpf(cpf):
    t = _format_cpf_masked(cpf or "")
    return t if t else "-"


def _format_rg(rg, *, sem_rg=False):
    t = _format_rg_masked(rg or "", sem_rg=sem_rg)
    return t if t else "-"


def _format_placa(placa):
    t = _format_placa_masked(placa or "")
    return t if t else "-"


def _format_telefone(tel):
    t = _format_telefone_masked(tel or "")
    return t if t else "—"


def apresentar_unidade_card(unidade, edit_url="#", delete_url="#"):
    return {
        "title": unidade.nome,
        "subtitle": unidade.sigla or "Sem sigla",
        "meta": [
            build_meta("Sigla", unidade.sigla or "-"),
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_cidade_card(cidade, edit_url="#", delete_url="#"):
    return {
        "title": cidade.nome,
        "subtitle": cidade.uf,
        "meta": [
            build_meta("UF", cidade.uf),
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_cargo_card(cargo, edit_url="#", delete_url="#"):
    return {
        "title": cargo.nome,
        "subtitle": "Cadastro de cargo",
        "meta": [],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_combustivel_card(combustivel, edit_url="#", delete_url="#"):
    return {
        "title": combustivel.nome,
        "subtitle": "Cadastro de combustível",
        "meta": [],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_servidor_card(servidor, edit_url="#", delete_url="#"):
    unidade_label = "-"
    if servidor.unidade:
        unidade_label = servidor.unidade.sigla or servidor.unidade.nome
    return {
        "title": servidor.nome,
        "subtitle": servidor.cargo.nome if servidor.cargo else "Cargo não informado",
        "meta": [
            build_meta("CPF", _format_cpf(servidor.cpf)),
            build_meta("RG", _format_rg(servidor.rg, sem_rg=servidor.sem_rg)),
            build_meta("Telefone", _format_telefone(servidor.telefone)),
            build_meta("Unidade", unidade_label),
        ],
        "actions": _actions(edit_url, delete_url),
    }


def _motoristas_label(viatura):
    lista = list(viatura.motoristas.all())
    if not lista:
        return "Nenhum motorista vinculado"
    return ", ".join(s.nome for s in lista)


def _viatura_unidade_label(viatura):
    if viatura.unidade_id:
        return viatura.unidade.sigla or viatura.unidade.nome
    return "—"


def apresentar_viatura_card(viatura, edit_url="#", delete_url="#"):
    placa_fmt = _format_placa(viatura.placa)
    modelo = (viatura.modelo or "").strip()
    title = f"{modelo} — {placa_fmt}" if modelo else placa_fmt
    unidade_label = _viatura_unidade_label(viatura)
    subt = unidade_label if unidade_label != "—" else (viatura.get_tipo_display() if viatura.tipo else "Tipo não informado")
    return {
        "title": title,
        "subtitle": subt,
        "meta": [
            build_meta("Unidade", unidade_label),
            build_meta("Combustível", viatura.combustivel.nome if viatura.combustivel else "-"),
            build_meta("Tipo", viatura.get_tipo_display() if viatura.tipo else "-"),
            build_meta("Motoristas", _motoristas_label(viatura)),
        ],
        "actions": _actions(edit_url, delete_url),
    }


def _initials(text, fallback="??"):
    parts = [part for part in str(text or "").strip().split() if part]
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _join_subtitle(*parts):
    clean = [
        str(part).strip()
        for part in parts
        if part is not None and str(part).strip() and str(part).strip() not in {"—", "-"}
    ]
    return " · ".join(clean)


def apresentar_linha_lista_simples_cargo(cargo, edit_url="#", delete_url="#", set_default_url=None, delete_modal=False):
    row = {
        "avatar": _initials(cargo.nome, "CG"),
        "title": cargo.nome,
        "badges": [],
        "subtitle": "",
        "facts": [],
        "meta": [],
        "edit_url": edit_url,
        "edit_fields_json": json.dumps({"nome": cargo.nome}, ensure_ascii=False),
        "delete_url": delete_url,
        "delete_modal": delete_modal,
        "set_default_url": set_default_url,
    }
    if getattr(cargo, "is_padrao", False):
        row["badges"].append(build_badge("Padrão", "default"))
        row["set_default_url"] = None
    return row


def apresentar_linha_lista_simples_combustivel(combustivel, edit_url="#", delete_url="#", set_default_url=None, delete_modal=False):
    row = {
        "avatar": _initials(combustivel.nome, "CB"),
        "title": combustivel.nome,
        "badges": [],
        "subtitle": "",
        "facts": [],
        "meta": [],
        "edit_url": edit_url,
        "edit_fields_json": json.dumps({"nome": combustivel.nome}, ensure_ascii=False),
        "delete_url": delete_url,
        "delete_modal": delete_modal,
        "set_default_url": set_default_url,
    }
    if getattr(combustivel, "is_padrao", False):
        row["badges"].append(build_badge("Padrão", "default"))
        row["set_default_url"] = None
    return row


def apresentar_linha_lista_simples_unidade(unidade, edit_url="#", delete_url="#", delete_modal=False):
    sigla = unidade.sigla or "—"
    return {
        "avatar": _initials(unidade.sigla or unidade.nome, "UN"),
        "title": unidade.nome,
        "badges": [],
        "subtitle": sigla if sigla != "—" else "",
        "facts": [],
        "meta": [
            build_meta("Sigla", sigla),
        ],
        "edit_url": edit_url,
        "edit_fields_json": json.dumps({"nome": unidade.nome, "sigla": unidade.sigla or ""}, ensure_ascii=False),
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }


def apresentar_linha_lista_simples_cidade(cidade):
    facts = [
        build_meta("IBGE", cidade.codigo_ibge or "—"),
    ]
    return {
        "avatar": _initials(cidade.nome, "CI"),
        "title": cidade.nome,
        "badges": [],
        "subtitle": cidade.uf or "",
        "facts": facts,
        "meta": [
            build_meta("UF", cidade.uf),
            *facts,
        ],
    }


def apresentar_linha_lista_simples_estado(estado, edit_url="#", delete_url="#", delete_modal=False):
    cod = str(estado.codigo_ibge) if estado.codigo_ibge is not None else "—"
    facts = [
        build_meta("IBGE", cod),
    ]
    return {
        "avatar": (estado.sigla or "UF")[:2].upper(),
        "title": estado.nome,
        "badges": [],
        "subtitle": estado.sigla or "",
        "facts": facts,
        "meta": [
            build_meta("Sigla", estado.sigla),
            *facts,
        ],
        "edit_url": edit_url,
        "edit_fields_json": json.dumps(
            {
                "nome": estado.nome,
                "sigla": estado.sigla,
                "codigo_ibge": estado.codigo_ibge if estado.codigo_ibge is not None else "",
            },
            ensure_ascii=False,
        ),
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }


def apresentar_linha_lista_simples_servidor(servidor, edit_url="#", delete_url="#", delete_modal=False):
    unidade_label = "—"
    if servidor.unidade:
        unidade_label = servidor.unidade.sigla or servidor.unidade.nome
    cargo_label = servidor.cargo.nome if servidor.cargo else "—"
    badges = []
    if servidor.status == servidor.STATUS_RASCUNHO:
        badges.append(build_badge("Rascunho", "draft"))
    facts = [
        build_meta("CPF", _format_cpf(servidor.cpf)),
        build_meta("RG", _format_rg(servidor.rg, sem_rg=servidor.sem_rg)),
        build_meta("Telefone", _format_telefone(servidor.telefone)),
    ]
    return {
        "avatar": _initials(servidor.nome, "SV"),
        "title": servidor.nome,
        "badges": badges,
        "subtitle": _join_subtitle(cargo_label, unidade_label),
        "facts": facts,
        "meta": [
            build_meta("Cargo", cargo_label),
            *facts,
            build_meta("Unidade", unidade_label),
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }


def apresentar_linha_lista_simples_viatura(viatura, edit_url="#", delete_url="#", delete_modal=False):
    placa_fmt = _format_placa(viatura.placa)
    modelo = (viatura.modelo or "").strip()
    title = f"{modelo} — {placa_fmt}" if modelo else placa_fmt
    badges = []
    if viatura.status == viatura.STATUS_RASCUNHO:
        badges.append(build_badge("Rascunho", "draft"))
    unidade_label = _viatura_unidade_label(viatura)
    combustivel = viatura.combustivel.nome if viatura.combustivel else "—"
    tipo = viatura.get_tipo_display() if viatura.tipo else "—"
    facts = [
        build_meta("Placa", placa_fmt),
        build_meta("Tipo", tipo),
        build_meta("Motoristas", _motoristas_label(viatura)),
    ]
    return {
        "avatar": _initials(modelo or placa_fmt, "VT"),
        "title": title,
        "badges": badges,
        "subtitle": _join_subtitle(unidade_label, combustivel),
        "facts": facts,
        "meta": [
            build_meta("Placa", placa_fmt),
            build_meta("Unidade", unidade_label),
            build_meta("Combustível", combustivel),
            build_meta("Tipo", tipo),
            build_meta("Motoristas", _motoristas_label(viatura)),
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }
