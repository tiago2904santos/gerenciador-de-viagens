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
        from integracoes.google_drive.services import is_mock, mimetype_para_formato, upload_artefato

        enviados_ids = DriveArquivo.objects.values_list("artefato_id", flat=True)
        pendentes = (
            DocumentoArtefato.objects.exclude(pk__in=enviados_ids)
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
            result = upload_artefato(art)
            if result is None:
                erros += 1
                self.stdout.write(self.style.ERROR(f"  ERRO  {art.pk}"))
                continue

            file_id, url = result
            nome = art.arquivo.name.rsplit("/", 1)[-1] if art.arquivo else ""
            DriveArquivo.objects.create(
                artefato=art,
                file_id=file_id,
                url=url,
                nome=nome,
                mime_type=mimetype_para_formato(art.formato),
                mock=is_mock(),
            )
            ok += 1
            self.stdout.write(f"  OK    {art.pk} → {file_id}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Concluído: {ok} enviados, {erros} erros."))
