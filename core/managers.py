"""`BE-09` — o recorte por área deixa de depender de o programador lembrar.

Até aqui `core/tenancy.py:56` (`filter_queryset_by_area`) era função livre, aplicada
à mão em ~140 sites. Os ~288 `.objects.` nus sobre os 28 modelos com `area` não a
aplicavam, e quatro vazamentos entre áreas (`BE-04`, `BE-05`, `BE-10`, `DB-03`) foram
a prova de que a convenção falha.

## O interruptor é a request, e não a área

A parte que exige explicação é a linha `if get_current_request() is None: return`.

Fora de um request `get_current_area()` devolve `None`, e com `None`
`filter_queryset_by_area` devolve o balde `area IS NULL` — quase sempre vazio. Se o
manager herdasse essa semântica, o efeito em produção seria, medido:

- `documentos/tasks.py:33` — `Oficio.objects.filter(pk=...).first()` viraria `None`,
  engolido pelo `if oficio is None: return` da própria task. Geração de PDF vira
  no-op, sem log e sem retry.
- `documentos/services/async_generation.py:56` — `model.objects.get(pk=pk)` levantaria
  `DoesNotExist` para todo job assíncrono.
- `roteiros/management/commands/limpar_roteiros_orfaos.py` — "órfão" viraria falso
  positivo e o comando **apagaria o que não devia**.
- `core/management/commands/backfill_legacy_areas.py` — o comando que existe para
  achar `area IS NULL` se auto-filtraria.

E nada disso apareceria na suíte: `config/settings/test.py:64` liga
`CELERY_TASK_ALWAYS_EAGER = True`, então nos testes a task roda **dentro** do request,
com o thread-local populado. Por isso o teste de contrato usa `sem_request()`
explicitamente — é o único jeito de alcançar esse caminho.

Worker, comando, shell e script continuam recortando sozinhos, com o `pk` ou o
`area_id` que já recebem hoje. O manager não muda nada para eles.

## O que continua irrestrito, e por quê

`objects` **não** é o `_default_manager`: cada modelo declara
`Meta.default_manager_name = "all_objects"`. Isso mantém idênticos, sem uma linha
alterada, os caminhos que o Django resolve sozinho a partir do `_default_manager`
(verificado no Django 5.2.17 instalado):

- admin (`contrib/admin/options.py:437`) — a ferramenta de emergência;
- campos de FK gerados por `ModelForm` (`db/models/fields/related.py:1213`);
- `validate_unique` (`db/models/base.py:1505`) e `UniqueConstraint.validate`
  (`db/models/constraints.py:623`) — senão o erro migra do formulário para um
  `IntegrityError` no INSERT;
- relações reversas e M2M (`related_descriptors.py:642, 1022`), que derivam a classe
  do manager de `_default_manager.__class__`;
- `dumpdata` (`core/management/commands/dumpdata.py:215`);
- `core/tenancy.py:116` (guarda m2m entre áreas), `core/checks.py:50` (`core.E001`) e
  `core/management/commands/backfill_legacy_areas.py`, que usam `_default_manager`
  explicitamente — os três **precisam** enxergar todas as áreas para funcionar.

O `_base_manager` nunca é afetado: sem `Meta.base_manager_name`, o Django instancia um
`Manager()` limpo (`db/models/options.py:492`). Travessia de FK, `save()`,
`refresh_from_db()` e a cascata de delete continuam atravessando fronteira de área.

## A armadilha do modelo histórico — ler antes de migrar o próximo app

`db/migrations/state.py:896-919` só conserva, no `ModelState`, managers que sejam
`_default_manager`, `_base_manager` ou `use_in_migrations`. O `objects` recortado não
é nenhum dos três, então **ele deixa de existir no modelo histórico** a partir da
migração `AlterModelManagers` do app. O `all_objects`, por ser `_default_manager`,
sobrevive como `Manager` puro — e **antes** daquela migração ele ainda não existe.

Ou seja, dentro de `RunPython` a escolha depende da posição no grafo, não do modelo:

- migração **anterior** ao `AlterModelManagers` do app → só existe `objects`;
- migração **posterior** → só existe `all_objects`.

Ambos os lados falham alto (`AttributeError` no `migrate`, antes de tocar em dado) —
por isso não há catraca para isto: `manage.py test` e o deploy já são o gate. O que
não é óbvio é que o erro pode aparecer numa migração de **outro app**: foi o caso de
`prestacoes_contas/migrations/0008`, que faz `apps.get_model("oficios", "Oficio")` e
roda depois de `oficios/0018`. Ao migrar um app, confira `migrate --plan` e corrija
só as migrações posicionadas **depois** da nova.

Não usar `use_in_migrations = True` para contornar isso: ele congelaria
`core.managers.AreaScopedManager` dentro de toda migração futura, que é exatamente o
acoplamento que o modelo histórico existe para evitar.
"""

from __future__ import annotations

from django.db import models

from core.tenancy import filter_queryset_by_area


class AreaScopedManager(models.Manager):
    """`objects` que recorta pela área ativa quando existe request."""

    #: Modelo histórico de migração precisa continuar com `Manager` puro. Com o
    #: padrão `False`, `db/migrations/state.py:905` troca este manager por um shim
    #: limpo ao montar o `ModelState`. Não mexer.
    use_in_migrations = False

    def __init__(self, *, campo: str = "area"):
        """``campo`` é o mesmo hook de `filter_queryset_by_area`, para o modelo que
        não tem coluna `area` e herda a fronteira de um vínculo obrigatório — hoje só
        `Justificativa`, via `oficio__area` (`justificativas/selectors.py:24`)."""
        super().__init__()
        self.campo = campo

    def get_queryset(self):
        # Import tardio pelo mesmo motivo de `core/tenancy.py:11`: `core.middleware`
        # importa middleware do `django.contrib.auth` no topo, e este módulo é
        # carregado enquanto os modelos ainda estão sendo montados.
        from core.middleware import get_current_request

        queryset = super().get_queryset()
        if get_current_request() is None:
            return queryset
        return filter_queryset_by_area(queryset, campo=self.campo)
