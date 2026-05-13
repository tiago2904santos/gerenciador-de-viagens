"""Substitui todos os modelos de motivo e de justificativa por 5 registros de teste cada."""

from django.core.management.base import BaseCommand
from django.db import transaction

from justificativas.models import ModeloJustificativa
from oficios.models import ModeloMotivoOficio

_MOTIVOS = [
    (
        "AUDIÊNCIA JUDICIAL",
        (
            "Participação em audiência ou sessão judicial designada pelo Tribunal, "
            "com comparecimento obrigatório em data e horário já fixados na pauta."
        ),
        10,
        True,
    ),
    (
        "CAPACITAÇÃO / CURSO",
        (
            "Participação em capacitação, curso ou treinamento institucional ou convocado por órgão "
            "superior, conforme convocação formal anexa ao processo."
        ),
        20,
        False,
    ),
    (
        "MISSÃO / REPRESENTAÇÃO INSTITUCIONAL",
        (
            "Representação da unidade em evento, cerimônia ou missão externa de caráter institucional, "
            "mediante designação formal da chefia."
        ),
        30,
        False,
    ),
    (
        "PERÍCIA OU TRABALHO DE CAMPO",
        (
            "Deslocamento para realização de perícia, inspeção, coleta de informações ou apoio técnico "
            "em local diverso da sede, conforme demanda operacional registrada."
        ),
        40,
        False,
    ),
    (
        "REUNIÃO INTERINSTITUCIONAL",
        (
            "Participação em reunião agendada com outros órgãos ou entidades parceiras para articulação "
            "de políticas, planejamento conjunto ou acompanhamento de protocolos."
        ),
        50,
        False,
    ),
]

_JUSTIFICATIVAS = [
    (
        "ANTECEDÊNCIA REGULAMENTAR",
        (
            "O cadastro do ofício ocorreu com antecedência igual ou inferior ao prazo mínimo previsto "
            "na norma interna, sendo necessário registrar formalmente os fundamentos da viagem."
        ),
        10,
        True,
    ),
    (
        "URGÊNCIA OPERACIONAL",
        (
            "Demanda classificada como prioritária pela gestão, exigindo deslocamento em curto prazo "
            "para garantir continuidade do serviço ou cumprimento de prazo externo crítico."
        ),
        20,
        False,
    ),
    (
        "REMARCAÇÃO DE DATAS",
        (
            "Alteração de datas de agenda já planejada (audiência, evento ou reunião), mantendo-se "
            "o mesmo objeto da viagem e exigindo novo registro para fins de controle."
        ),
        30,
        False,
    ),
    (
        "EVENTO DE CALENDÁRIO FIXO",
        (
            "Participação em evento com data imutável definida por órgão externo ou calendário oficial, "
            "não passível de postergação sem prejuízo institucional."
        ),
        40,
        False,
    ),
    (
        "COMPOSIÇÃO MÍNIMA DE EQUIPE",
        (
            "Necessidade de presença física de integrante da equipe para atividade que não pode ser "
            "realizada remotamente, conforme natureza do encargo."
        ),
        50,
        False,
    ),
]


class Command(BaseCommand):
    help = "Apaga todos os modelos de motivo e de justificativa e cria 5 de teste de cada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Não pedir confirmação (útil para scripts).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        n_m = ModeloMotivoOficio.objects.count()
        n_j = ModeloJustificativa.objects.count()
        self.stdout.write(
            self.style.WARNING(
                f"Isso remove {n_m} modelo(s) de motivo e {n_j} modelo(s) de justificativa existentes."
            )
        )
        if not options["no_input"]:
            confirm = input("Continuar? [s/N]: ").strip().lower()
            if confirm not in ("s", "sim", "y", "yes"):
                self.stdout.write(self.style.ERROR("Cancelado."))
                return

        ModeloMotivoOficio.objects.all().delete()
        ModeloJustificativa.objects.all().delete()

        for nome, texto, ordem, is_padrao in _MOTIVOS:
            ModeloMotivoOficio.objects.create(
                nome=nome,
                texto=texto,
                ativo=True,
                ordem=ordem,
                is_padrao=is_padrao,
            )
        for nome, texto, ordem, is_padrao in _JUSTIFICATIVAS:
            ModeloJustificativa.objects.create(
                nome=nome,
                texto=texto,
                ativo=True,
                ordem=ordem,
                is_padrao=is_padrao,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Criados 5 modelos de motivo e 5 modelos de justificativa de teste."
            )
        )
