"""Remove as Ordens de Serviço "rascunho em branco" enviadas ao Drive por engano.

Contexto: o backfill automático de OS (``organizer._garantir_ordens_servico``)
usava, por um bug, a função de geração ERRADA (``gerar_resposta_ordem_servico_documento``),
que produz uma versão RASCUNHO sem saber qual servidor foi designado
(``payload_snapshot["em_elaboracao"] == True``). Isso mandou PDFs em branco pro
Drive real para cada ofício com OS vinculada.

Este comando identifica exatamente esses artefatos (pela marca ``em_elaboracao``
no snapshot), apaga o arquivo do Drive real e o registro local, e — já com o
backfill corrigido (usa ``gerar_os_pdf_response``, com os dados reais) — deixa
o sistema pronto para o próximo "Reorganizar" gerar a versão correta.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.errors import capture


class Command(BaseCommand):
    help = "Remove OS 'rascunho em branco' (bug do backfill antigo) do banco e do Drive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista o que seria removido, sem apagar nada.",
        )

    def handle(self, *args, **options):
        from documentos.models import DocumentoArtefato
        from integracoes.google_drive.services import get_client

        candidatos = DocumentoArtefato.objects.filter(tipo="ordem_servico")
        quebrados = [
            art
            for art in candidatos
            if isinstance(art.payload_snapshot, dict) and art.payload_snapshot.get("em_elaboracao")
        ]

        self.stdout.write(f"OS rascunho (em_elaboracao=True) encontradas: {len(quebrados)}")
        if not quebrados:
            self.stdout.write(self.style.SUCCESS("Nada para limpar."))
            return

        for art in quebrados:
            drive_info = ""
            try:
                drive_info = f" | drive_file_id={art.drive_arquivo.file_id}"
            except Exception as exc:
                capture(exc, "drive.management.commands.gdrive_limpar_os_rascunho.handle")  # pragma: no cover
                pass
            self.stdout.write(f"  - {art.pk} | oficio={art.oficio_id}{drive_info}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: nada foi apagado."))
            return

        client = get_client()
        removidos_drive = 0
        for art in quebrados:
            try:
                reg = art.drive_arquivo
            except Exception as exc:
                capture(exc, "drive.management.commands.gdrive_limpar_os_rascunho.handle")  # pragma: no cover
                reg = None
            if reg is not None and reg.file_id and not reg.mock:
                client.excluir_arquivo(reg.file_id)
                removidos_drive += 1
            if reg is not None:
                reg.delete()
            art.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Removidos {len(quebrados)} artefato(s) quebrado(s); "
                f"{removidos_drive} arquivo(s) apagado(s) do Drive real."
            )
        )
        self.stdout.write(
            "Rode 'Reorganizar' (ou o comando gdrive_reorganizar) para gerar as OS corretas."
        )
