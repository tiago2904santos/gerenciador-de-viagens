from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Reorganiza a árvore do Google Drive por evento/categoria, movendo e "
        "renomeando os arquivos já enviados e subindo os que faltam. "
        "Usa as cópias locais (FileField) como fonte."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--evento",
            type=int,
            default=None,
            help="Reorganiza apenas o evento com este ID (padrão: todos).",
        )
        parser.add_argument(
            "--avulsos",
            action="store_true",
            help="Inclui ofícios sem evento (Avulsos). Por padrão são incluídos.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra os caminhos/nomes planejados, sem tocar no Drive.",
        )

    def handle(self, *args, **options):
        from eventos.models import Evento
        from integracoes.google_drive import organizer

        dry = options["dry_run"]
        evento_id = options["evento"]

        eventos = Evento.objects.all()
        if evento_id is not None:
            eventos = eventos.filter(pk=evento_id)

        total_eventos = eventos.count()
        self.stdout.write(f"Eventos a processar: {total_eventos}{' (dry-run)' if dry else ''}")

        for evento in eventos.iterator():
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(str(evento)))
            if dry:
                linhas = organizer.planejar_evento(evento)
                if not linhas:
                    self.stdout.write("  (nenhum arquivo)")
                for linha in linhas:
                    self.stdout.write(f"  {linha}")
            else:
                try:
                    organizer.organizar_evento(evento)
                    self.stdout.write(self.style.SUCCESS("  OK"))
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(self.style.ERROR(f"  ERRO: {exc}"))

        # Ofícios avulsos (sem evento) + artefatos órfãos
        self._processar_avulsos(dry)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Concluído."))

    def _processar_avulsos(self, dry: bool) -> None:
        from oficios.models import Oficio
        from integracoes.google_drive import organizer

        avulsos = Oficio.objects.filter(evento__isnull=True)
        total = avulsos.count()
        if total:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"Avulsos (ofícios sem evento): {total}"))
        for oficio in avulsos.iterator():
            if dry:
                for linha in organizer.planejar_oficio(oficio):
                    self.stdout.write(f"  {linha}")
            else:
                try:
                    organizer.organizar_oficio(oficio)
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(self.style.ERROR(f"  ERRO ofício {oficio.pk}: {exc}"))
