"""Remove o sufixo " - {cidade}/{UF}" que a geracao automatica de titulo do
Evento costumava colar no final (ver eventos/views.py, etapa 1 do wizard).

Esse sufixo duplicava a cidade, pois o card de listagem (evento_list_card.html)
ja concatena "titulo · destino · periodo" separadamente. O gerador de titulo foi
corrigido para nao colar mais a cidade, mas eventos ja salvos com o padrao
antigo continuam com o titulo duplicado ate serem corrigidos por este comando.

So remove o sufixo quando ele bater exatamente com o destino do proprio evento
(destino_cidade[/destino_uf] ou so destino_uf) — nao mexe em titulos digitados
manualmente que so por coincidencia terminem em algo parecido, a menos que o
final seja identico ao destino calculado.

Por padrao roda em modo dry-run (so mostra o que faria). Só altera o banco
com --confirmar.

Uso:
    python manage.py corrigir_titulo_evento_duplicado
    python manage.py corrigir_titulo_evento_duplicado --confirmar
"""

from django.core.management.base import BaseCommand


from eventos.models import Evento


def _sufixo_destino(evento) -> str:
    cidade = (evento.destino_cidade or "").strip()
    uf = (evento.destino_uf or "").strip()
    if cidade:
        destino = f"{cidade}/{uf}" if uf else cidade
    elif uf:
        destino = uf
    else:
        return ""
    return f" - {destino}"


class Command(BaseCommand):
    help = (
        "Remove o sufixo ' - {cidade}/{UF}' duplicado do titulo de eventos "
        "gerado pela versao antiga do auto-preenchimento. Dry-run por padrao; "
        "use --confirmar para aplicar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Executa de fato. Sem essa flag, apenas mostra o que seria feito (dry-run).",
        )

    def handle(self, *args, **options):
        confirmar = options["confirmar"]

        afetados = []
        for evento in Evento.objects.all():
            sufixo = _sufixo_destino(evento)
            if not sufixo:
                continue
            titulo = evento.titulo or ""
            if titulo == sufixo.lstrip(" -") or not titulo.endswith(sufixo):
                continue
            novo_titulo = titulo[: -len(sufixo)].strip()
            if not novo_titulo:
                continue
            afetados.append((evento, titulo, novo_titulo))

        if not afetados:
            self.stdout.write("Nenhum evento com titulo duplicado encontrado.")
            return

        for evento, titulo, novo_titulo in afetados:
            self.stdout.write(f"Evento #{evento.pk}: {titulo!r} -> {novo_titulo!r}")

        if not confirmar:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(afetados)} evento(s) seriam corrigidos. "
                    "Nada foi alterado. Rode novamente com --confirmar para aplicar."
                )
            )
            return

        for evento, _titulo, novo_titulo in afetados:
            evento.titulo = novo_titulo
            evento.save(update_fields=["titulo"])

        self.stdout.write(self.style.WARNING(f"{len(afetados)} evento(s) corrigido(s)."))
