"""Diagnóstico somente leitura da tabela de Roteiros.

Não apaga nem altera nenhum registro. Lista cada roteiro com:
- quantos destinos/trechos possui;
- quais Ofícios, Prestações de Contas ou Evento apontam para ele;
- se está VAZIO (rascunho sem destino/trecho), ÓRFÃO (nada aponta para ele) ou
  faz parte de um grupo DUPLICADO (mesma sede, mesma sequência de destinos e
  mesma saída de outro(s) roteiro(s)).

Uso:
    python manage.py diagnosticar_roteiros
    python manage.py diagnosticar_roteiros --apenas-problemas
"""

from collections import defaultdict

from django.core.management.base import BaseCommand

from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro


class Command(BaseCommand):
    help = (
        "Lista os Roteiros cadastrados marcando quais estão vazios, órfãos (sem "
        "nenhum Ofício/Prestação de Contas/Evento referenciando) ou duplicados de "
        "outro roteiro. Apenas leitura, não altera o banco."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apenas-problemas",
            action="store_true",
            help="Omite da listagem os roteiros que não têm nenhum problema encontrado.",
        )

    def handle(self, *args, **options):
        apenas_problemas = options["apenas_problemas"]

        roteiros = list(
            Roteiro.objects.select_related("origem_estado", "origem_cidade")
            .prefetch_related("destinos__cidade", "trechos")
            .order_by("origem_cidade__nome", "pk")
        )

        oficios_por_roteiro = defaultdict(list)
        for oficio in Oficio.objects.filter(roteiro_id__isnull=False).only(
            "pk", "numero", "ano", "roteiro_id"
        ):
            oficios_por_roteiro[oficio.roteiro_id].append(oficio)

        prestacoes_por_roteiro = defaultdict(list)
        for pc in PrestacaoContas.objects.filter(roteiro_ajustado_id__isnull=False).only(
            "pk", "roteiro_ajustado_id"
        ):
            prestacoes_por_roteiro[pc.roteiro_ajustado_id].append(pc)

        info_por_roteiro = {}
        grupos_duplicados = defaultdict(list)
        for roteiro in roteiros:
            destino_ids = tuple(d.cidade_id for d in roteiro.destinos.all())
            info_por_roteiro[roteiro.pk] = destino_ids
            if roteiro.origem_cidade_id and destino_ids:
                assinatura = (roteiro.origem_cidade_id, destino_ids, roteiro.saida_dt)
                grupos_duplicados[assinatura].append(roteiro.pk)

        total = len(roteiros)
        total_orfaos = 0
        total_vazios = 0
        total_duplicados = 0
        linhas = []

        for roteiro in roteiros:
            destino_ids = info_por_roteiro[roteiro.pk]
            oficios = oficios_por_roteiro.get(roteiro.pk, [])
            prestacoes = prestacoes_por_roteiro.get(roteiro.pk, [])
            assinatura = (roteiro.origem_cidade_id, destino_ids, roteiro.saida_dt)
            grupo = grupos_duplicados.get(assinatura, [roteiro.pk])

            eh_duplicado = len(grupo) > 1
            eh_vazio = not destino_ids and roteiro.trechos.count() == 0
            eh_orfao = not oficios and not prestacoes and roteiro.evento_id is None

            if eh_orfao:
                total_orfaos += 1
            if eh_vazio:
                total_vazios += 1
            if eh_duplicado:
                total_duplicados += 1

            if apenas_problemas and not (eh_orfao or eh_vazio or eh_duplicado):
                continue

            tags = []
            if eh_orfao:
                tags.append("ORFAO")
            if eh_vazio:
                tags.append("VAZIO")
            if eh_duplicado:
                outros = sorted(pk for pk in grupo if pk != roteiro.pk)
                tags.append(f"DUPLICADO(tambem_em={outros})")
            if not tags:
                tags.append("ok")

            refs = []
            if oficios:
                refs.append(
                    "oficios="
                    + ",".join(
                        f"#{o.numero}/{o.ano}" if o.numero else f"pk{o.pk}"
                        for o in oficios
                    )
                )
            if prestacoes:
                refs.append(f"prestacoes={len(prestacoes)}")
            if roteiro.evento_id:
                refs.append(f"evento=#{roteiro.evento_id}")
            refs_str = "; ".join(refs) if refs else "sem referencias"

            titulo = self._titulo(roteiro)
            linhas.append(
                f"#{roteiro.pk:<6} {roteiro.status:<11} {titulo:<45} "
                f"destinos={len(destino_ids)} trechos={roteiro.trechos.count()} "
                f"criado={roteiro.created_at:%Y-%m-%d} "
                f"[{', '.join(tags)}] {refs_str}"
            )

        for linha in linhas:
            self.stdout.write(linha)

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"Resumo: {total} roteiros | {total_orfaos} orfaos | "
                f"{total_vazios} vazios | {total_duplicados} em grupos duplicados"
            )
        )

    def _titulo(self, roteiro):
        if roteiro.origem_cidade_id:
            origem = roteiro.origem_cidade.nome
        elif roteiro.origem_estado_id:
            origem = roteiro.origem_estado.sigla
        else:
            origem = "?"
        destinos = [d.cidade.nome for d in roteiro.destinos.all() if d.cidade_id]
        if destinos:
            return origem + " -> " + ", ".join(destinos)
        return origem
