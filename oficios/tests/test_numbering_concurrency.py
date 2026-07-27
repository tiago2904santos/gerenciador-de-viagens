from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from oficios.models import Oficio
from oficios.services import reservar_numero_oficio
from usuarios.models import AreaTrabalho


@skipUnless(
    connection.vendor == "postgresql",
    "O advisory lock de produção é específico do PostgreSQL.",
)
class OficioNumberingConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_duas_criacoes_simultaneas_recebem_numeros_distintos(self):
        area = AreaTrabalho.objects.create(nome="Área concorrente", sigla="CONC")
        area_id = area.pk
        barrier = Barrier(2)

        def create_draft():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                oficio = Oficio(
                    area_id=area_id,
                    data_criacao=timezone.localdate(),
                    status=Oficio.STATUS_RASCUNHO,
                    custeio=Oficio.CUSTEIO_UNIDADE_DPC,
                )
                oficio = reservar_numero_oficio(oficio)
                return oficio.numero
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            numeros = list(executor.map(lambda _index: create_draft(), range(2)))

        self.assertEqual(sorted(numeros), [1, 2])
        self.assertEqual(
            Oficio.objects.filter(
                area_id=area_id,
                ano=timezone.localdate().year,
                numero__in=numeros,
            ).count(),
            2,
        )
