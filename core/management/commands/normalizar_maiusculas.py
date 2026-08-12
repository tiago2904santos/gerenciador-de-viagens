"""Leva os registros antigos para a caixa que a máscara passou a exigir.

O `NOVO-53`/`NOVO-55` puseram `data-mask="upper"` em 59 campos de texto. A
máscara age no navegador, então ela vale **do próximo salvamento em diante**:
tudo que já estava gravado continua na caixa em que foi digitado. O sistema
passa a ter duas populações no mesmo campo, e quem lê a lista vê a diferença.

Este comando responde às duas perguntas dessa dívida, nesta ordem:

  1. quais campos de **modelo** herdaram a máscara (campo de formulário sem
     modelo por trás não tem histórico para migrar);
  2. quantas linhas de cada um divergem da própria versão em maiúscula.

Sem `--commit` ele só relata. É a mesma convenção do `backfill_legacy_areas`,
e aqui ela importa mais: a operação é destrutiva por natureza — "São Paulo"
vira "SÃO PAULO" e não há como voltar sem backup.

## Por que a descoberta é dinâmica

A lista de campos podia estar escrita aqui, e ficaria errada no dia seguinte.
Ela é derivada de onde a decisão realmente mora: o widget do formulário. Um
campo que ganhar `text_attrs` amanhã entra neste relatório sem ninguém editar
este arquivo; um campo que sair da máscara some dele.

O preço é que formulário que não instancia sem argumento não pode ser
inspecionado. O comando **conta e nomeia** esses casos em vez de ignorá-los em
silêncio — um inventário que omite o que não conseguiu ler é pior que nenhum.

## Por que a maiúscula é calculada em Python, e não com `UPPER()` do banco

Quem define o que é "maiúscula" neste sistema não é o PostgreSQL: é o
`toUpperCase()` do navegador, que a máscara aplica enquanto o usuário digita.
A migração existe para deixar o histórico igual ao que a máscara produziria —
então ela tem que usar a mesma definição, não uma parecida.

A primeira versão usava `Upper()` do Django, que vira `UPPER()` no SQL. Isso
delega a regra ao banco, e a regra do banco depende do `LC_CTYPE` dele. A suíte
mostrou o problema em uma linha: em SQLite, `UPPER('Reunião')` devolve
`'REUNIãO'` — maiúsculo só no ASCII. O resultado seria um campo em caixa
**mista**, pior que o estado que a migração veio corrigir, e num sistema em
português quase todo nome tem acento.

Em PostgreSQL com locale UTF-8 o acento sai certo, e é por isso que o defeito
não apareceu no banco de desenvolvimento. Mas "certo desde que o servidor esteja
com o locale certo" não é garantia que se queira num `UPDATE` irreversível sobre
a base inteira.

`str.upper()` do Python segue o mesmo mapeamento Unicode que o `toUpperCase()`
do JavaScript. A comparação que decide o que diverge usa a mesma função, então
contagem e escrita concordam entre si e com a tela.

## Por que a colisão é decidida pelo banco

Passar tudo para maiúscula numa coluna única pode juntar duas linhas numa chave só:
"Reunião" e "REUNIÃO" convivem hoje e não convivem depois.

A tentação era procurar esses pares em Python, agrupando por valor. Isso
reimplementaria a semântica de unicidade — e ela não é simples aqui:
`TipoEvento` tem duas `UniqueConstraint` com `condition`, uma valendo só para
linhas sem área e outra só para linhas com área. Agrupar por valor ignorando a
condição bloquearia campo que está perfeitamente bem.

Então quem decide é o banco: o `UPDATE` roda dentro de um savepoint. Se passar,
passou de verdade — com condição, colação e índice parcial incluídos. Se falhar,
o savepoint volta, o campo fica de fora e a mensagem do PostgreSQL (que nomeia a
restrição e o valor duplicado) vai no relatório. Na simulação a transação
inteira volta no fim.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from collections import defaultdict

from django import forms
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db import models
from django.db import transaction

from core.forms.widgets import NOMES_SEM_MAIUSCULA

logger = logging.getLogger(__name__)

MASCARA = "upper"


class Command(BaseCommand):
    help = (
        "Relata (e com --commit aplica) a normalização em maiúscula dos "
        "registros gravados antes da máscara dos campos de texto."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Aplica as alterações; sem esta opção apenas exibe o plano.",
        )
        parser.add_argument(
            "--campo",
            action="append",
            default=[],
            metavar="app.Modelo.campo",
            help=(
                "Restringe a um ou mais campos. Repetível. Sem esta opção, "
                "todos os campos com máscara entram."
            ),
        )

    # ------------------------------------------------------------ descoberta
    def _classes_de_formulario(self):
        """Todo `ModelForm` declarado nos módulos `forms` dos apps do projeto."""
        for config in apps.get_app_configs():
            if config.name.startswith("django."):
                continue
            try:
                modulo = importlib.import_module(f"{config.name}.forms")
            except ModuleNotFoundError:
                continue
            for objeto in vars(modulo).values():
                if not inspect.isclass(objeto):
                    continue
                if not issubclass(objeto, forms.BaseForm):
                    continue
                # Só o que o módulo declara: reexportação contaria duas vezes,
                # e um formulário de pacote é inspecionado no módulo dele.
                if objeto.__module__ != modulo.__name__:
                    continue
                if getattr(getattr(objeto, "Meta", None), "model", None) is None:
                    continue
                yield objeto

    def _campos_com_mascara(self):
        """(label do modelo, nome do campo) para cada campo mascarado.

        Devolve também os formulários que não puderam ser instanciados — o
        inventário precisa dizer o tamanho do próprio ponto cego.
        """
        pares: set[tuple[str, str]] = set()
        origens: dict[tuple[str, str], set[str]] = defaultdict(set)
        nao_lidos: list[tuple[str, str]] = []
        reservados: list[str] = []

        for classe in self._classes_de_formulario():
            modelo = classe.Meta.model
            try:
                instancia = classe()
            except Exception as erro:  # noqa: BLE001 - o motivo vai no relatório
                logger.debug(
                    "Formulário ignorado no inventário de maiúsculas: %s.%s",
                    classe.__module__,
                    classe.__name__,
                    exc_info=erro,
                )
                nao_lidos.append(
                    (f"{classe.__module__}.{classe.__name__}", type(erro).__name__),
                )
                continue
            concretos = {
                campo.name
                for campo in modelo._meta.concrete_fields
                if isinstance(campo, (models.CharField, models.TextField))
            }
            for nome, campo in instancia.fields.items():
                if campo.widget.attrs.get("data-mask") != MASCARA:
                    continue
                if nome not in concretos:
                    continue
                # Segunda tranca, e ela não é redundância. A lista de campos vem
                # do formulário; se um formulário voltar a mascarar `username`,
                # o comando reescreveria a chave que o Django compara byte a
                # byte no login e ninguém mais entraria. Foi exatamente o que
                # aconteceu (`NOVO-56`) — e foi este comando que descobriu.
                #
                # Não é `continue` silencioso: o campo estar aqui já significa
                # que um formulário está errado, e isso precisa aparecer.
                if nome in NOMES_SEM_MAIUSCULA or nome.endswith("_busca_ui"):
                    reservados.append(
                        f"{classe.__module__}.{classe.__name__}.{nome} "
                        f"({modelo._meta.label})",
                    )
                    continue
                chave = (modelo._meta.label, nome)
                pares.add(chave)
                origens[chave].add(classe.__name__)

        return sorted(pares), origens, nao_lidos, sorted(set(reservados))

    # ------------------------------------------------------------- execução
    def _gerenciador(self, modelo):
        """Modelo com exclusão lógica esconde linhas do gerenciador padrão."""
        return getattr(modelo, "all_objects", modelo._default_manager)

    def _divergentes(self, gerenciador, campo: str) -> list[tuple]:
        """(pk, valor em maiúscula) das linhas que não estão em maiúscula.

        A comparação é em Python, e isso não é detalhe de implementação.
        """
        divergentes = []
        for pk, valor in gerenciador.values_list("pk", campo):
            if not valor:
                continue
            alto = str(valor).upper()
            if alto != valor:
                divergentes.append((pk, alto))
        return divergentes

    def _aplicar(self, modelo, campo: str, divergentes: list[tuple]) -> tuple[int, str]:
        """Grava num savepoint. Devolve (linhas, erro)."""
        objetos = [modelo(pk=pk, **{campo: valor}) for pk, valor in divergentes]
        try:
            with transaction.atomic():
                # `bulk_update` e não `save()`: o `auto_now` de `atualizado_em`
                # marcaria toda a base com a data da migração, e mudar a caixa
                # não é edição de conteúdo feita por ninguém.
                self._gerenciador(modelo).bulk_update(objetos, [campo], batch_size=500)
        except IntegrityError as erro:
            return 0, " ".join(str(erro).split())
        return len(objetos), ""

    def handle(self, *args, **options):
        pares, origens, nao_lidos, reservados = self._campos_com_mascara()

        filtro = set(options["campo"])
        if filtro:
            pares = [
                (label, campo)
                for label, campo in pares
                if f"{label}.{campo}" in filtro
            ]
            desconhecidos = filtro - {f"{label}.{campo}" for label, campo in pares}
            for alvo in sorted(desconhecidos):
                self.stdout.write(
                    self.style.WARNING(f"{alvo}: não é campo de modelo com máscara."),
                )

        self.stdout.write(f"campos de modelo com máscara: {len(pares)}")
        if reservados:
            self.stdout.write(
                self.style.ERROR(
                    f"campos reservados mascarados por engano: {len(reservados)} "
                    "— não serão migrados, e o formulário precisa ser corrigido:",
                ),
            )
            for alvo in reservados:
                self.stdout.write(f"  {alvo}")
        if nao_lidos:
            self.stdout.write(
                self.style.WARNING(
                    f"formulários não inspecionados: {len(nao_lidos)} "
                    "(exigem argumento no construtor)",
                ),
            )
            for nome, erro in sorted(nao_lidos):
                self.stdout.write(f"  {nome} ({erro})")
        self.stdout.write("")

        # Simulação e aplicação percorrem exatamente o mesmo caminho: as duas
        # escrevem no banco. A diferença é só que a simulação desfaz no fim, e
        # é isso que faz o relatório valer — um "vai dar certo" que não tentou
        # escrever não vale nada num campo com restrição de unicidade.
        with transaction.atomic():
            resumo = self._percorrer(pares)
            if not options["commit"]:
                transaction.set_rollback(True)

        if origens and options["verbosity"] >= 2:
            self.stdout.write("")
            self.stdout.write("origem da máscara, por campo:")
            for (label, campo), classes in sorted(origens.items()):
                self.stdout.write(f"  {label}.{campo}: {', '.join(sorted(classes))}")

        if not options["commit"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("Simulação: nada foi gravado. Use --commit."),
            )
            return
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Normalização concluída: {resumo} linha(s)."),
        )

    def _percorrer(self, pares) -> int:
        self.stdout.write(f"{'modelo.campo':<52}{'linhas':>8}{'divergem':>10}")
        bloqueado: list[tuple[str, str]] = []
        total_linhas = total_divergem = total_aplicado = 0

        for label, campo in pares:
            modelo = apps.get_model(label)
            gerenciador = self._gerenciador(modelo)
            linhas = gerenciador.count()
            divergentes = self._divergentes(gerenciador, campo)
            total_linhas += linhas
            total_divergem += len(divergentes)

            erro = ""
            if divergentes:
                aplicado, erro = self._aplicar(modelo, campo, divergentes)
                total_aplicado += aplicado

            marca = "  BLOQUEADO" if erro else ("  <-" if divergentes else "")
            self.stdout.write(
                f"{label + '.' + campo:<52}{linhas:>8}{len(divergentes):>10}{marca}",
            )
            if erro:
                bloqueado.append((f"{label}.{campo}", erro))

        self.stdout.write(f"{'TOTAL':<52}{total_linhas:>8}{total_divergem:>10}")

        if bloqueado:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    f"campos bloqueados por unicidade ({len(bloqueado)}) — a "
                    "maiúscula juntaria duas linhas numa chave só. Resolva o "
                    "par no sistema antes de migrar o campo:",
                ),
            )
            for alvo, erro in bloqueado:
                self.stdout.write(f"  {alvo}")
                self.stdout.write(f"    {erro}")
        return total_aplicado
