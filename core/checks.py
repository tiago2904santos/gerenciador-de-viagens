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
    """`core.W002` — era `core.E002`, rebaixado de propósito (`NOVO-12`).

    Produção roda `DOCUMENTOS_DEFAULT_PDF_ENGINE=auto` e não tem unoserver no ar.
    Enquanto o check era `Error`, ligar `check --deploy --fail-level ERROR` no
    `deploy.yml` travaria todo deploy — e um check que ninguém pode satisfazer não
    é catraca, é ruído. O SLA real de geração continua medido pelo CI ("Enforce
    real document generation SLA" em `tests.yml`, com unoserver de verdade).
    Quando produção subir o unoserver e ligar as duas variáveis, este aviso some;
    repromovê-lo a `Error` aí volta a ser catraca honesta.
    """
    engine = (
        getattr(settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "") or ""
    ).strip().lower()
    url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", "") or "").strip()
    if engine == "unoserver" and url:
        return []
    return [
        CheckWarning(
            "Produção deve usar o conversor LibreOffice residente (unoserver).",
            hint=(
                "Defina DOCUMENTOS_DEFAULT_PDF_ENGINE=unoserver e "
                "DOCUMENTOS_UNOSERVER_URL; valide depois com "
                "`documentos_unoserver_check --benchmark "
                "--representative-resources --max-ms 1000 --iterations 3`."
            ),
            id="core.W002",
        ),
    ]


#: Espelho dos critérios de `security.W009` do Django — que é **Warning**, e o
#: gate do deploy roda com `--fail-level ERROR`. Sem esta promoção, a chave de 9
#: caracteres que motivou o `NOVO-12` passaria pelo gate que existe por causa dela.
_SECRET_KEY_MIN_LENGTH = 50
_SECRET_KEY_MIN_UNIQUE_CHARS = 5
_SECRET_KEY_INSECURE_PREFIX = "django-insecure-"


@register(Tags.security, deploy=True)
def check_secret_key_strength(app_configs, **kwargs):
    """`core.E003` — `SECRET_KEY` fraca bloqueia o deploy (`NOVO-12`).

    É ela que assina cookie de sessão e token de recuperação de senha: com uma
    chave curta dá para forjar sessão de qualquer usuário, superusuário incluído.
    O defeito medido em 06/08/2026 (9 caracteres, no VPS) era exatamente o caso
    que nenhum grep por placeholder pega — só uma régua olhando a configuração
    carregada.
    """
    chave = str(getattr(settings, "SECRET_KEY", "") or "")
    fraca = (
        len(chave) < _SECRET_KEY_MIN_LENGTH
        or len(set(chave)) < _SECRET_KEY_MIN_UNIQUE_CHARS
        or chave.startswith(_SECRET_KEY_INSECURE_PREFIX)
    )
    if not fraca:
        return []
    return [
        Error(
            "SECRET_KEY fraca para produção: são necessários ao menos "
            f"{_SECRET_KEY_MIN_LENGTH} caracteres, "
            f"{_SECRET_KEY_MIN_UNIQUE_CHARS} distintos, sem o prefixo "
            f"'{_SECRET_KEY_INSECURE_PREFIX}'.",
            hint=(
                "Gere com `python -c \"import secrets; "
                "print(secrets.token_urlsafe(64))\"` e troque no .env; sessões "
                "ativas serão invalidadas."
            ),
            id="core.E003",
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
