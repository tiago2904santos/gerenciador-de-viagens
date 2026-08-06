from __future__ import annotations

from django.apps import apps
from django.conf import settings
from django.core.checks import Error
from django.core.checks import Tags
from django.core.checks import Warning as CheckWarning
from django.core.checks import register
from django.db import DatabaseError

#: `core.E001` — bloqueia o deploy. São os oito modelos operacionais: registro sem
#: área aqui é dado de trabalho órfão, e o `backfill_legacy_areas` sabe tratá-los.
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

#: `NOVO-31`: a tabela de vínculo não é dado de tenant — `area` nela já é NOT NULL.
_FORA_DA_VARREDURA = {"usuarios.VinculoUsuarioArea"}

#: `AuditEvent.area` é `SET_NULL` **por projeto**: evento antigo perde a área quando
#: ela é apagada, e a trilha precisa sobreviver a isso. Linha sem área aqui é
#: histórico, não pendência — e por isso ela nunca entra no `DB-02`.
_AREA_NULA_LEGITIMA = {"core.AuditEvent"}


def _modelos_com_area():
    """Todo modelo com coluna `area` concreta, por introspecção.

    `NOVO-31`: a lista era fixa com oito nomes e ficou para trás — os seis de
    `cadastros`, os cinco de `planos_trabalho` e os demais nunca foram olhados,
    justamente os que os comandos de seed criam sem área. Derivar do registro de
    apps é o que impede a lista de envelhecer de novo.
    """
    for modelo in apps.get_models():
        label = modelo._meta.label
        if label in _FORA_DA_VARREDURA or label in _AREA_NULA_LEGITIMA:
            continue
        if any(campo.name == "area" for campo in modelo._meta.concrete_fields):
            yield label, modelo


def _contar_sem_area(modelos):
    """`[(label, quantidade), ...]` para os que têm linha sem área.

    Usa `_default_manager`, que depois do `BE-09` é o manager **irrestrito**
    (`Meta.default_manager_name = "all_objects"`). Se um dia alguém apontar o
    `_default_manager` para o manager que recorta, este check passa a reportar
    zero em silêncio — é uma das razões de aquela decisão estar travada por teste.
    """
    achados = []
    for label, modelo in modelos:
        quantidade = modelo._default_manager.filter(area__isnull=True).count()
        if quantidade:
            achados.append((label, quantidade))
    return achados


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
    """Duas severidades, de propósito.

    `core.E001` **bloqueia** o deploy e cobre os oito modelos operacionais, como
    sempre cobriu. `core.W001` apenas **relata** os demais modelos com `area`.

    A separação existe porque o `NOVO-31` era cegueira, não leniência: promover os
    outros vinte a `Error` de uma vez tornaria vermelho todo deploy até alguém
    rodar o backfill — decisão que não cabe a um check tomar sozinho. O aviso põe
    o número à vista, que é o que o `DB-02` precisa para ser desenhado; cada modelo
    sobe para `Error` quando entrar no `NOT NULL`.
    """
    try:
        operacionais = [
            (label, modelo)
            for label, modelo in _modelos_com_area()
            if label in _OPERATIONAL_MODELS
        ]
        demais = [
            (label, modelo)
            for label, modelo in _modelos_com_area()
            if label not in _OPERATIONAL_MODELS
        ]
        com_pendencia = _contar_sem_area(operacionais)
        apenas_relatados = _contar_sem_area(demais)
    except DatabaseError:
        return []

    def descrever(achados):
        return ", ".join(f"{label}={quantidade}" for label, quantidade in achados)

    problemas = []
    if com_pendencia:
        problemas.append(
            Error(
                "Há registros operacionais sem área explícita: " + descrever(com_pendencia),
                hint=(
                    "Faça backup e execute "
                    "`python manage.py backfill_legacy_areas --area SIGLA --commit` "
                    "antes do deploy."
                ),
                id="core.E001",
            ),
        )
    if apenas_relatados:
        problemas.append(
            CheckWarning(
                "Modelos com `area` anulável e linhas sem área: " + descrever(apenas_relatados),
                hint=(
                    "Não bloqueia o deploy. É a medição que o `DB-02` precisa antes de "
                    "tornar `area` obrigatória — cada modelo vira `core.E001` quando "
                    "entrar no `NOT NULL`."
                ),
                id="core.W001",
            ),
        )
    return problemas
