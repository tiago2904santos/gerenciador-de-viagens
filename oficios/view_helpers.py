import re
from django.contrib import messages
from django.http import QueryDict
from django.shortcuts import redirect
from django.utils import timezone
from core.tenancy import filter_queryset_by_area
from cadastros.models import Combustivel
from .models import Oficio
from .presenters import apresentar_oficio_wizard_header
from .presenters import apresentar_oficio_wizard_page_steps
from .presenters import apresentar_oficio_wizard_steps
from .selectors import listar_servidores_para_oficio
from .selectors import listar_viaturas_para_oficio
from .services import oficio_esta_completo_para_finalizar
from core.wizard import normalizar_acao_do_wizard



def _redirect_lista_oficio(request, oficio, message):
    messages.success(request, message)
    if getattr(oficio, "evento_id", None):
        return redirect("eventos:guiado_etapa", pk=oficio.evento_id, etapa=3)
    return redirect("oficios:index")


# BE-01: a implementação mora em core/wizard.py, compartilhada com planos de
# trabalho. O alias sobrevive porque `oficios.views._wizard_normalizar_acao` é
# contrato de um teste existente.
_wizard_normalizar_acao = normalizar_acao_do_wizard


def _wizard_persist_action_para_dados_viajantes(nav_action: str) -> str:
    if nav_action == "wizard_next":
        return "save_continue"
    return "save_draft"


def _wizard_footer_ctx(oficio):
    return {"oficio_completo": oficio_esta_completo_para_finalizar(oficio)}


def _wizard_steps_ctx(*, oficio=None, etapa_atual="dados_viajantes", **kwargs):
    steps = apresentar_oficio_wizard_steps(
        oficio=oficio,
        etapa_atual=etapa_atual,
        **kwargs,
    )
    return {
        "wizard_steps": steps,
        "wizard_page_steps": apresentar_oficio_wizard_page_steps(steps),
    }


def _wizard_shell_ctx(*, oficio=None, etapa_atual, **step_kwargs):
    return {
        "wizard_header": apresentar_oficio_wizard_header(etapa_atual, oficio=oficio),
        **_wizard_steps_ctx(oficio=oficio, etapa_atual=etapa_atual, **step_kwargs),
    }


def _wizard_roteiro_step_status(oficio):
    if not getattr(oficio, "roteiro_id", None):
        return "incomplete"
    roteiro = oficio.roteiro
    return (
        "complete"
        if (roteiro.origem_cidade_id or roteiro.origem_estado_id)
        else "incomplete"
    )


def _motorista_oficio_numero_display(ref):
    ref = (ref or "").strip()
    if not ref:
        return ""
    head = ref.split("/", 1)[0]
    return re.sub(r"\D", "", head)[:3]


def _prepare_dados_viajantes_form(form):
    servidores_qs = listar_servidores_para_oficio()
    form.fields["servidores"].queryset = servidores_qs
    form.fields["servidores_termo_autorizacao"].queryset = servidores_qs
    form.fields["viatura"].queryset = listar_viaturas_para_oficio()


def _prepare_transporte_form(form):
    form.fields["viatura"].queryset = listar_viaturas_para_oficio()
    form.fields["motorista"].queryset = listar_servidores_para_oficio()
    form.fields["transporte_combustivel_manual"].queryset = filter_queryset_by_area(Combustivel.objects).order_by("nome")


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


def _oficio_dados_viajantes_autosave_data(oficio):
    return _querydict_from_pairs(
        {
            "numero": oficio.numero or "",
            "protocolo": oficio.protocolo or "",
            "modelo_motivo": "",
            "motivo": oficio.motivo or "",
            "custeio": oficio.custeio or Oficio.CUSTEIO_UNIDADE_DPC,
            "custeio_observacao": oficio.custeio_observacao or "",
            "viatura": oficio.viatura_id or "",
            "servidores": list(oficio.servidores.values_list("pk", flat=True)),
            "servidores_termo_autorizacao_present": "1",
            "servidores_termo_autorizacao": list(
                oficio.servidores_termo_autorizacao.values_list("pk", flat=True),
            ),
            "transporte_embed": "1",
            "porte_transporte_armas": "sim" if oficio.porte_transporte_armas else "nao",
            "transporte_placa_manual": oficio.transporte_placa_manual or "",
            "transporte_modelo_manual": oficio.transporte_modelo_manual or "",
            "transporte_combustivel_manual": oficio.transporte_combustivel_manual_id or "",
            "transporte_tipo_manual": oficio.transporte_tipo_manual or "",
            "motorista_modo": oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR,
            "motorista": oficio.motorista_id or "",
            "motorista_manual_nome": oficio.motorista_manual_nome or "",
            "motorista_oficio_referencia": oficio.motorista_oficio_referencia or "",
            "motorista_protocolo_ref": oficio.motorista_protocolo_ref or "",
        }
    )


def _oficio_transporte_autosave_data(oficio):
    return _querydict_from_pairs(
        {
            "viatura": oficio.viatura_id or "",
            "porte_transporte_armas": "sim" if oficio.porte_transporte_armas else "nao",
            "transporte_placa_manual": oficio.transporte_placa_manual or "",
            "transporte_modelo_manual": oficio.transporte_modelo_manual or "",
            "transporte_combustivel_manual": oficio.transporte_combustivel_manual_id or "",
            "transporte_tipo_manual": oficio.transporte_tipo_manual or "",
            "motorista_modo": oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR,
            "motorista": oficio.motorista_id or "",
            "motorista_manual_nome": oficio.motorista_manual_nome or "",
            "motorista_oficio_referencia": oficio.motorista_oficio_referencia or "",
            "motorista_protocolo_ref": oficio.motorista_protocolo_ref or "",
        }
    )


def _oficio_autosave_version(oficio):
    oficio.refresh_from_db()
    return int(timezone.localtime(oficio.updated_at).timestamp())


def _justificativa_autosave_data(inst):
    return _querydict_from_pairs(
        {
            "modelo": inst.modelo_id or "",
            "texto": inst.texto or "",
        }
    )


def _autosave_form_errors(*forms):
    errors = {}
    for form in forms:
        for field, messages_list in form.errors.items():
            errors[field] = [str(item) for item in messages_list]
    return errors
