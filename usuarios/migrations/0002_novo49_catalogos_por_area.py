"""NOVO-49 — saneia catálogos e elimina definitivamente o balde global."""

from django.db import migrations

from core.catalogos_iniciais import (
    ATIVIDADES_PLANO,
    HORARIOS,
    PROGRAMAS,
    TIPOS_EVENTO,
)


def semear_areas_e_remover_globais(apps, schema_editor):
    AreaTrabalho = apps.get_model("usuarios", "AreaTrabalho")
    TipoEvento = apps.get_model("eventos", "TipoEvento")
    Atividade = apps.get_model("planos_trabalho", "AtividadePlanoTrabalho")
    Programa = apps.get_model("planos_trabalho", "ProgramaSolicitante")
    Horario = apps.get_model("planos_trabalho", "HorarioAtendimento")

    for area in AreaTrabalho._base_manager.order_by("pk"):
        for indice, (_, nome) in enumerate(TIPOS_EVENTO):
            TipoEvento._base_manager.get_or_create(
                area=area,
                nome=nome,
                defaults={"ordem": (indice + 1) * 10, "ativo": True},
            )
        for nome, ordem in PROGRAMAS:
            Programa._base_manager.get_or_create(
                area=area,
                nome=nome,
                defaults={"ordem": ordem, "ativo": True},
            )
        for faixa, ordem in HORARIOS:
            Horario._base_manager.get_or_create(
                area=area,
                faixa=faixa,
                defaults={"ordem": ordem, "ativo": True},
            )
        for item in ATIVIDADES_PLANO:
            defaults = {**item, "ativo": True}
            codigo = defaults.pop("codigo")
            Atividade._base_manager.get_or_create(
                area=area,
                codigo=codigo,
                defaults=defaults,
            )

    for modelo in (TipoEvento, Atividade, Programa, Horario):
        modelo._base_manager.filter(area__isnull=True).delete()


def restaurar_catalogos_globais(apps, schema_editor):
    """Recria apenas o seed global; dados próprios das áreas são preservados."""
    TipoEvento = apps.get_model("eventos", "TipoEvento")
    Atividade = apps.get_model("planos_trabalho", "AtividadePlanoTrabalho")
    Programa = apps.get_model("planos_trabalho", "ProgramaSolicitante")
    Horario = apps.get_model("planos_trabalho", "HorarioAtendimento")

    for indice, (_, nome) in enumerate(TIPOS_EVENTO):
        TipoEvento._base_manager.get_or_create(
            area=None,
            nome=nome,
            defaults={"ordem": (indice + 1) * 10, "ativo": True},
        )
    for nome, ordem in PROGRAMAS:
        Programa._base_manager.get_or_create(
            area=None,
            nome=nome,
            defaults={"ordem": ordem, "ativo": True},
        )
    for faixa, ordem in HORARIOS:
        Horario._base_manager.get_or_create(
            area=None,
            faixa=faixa,
            defaults={"ordem": ordem, "ativo": True},
        )
    for item in ATIVIDADES_PLANO:
        defaults = {**item, "ativo": True}
        codigo = defaults.pop("codigo")
        Atividade._base_manager.get_or_create(
            area=None,
            codigo=codigo,
            defaults=defaults,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_initial"),
        ("eventos", "0016_db02_catalogos_por_area"),
        ("planos_trabalho", "0024_db02_catalogos_por_area"),
    ]

    operations = [
        migrations.RunPython(
            semear_areas_e_remover_globais,
            restaurar_catalogos_globais,
        ),
    ]
