"""BE-03 — o filtro "criado de/até" da lista de ofícios precisa filtrar.

`listar_oficios` usava `data_criacao__date__gte`/`__date__lte`, mas
`Oficio.data_criacao` é `DateField` — o lookup `__date` só existe em
`DateTimeField`. O Django levanta `FieldError`, e dois `except Exception: pass`
engoliam o erro.

O usuário preenchia o intervalo, o sistema devolvia a lista inteira, e nada na
tela dizia que o filtro tinha sido descartado. Quem procurava os ofícios de um
mês recebia todos e concluía errado sobre o que existe.
"""

from __future__ import annotations

from datetime import date

from django.test import TestCase

from oficios.models import Oficio
from oficios.selectors import listar_oficios
from core.testing import area_de_teste
from core.testing import com_request


class FiltroDeDataDeCriacaoTests(TestCase):
    def setUp(self):
        # DB-02: selectors/forms/services recortam pela area do request;
        # chamada direta reproduz o contexto que a view teria.
        self.enterContext(com_request(area_de_teste()))
        self.antigo = Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026, data_criacao=date(2026, 1, 15))
        self.meio = Oficio.objects.create(area=area_de_teste(), numero=2, ano=2026, data_criacao=date(2026, 6, 10))
        self.recente = Oficio.objects.create(area=area_de_teste(), numero=3, ano=2026, data_criacao=date(2026, 11, 20))

    def _numeros(self, **kwargs):
        return sorted(listar_oficios(**kwargs).values_list("numero", flat=True))

    def test_filtro_de_inicio_recorta_de_verdade(self):
        self.assertEqual(self._numeros(criacao_de=date(2026, 6, 1)), [2, 3])

    def test_filtro_de_fim_recorta_de_verdade(self):
        self.assertEqual(self._numeros(criacao_ate=date(2026, 6, 30)), [1, 2])

    def test_intervalo_fechado_recorta_dos_dois_lados(self):
        self.assertEqual(
            self._numeros(criacao_de=date(2026, 6, 1), criacao_ate=date(2026, 6, 30)),
            [2],
        )

    def test_limites_do_intervalo_sao_inclusivos(self):
        self.assertEqual(
            self._numeros(criacao_de=date(2026, 6, 10), criacao_ate=date(2026, 6, 10)),
            [2],
        )

    def test_sem_filtro_devolve_todos(self):
        self.assertEqual(self._numeros(), [1, 2, 3])

    def test_aceita_a_string_iso_que_a_view_passa_do_querystring(self):
        """A view passa `request.GET` cru — o selector precisa aguentar string."""
        self.assertEqual(self._numeros(criacao_de="2026-06-01"), [2, 3])

    def test_texto_que_nao_e_data_nao_derruba_a_lista(self):
        """Sem o `except Exception` de volta: `?criacao_de=abc` ignora o filtro, não estoura."""
        self.assertEqual(self._numeros(criacao_de="abc"), [1, 2, 3])
