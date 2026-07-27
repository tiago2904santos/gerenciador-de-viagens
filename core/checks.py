from __future__ import annotations

from django.apps import apps
from django.conf import settings
from django.core.checks import Error
from django.core.checks import Tags
from django.core.checks import register
from django.db import DatabaseError

_OPERATIONAL_MODELS = (
    "roteiros.Roteiro",
    "eventos.Evento",
    "documentos.DocumentoArtefato",
    "oficios.Oficio",
    "termos.TermoAutorizacao",
    "planos_trabalho.PlanoTrabalho",
    "ordens_servico.OrdemServico",
    "prestacoes_contas.PrestacaoContas",
)


@register(Tags.security, deploy=True)
def check_document_generation_sla_configuration(app_configs, **kwargs):
    engine = (
        getattr(settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "") or ""
    ).strip().lower()
    url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", "") or "").strip()
    if engine == "unoserver" and url:
        return []
    return [
        Error(
            "Produção deve usar o conversor LibreOffice residente (unoserver).",
            hint=(
                "Defina DOCUMENTOS_DEFAULT_PDF_ENGINE=unoserver e "
                "DOCUMENTOS_UNOSERVER_URL; valide depois com "
                "`documentos_unoserver_check --benchmark "
                "--representative-resources --max-ms 1000 --iterations 3`."
            ),
            id="core.E002",
        ),
    ]


@register(Tags.database, deploy=True)
def check_operational_records_have_area(app_configs, **kwargs):
    offenders = []
    try:
        for label in _OPERATIONAL_MODELS:
            model = apps.get_model(label)
            count = model._default_manager.filter(area__isnull=True).count()
            if count:
                offenders.append(f"{label}={count}")
    except DatabaseError:
        return []

    if not offenders:
        return []
    return [
        Error(
            "Há registros operacionais sem área explícita: " + ", ".join(offenders),
            hint=(
                "Faça backup e execute "
                "`python manage.py backfill_legacy_areas --area SIGLA --commit` "
                "antes do deploy."
            ),
            id="core.E001",
        ),
    ]
