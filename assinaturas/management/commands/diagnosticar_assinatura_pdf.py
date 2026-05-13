from __future__ import annotations

from django.core.management.base import BaseCommand

from assinaturas.services.validacao_codigo import validar_assinatura_por_codigo


class Command(BaseCommand):
    help = "Diagnostica o estado de uma assinatura pela etiqueta (codigo CV-...)."

    def add_arguments(self, parser):
        parser.add_argument("codigo", type=str)

    def handle(self, *args, **options):
        codigo = options["codigo"]
        r = validar_assinatura_por_codigo(codigo)
        self.stdout.write(f"codigo: {codigo}")
        self.stdout.write(f"existe: {r['existe']}")
        if not r["existe"]:
            self.stdout.write("motivo: codigo_desconhecido")
            return
        ass = r["assinatura"]
        art = r["artefato"]
        assert ass is not None and art is not None
        self.stdout.write(f"assinatura_id: {ass.pk}")
        self.stdout.write(f"artefato_id: {art.pk}")
        self.stdout.write(f"hash_esperado: {r['hash_esperado']}")
        self.stdout.write(f"hash_atual: {r['hash_atual']}")
        self.stdout.write(f"integra: {r['integra']}")
        self.stdout.write(f"pdf_assinado_disponivel: {r['pdf_assinado_disponivel']}")
        self.stdout.write(f"motivo: {r['motivo']}")
        ev = ass.posicao_carimbo_json or {}
        self.stdout.write(f"posicao_carimbo: {ev}")
        self.stdout.write(f"pagina_carimbo: {ass.pagina_carimbo}")
