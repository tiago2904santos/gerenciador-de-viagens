"""Remove arquivos duplicados (mesmo nome) nas pastas globais de tipo do Drive.

Contexto: por execuções concorrentes de "Reorganizar"/geração automática, o
mesmo documento pode ter acabado enviado mais de uma vez para a mesma pasta
canônica (Ofícios/Termos/Planos de trabalho/Ordens de serviço/Justificativas),
com o mesmo nome. Este comando junta os duplicados: mantém o mais recente e
apaga os demais, corrigindo o ``DriveArquivo`` local se ele apontava para um
dos removidos.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

_TIPOS = ["oficio", "justificativa", "termo_autorizacao", "ordem_servico", "plano_trabalho"]


class Command(BaseCommand):
    help = "Remove arquivos duplicados (mesmo nome) nas pastas globais de tipo do Drive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista os duplicados encontrados, sem apagar nada.",
        )

    def handle(self, *args, **options):
        from integracoes.google_drive import naming
        from integracoes.google_drive.models import DriveArquivo
        from integracoes.google_drive.services import get_client, get_pasta_raiz_id

        client = get_client()
        raiz = get_pasta_raiz_id() or None
        dry_run = options["dry_run"]

        total_grupos = 0
        total_removidos = 0

        for tipo in _TIPOS:
            nome_pasta = naming.pasta_tipo(tipo)
            pasta_id = client.get_or_create_pasta(nome_pasta, raiz)
            arquivos = client.listar_arquivos(pasta_id)

            por_nome: dict[str, list[dict]] = {}
            for arq in arquivos:
                por_nome.setdefault(arq["name"], []).append(arq)

            for nome, grupo in por_nome.items():
                if len(grupo) <= 1:
                    continue
                total_grupos += 1
                grupo.sort(key=lambda a: a.get("modifiedTime", ""), reverse=True)
                manter, remover = grupo[0], grupo[1:]
                self.stdout.write(
                    f"{nome_pasta}/{nome}: {len(grupo)} cópias — mantendo {manter['id']}, "
                    f"removendo {len(remover)}"
                )
                if dry_run:
                    continue

                removidos_ids = []
                for arq in remover:
                    client.excluir_arquivo(arq["id"])
                    removidos_ids.append(arq["id"])
                    total_removidos += 1

                DriveArquivo.objects.filter(file_id__in=removidos_ids).update(file_id=manter["id"])

        if dry_run:
            self.stdout.write(self.style.WARNING(f"--dry-run: {total_grupos} grupo(s) com duplicata, nada apagado."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{total_grupos} grupo(s) com duplicata; {total_removidos} arquivo(s) removido(s)."
                )
            )
