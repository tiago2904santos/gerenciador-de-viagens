"""Desvincula e apaga um roteiro vazio (sem destino/trecho) que ainda está
referenciado por algum Ofício ou Prestação de Contas — o caso do
`limpar_roteiros_orfaos` não cobre, porque esse comando só mexe em roteiros
sem NENHUMA referência.

Recusa a operar se o roteiro tiver qualquer destino ou trecho (não é "vazio")
— assim não há risco de apagar um roteiro com dado real por engano.

Por padrão roda em modo dry-run (só mostra o que faria). Só altera o banco
com --confirmar.

Uso:
    python manage.py desvincular_roteiro_vazio <pk>
    python manage.py desvincular_roteiro_vazio <pk> --confirmar
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro


class Command(BaseCommand):
    help = (
        "Desvincula (Oficio/PrestacaoContas) e apaga um roteiro vazio (sem destino "
        "nem trecho) pelo pk. Recusa se o roteiro tiver algum destino/trecho. "
        "Dry-run por padrao; use --confirmar para aplicar."
    )

    def add_arguments(self, parser):
        parser.add_argument("pk", type=int, help="pk do Roteiro a desvincular/apagar")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Executa de fato. Sem essa flag, apenas mostra o que seria feito (dry-run).",
        )

    def handle(self, *args, **options):
        pk = options["pk"]
        confirmar = options["confirmar"]

        try:
            roteiro = Roteiro.objects.get(pk=pk)
        except Roteiro.DoesNotExist:
            raise CommandError(f"Roteiro #{pk} não encontrado.")

        if roteiro.destinos.exists() or roteiro.trechos.exists():
            raise CommandError(
                f"Roteiro #{pk} tem destino(s) e/ou trecho(s) — não é um roteiro vazio. "
                "Nada foi feito."
            )

        oficios = list(Oficio.objects.filter(roteiro_id=pk))
        prestacoes = list(PrestacaoContas.objects.filter(roteiro_ajustado_id=pk))

        for oficio in oficios:
            label = f"#{oficio.numero}/{oficio.ano}" if oficio.numero else f"pk{oficio.pk}"
            self.stdout.write(f"Oficio {label}: roteiro -> None")
        for pc in prestacoes:
            self.stdout.write(f"PrestacaoContas #{pc.pk}: roteiro_ajustado -> None")
        self.stdout.write(f"Roteiro #{pk} (vazio) seria apagado")

        if not confirmar:
            self.stdout.write(
                self.style.WARNING("Nada foi alterado. Rode novamente com --confirmar para aplicar.")
            )
            return

        with transaction.atomic():
            for oficio in oficios:
                oficio.roteiro = None
                oficio.save(update_fields=["roteiro", "updated_at"])
            for pc in prestacoes:
                pc.roteiro_ajustado = None
                pc.save(update_fields=["roteiro_ajustado", "atualizado_em"])
            roteiro.delete()

        self.stdout.write(self.style.WARNING(f"Roteiro #{pk} desvinculado e apagado."))
