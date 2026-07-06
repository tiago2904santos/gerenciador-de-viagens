from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Faz upload para o Drive de DocumentoArtefatos que ainda não foram enviados"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=100,
            help="Número máximo de artefatos a processar (padrão: 100)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista os pendentes sem fazer upload",
        )

    def handle(self, *args, **options):
        from documentos.models import DocumentoArtefato
        from integracoes.google_drive.models import DriveArquivo
        from integracoes.google_drive.services import upload_artefato

        # Só PDF sobe ao Drive (DOCX/XLSX ficam só no sistema local) — sem esse
        # filtro, artefatos não-PDF nunca ganhariam DriveArquivo e apareceriam
        # sempre como "pendentes", mesmo sem nada de errado.
        enviados_ids = DriveArquivo.objects.values_list("artefato_id", flat=True)
        pendentes = (
            DocumentoArtefato.objects.filter(formato__iexact="pdf")
            .exclude(pk__in=enviados_ids)
            .order_by("criado_em")[: options["limite"]]
        )

        total = pendentes.count()
        self.stdout.write(f"Artefatos pendentes: {total}")

        if options["dry_run"]:
            for art in pendentes:
                self.stdout.write(f"  - {art.pk} | {art.tipo} | {art.formato} | {art.criado_em:%Y-%m-%d %H:%M}")
            return

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nenhum artefato pendente."))
            return

        ok = 0
        erros = 0
        for art in pendentes:
            # organizar_artefato (via upload_artefato) já cria o DriveArquivo.
            result = upload_artefato(art)
            if result is None:
                erros += 1
                self.stdout.write(self.style.ERROR(f"  ERRO  {art.pk}"))
                continue

            file_id, _url = result
            ok += 1
            self.stdout.write(f"  OK    {art.pk} → {file_id}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Concluído: {ok} enviados, {erros} erros."))
