"""`BE-15` — a numeração do Plano de Trabalho sob concorrência real.

Rede escrita **antes** de qualquer mudança, como o catálogo exige.

O plano é o caso (c) do `BE-15`, de natureza diferente dos outros dois: em vez de varrer a
tabela atrás do maior número, ele mantém um **contador persistido** em
`ConfiguracaoSistema.pt_ultimo_numero` e o serializa com `select_for_update` na própria
linha do contador. Não usa advisory lock.

Isso é defensável — travar o contador é travar exatamente o recurso disputado —, e este
teste existe para provar que funciona antes de mexer. Ao contrário dos outros dois, aqui o
`select_for_update` funciona **nos dois bancos**; mesmo assim o teste fica restrito ao
PostgreSQL, porque o SQLite serializa escrita no nível do arquivo e duas threads ali não
provam concorrência de verdade — passariam por acidente do banco, não por mérito do código.

O que o teste **não** cobre, e a fatia 3 vai cobrir: o plano não tem retry. Uma colisão que
escape do contador sobe `IntegrityError` cru para o usuário.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections
from django.db import connection
from django.test import TransactionTestCase

from cadastros.models import ConfiguracaoSistema
from planos_trabalho.models import PlanoTrabalho
from usuarios.models import AreaTrabalho


@skipUnless(
    connection.vendor == "postgresql",
    "No SQLite a escrita é serializada pelo próprio banco: duas threads passariam por "
    "acidente, não por mérito do lock.",
)
class PlanoNumberingConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_duas_reservas_simultaneas_recebem_numeros_distintos(self):
        area = AreaTrabalho.objects.create(nome="Área PT concorrente", sigla="PTC")
        # O contador mora na configuração da área; sem a linha, as duas threads cairiam
        # no `get_for_area` e cada uma criaria a sua — o teste mediria a criação, não a
        # numeração.
        ConfiguracaoSistema.get_for_area(area)
        area_id = area.pk
        barrier = Barrier(2)

        def reservar():
            close_old_connections()
            try:
                area_local = AreaTrabalho.objects.get(pk=area_id)
                barrier.wait(timeout=5)
                numero, _ano, _sufixo = PlanoTrabalho.proximo_numero(area_local)
                return numero
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            numeros = list(executor.map(lambda _i: reservar(), range(2)))

        self.assertEqual(
            sorted(numeros),
            [1, 2],
            "duas reservas simultâneas devolveram o mesmo número de plano",
        )
