from __future__ import annotations
from django.http import QueryDict
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from .models import PlanoTrabalho
from .selectors import get_plano_by_id
from .presenters import apresentar_plano_wizard_header
from .presenters import apresentar_plano_wizard_page_steps
from .presenters import apresentar_plano_wizard_steps
from .presenters import apresentar_plano_wizard_summary
from .services import avaliar_etapa_atividades
from .services import avaliar_etapa_efetivo_diarias
from .services import avaliar_etapa_identificacao


def _get_plano(pk) -> PlanoTrabalho:
    return get_plano_by_id(pk)


def _evento_etapa_url(evento_id):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": 4})
    return ""


def _plano_lista_url(plano=None):
    return _evento_etapa_url(getattr(plano, "evento_id", None)) or reverse("planos_trabalho:index")


def _plano_lista_label(plano=None):
    return "Dados do evento" if getattr(plano, "evento_id", None) else "Voltar a lista"


def _redirect_plano_lista(plano):
    if getattr(plano, "evento_id", None):
        return redirect("eventos:guiado_etapa", pk=plano.evento_id, etapa=4)
    return redirect("planos_trabalho:index")


def _wizard_steps_ctx(*, plano=None, etapa_atual="identificacao"):
    steps = apresentar_plano_wizard_steps(
        plano=plano,
        etapa_atual=etapa_atual,
        identificacao_status=avaliar_etapa_identificacao(plano) if plano else None,
        efetivo_diarias_status=avaliar_etapa_efetivo_diarias(plano) if plano else None,
        atividades_status=avaliar_etapa_atividades(plano) if plano else None,
        documentos_status="complete" if plano and plano.status == PlanoTrabalho.STATUS_GERADO else "not_started",
    )
    return {
        "wizard_steps": steps,
        "wizard_page_steps": apresentar_plano_wizard_page_steps(steps),
    }


def _wizard_shell_ctx(*, plano=None, etapa_atual):
    return {
        "wizard_header": apresentar_plano_wizard_header(etapa_atual, plano=plano),
        "wizard_summary": apresentar_plano_wizard_summary(plano) if plano else None,
        "plano": plano,
        "wizard_back_url": _plano_lista_url(plano),
        "wizard_back_label": _plano_lista_label(plano),
        **_wizard_steps_ctx(plano=plano, etapa_atual=etapa_atual),
    }


def _plano_autosave_version(plano: PlanoTrabalho) -> int:
    plano.refresh_from_db()
    return int(timezone.localtime(plano.updated_at).timestamp())


def _querydict_from_pairs(pairs):
    data = QueryDict(mutable=True)
    for name, value in pairs.items():
        if isinstance(value, (list, tuple, set)):
            data.setlist(name, [str(item) for item in value if item not in (None, "")])
        elif value is not None:
            data[name] = str(value)
    return data


def _merge_payload_fields(data, clean_fields):
    for name, value in clean_fields.items():
        if isinstance(value, list):
            data.setlist(name, [str(item) for item in value if item not in (None, "")])
        elif value is None:
            data[name] = ""
        else:
            data[name] = str(value)
    return data


def _autosave_form_errors(*forms):
    errors = {}
    for form in forms:
        for field, messages_list in form.errors.items():
            errors[field] = [str(item) for item in messages_list]
    return errors
