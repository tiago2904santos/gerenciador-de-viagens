"""Utilidades de teste para a fronteira de área (`BE-09`/`DB-02`).

Fica fora de `core/tests/` de propósito: todo app importa daqui, e módulo dentro
de `tests/` de um app importado por outro app vira acoplamento entre suítes.

`DB-02` tornou `area` NOT NULL nos oito modelos operacionais. Centenas de testes
anteriores criavam esses registros sem área — não por testarem isolamento, mas
porque a coluna aceitava NULL e o teste nasceu antes dela. Para esses, o custo de
satisfazer o invariante precisa ser uma linha: `area=area_de_teste()`.

Testes que **testam** a fronteira (contrato do manager, vazamento entre áreas)
continuam criando as próprias áreas nomeadas e usando `com_request`/`sem_request`
— os mesmos deste módulo, promovidos de `core/tests/test_area_scoped_manager.py`
quando o `DB-02` os tornou necessários fora dele.
"""

from __future__ import annotations

from contextlib import contextmanager

from django.test import RequestFactory


def area_de_teste(sigla="TST", nome="Área de teste"):
    """Área idempotente para satisfazer o NOT NULL do `DB-02`.

    `get_or_create` por sigla: chamadas repetidas no mesmo teste (ou no mesmo
    `setUpTestData`) devolvem a mesma linha, então dois registros criados "sem
    pensar em área" continuam na mesma área — que é o que o teste antigo
    assumia quando tudo era NULL.
    """
    from usuarios.models import AreaTrabalho

    area, criada = AreaTrabalho.objects.get_or_create(sigla=sigla, defaults={"nome": nome})
    if criada:
        # NOVO-49: a fixture representa o fluxo de criação real, que instala os
        # quatro catálogos no mesmo instante em que a área nasce.
        from core.catalogos_iniciais import semear_catalogos_da_area

        semear_catalogos_da_area(area)
    return area


def vincular_area(usuario, area=None, **campos):
    """Vínculo idempotente do usuário à área de teste (ou à `area` dada).

    Testes de view antigos logavam um usuário **sem vínculo** e enxergavam o
    balde `area IS NULL` — a semântica do próprio defeito do `DB-02`. Com o
    NOT NULL esse balde operacional é vazio por construção; o teste passa a
    declarar o que produção sempre exigiu: usuário vê dado da área a que está
    vinculado.
    """
    from usuarios.models import VinculoUsuarioArea

    area = area or area_de_teste()
    vinculo, _ = VinculoUsuarioArea.objects.get_or_create(
        usuario=usuario,
        area=area,
        defaults={"ativo": True, "area_padrao": True, **campos},
    )
    return vinculo


@contextmanager
def sem_request():
    """Reproduz o contexto de worker/comando: nenhum request no thread-local.

    `CurrentRequestMiddleware` limpa `_local.request` num `finally`, então num
    teste comum ele já está vazio — o valor deste helper é declarar a intenção
    e proteger contra teste vizinho que tenha vazado estado.
    """
    from core.middleware import sem_request as contexto_sem_request

    with contexto_sem_request():
        yield


@contextmanager
def com_request(area):
    """Simula o ciclo de request com uma área ativa (ou `None`)."""
    from core import middleware

    anterior = getattr(middleware._local, "request", None)
    request = RequestFactory().get("/")
    request.area = area
    request.vinculo_area = None
    middleware._local.request = request
    try:
        yield request
    finally:
        middleware._local.request = anterior
