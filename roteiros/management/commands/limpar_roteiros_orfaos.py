"""Apaga roteiros órfãos: sem nenhum Ofício, Prestação de Contas ou Evento
apontando para eles.

Por padrão roda em modo dry-run (só lista os candidatos, não apaga nada).
Só apaga de fato quando chamado com --confirmar.

Uso:
    python manage.py limpar_roteiros_orfaos                # dry-run
    python manage.py limpar_roteiros_orfaos --confirmar     # apaga de verdade
"""

from django.core.management.base import BaseCommand

from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro


class Command(BaseCommand):
    help = (
        "Lista (ou, com --confirmar, apaga) roteiros que não têm nenhum Ofício, "
        "Prestação de Contas ou Evento referenciando-os."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Executa a exclusão de fato. Sem essa flag, apenas lista os candidatos (dry-run).",
        )

    def handle(self, *args, **options):
        confirmar = options["confirmar"]

        oficios_com_roteiro = set(
            Oficio.objects.filter(roteiro_id__isnull=False).values_list("roteiro_id", flat=True)
        )
        prestacoes_com_roteiro = set(
            PrestacaoContas.objects.filter(roteiro_ajustado_id__isnull=False).values_list(
                "roteiro_ajustado_id", flat=True
            )
        )

        candidatos = (
            Roteiro.objects.filter(evento_id__isnull=True)
            .exclude(pk__in=oficios_com_roteiro)
            .exclude(pk__in=prestacoes_com_roteiro)
            .select_related("origem_estado", "origem_cidade")
            .order_by("pk")
        )

        if not candidatos.exists():
            self.stdout.write(self.style.SUCCESS("Nenhum roteiro orfao encontrado."))
            return

        for roteiro in candidatos:
            origem = roteiro.origem_cidade or roteiro.origem_estado or f"Roteiro #{roteiro.pk}"
            self.stdout.write(
                f"#{roteiro.pk:<6} {roteiro.status:<11} {str(origem):<30} criado={roteiro.created_at:%Y-%m-%d}"
            )

        total = candidatos.count()
        if confirmar:
            candidatos.delete()
            self.stdout.write(self.style.WARNING(f"{total} roteiro(s) orfao(s) apagado(s)."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{total} roteiro(s) seriam apagados. Rode novamente com --confirmar para excluir de fato."
                )
            )
