"""`BE-15` — a numeração da Ordem de Serviço sob concorrência real.

Rede escrita **antes** de qualquer mudança, como o catálogo exige. Ela existe para travar
o que hoje já funciona: `OrdemServico.save()` serializa a escolha do próximo número com
`pg_advisory_xact_lock` e se recupera de uma colisão com até três tentativas.

O molde é `oficios/tests/test_numbering_concurrency.py` — mesmo `TransactionTestCase`,
mesma `Barrier(2)`, mesmo `skipUnless` de PostgreSQL. O advisory lock não existe no
SQLite; lá vale o `select_for_update` de fallback, exercitado pelo resto da suíte.

Duas threads, um número cada: é a única prova que vale para numeração de documento
oficial, porque o defeito só aparece quando duas pessoas clicam "nova OS" no mesmo
segundo — e aí o dano é irreversível, já que o número foi impresso.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Lock
from unittest import mock
from unittest import skipUnless

from django.db import close_old_connections
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from ordens_servico.models import OrdemServico
from usuarios.models import AreaTrabalho


@skipUnless(
    connection.vendor == "postgresql",
    "O advisory lock de produção é específico do PostgreSQL.",
)
class OrdemServicoNumberingConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_duas_criacoes_simultaneas_recebem_numeros_distintos(self):
        area = AreaTrabalho.objects.create(nome="Área OS concorrente", sigla="OSC")
        area_id = area.pk
        barrier = Barrier(2)

        def criar():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                ordem = OrdemServico(
                    area_id=area_id,
                    data_evento_inicio=timezone.localdate(),
                    data_evento_fim=timezone.localdate(),
                )
                ordem.save()
                return ordem.numero
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            numeros = list(executor.map(lambda _i: criar(), range(2)))

        self.assertEqual(sorted(numeros), [1, 2])
        self.assertEqual(
            OrdemServico.objects.filter(
                area_id=area_id,
                ano=timezone.localdate().year,
                numero__in=numeros,
            ).count(),
            2,
        )

    def test_o_lock_evita_a_colisao_em_vez_de_apenas_se_recuperar_dela(self):
        """A garantia **do lock**, separada da garantia do retry.

        O teste acima não mede o lock: sem ele, as duas threads escolhem o mesmo número,
        uma colide, o retry escolhe outro, e o resultado final continua sendo `[1, 2]`.
        Medido — removendo o advisory lock, aquele teste **passa**. Ele prova
        "lock **ou** retry", que é bem menos do que se quer.

        O que separa os dois é a **contagem de escolhas**: com o escopo serializado, cada
        thread escolhe uma vez só. Toda escolha além do número de threads é uma colisão que
        aconteceu — e uma colisão que o retry teve de limpar é justamente o que o lock
        existe para evitar.
        """
        area = AreaTrabalho.objects.create(nome="Área OS lock", sigla="OSL")
        area_id = area.pk
        barrier = Barrier(2)
        escolhas = []
        trava = Lock()
        original = OrdemServico._assign_numero

        def contando(self_os):
            with trava:
                escolhas.append(1)
            return original(self_os)

        def criar():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                ordem = OrdemServico(
                    area_id=area_id,
                    data_evento_inicio=timezone.localdate(),
                    data_evento_fim=timezone.localdate(),
                )
                ordem.save()
                return ordem.numero
            finally:
                close_old_connections()

        with mock.patch.object(OrdemServico, "_assign_numero", contando):
            with ThreadPoolExecutor(max_workers=2) as executor:
                numeros = list(executor.map(lambda _i: criar(), range(2)))

        self.assertEqual(sorted(numeros), [1, 2])
        self.assertEqual(
            len(escolhas),
            2,
            "houve mais escolhas do que threads: as duas disputaram o mesmo número e só "
            "o retry salvou — o lock não serializou o escopo",
        )
