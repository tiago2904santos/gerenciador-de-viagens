"""Management command para criar/recriar protocolos de demonstração.

Executa o mesmo fluxo do ``garantir_protocolos_demo_treinamento`` mas de forma
explícita via linha de comando, útil para ambientes de treinamento/demo.
"""

from django.core.management.base import BaseCommand

from protocolos.services import garantir_protocolos_demo_treinamento


class Command(BaseCommand):
    help = "Cria ou atualiza os protocolos de demonstração para ambiente de treinamento."

    def handle(self, *args, **options):
        self.stdout.write("Criando protocolos de demonstração...")
        criados = garantir_protocolos_demo_treinamento()
        if criados:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(criados)} protocolo(s) de demonstração criado(s)/atualizado(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum protocolo criado. "
                    "Verifique se o ambiente de mock/treinamento está ativo."
                )
            )
