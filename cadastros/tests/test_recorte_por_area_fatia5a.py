"""BE-09, fatia 5a — os cinco modelos de cadastro básico.

`cadastros` é a maior fatia do ID: 129 chamadas fora de teste, contra ~50 das
anteriores. Mas o recorte em si é o de sempre — 60 dessas chamadas já passam por
`filter_queryset_by_area` sem área explícita, e para elas o manager é idempotente.

O que muda de figura são **cinco** consultas cujo escopo é o do próprio registro,
e duas delas falham do jeito mais caro: devolvendo **vazio**, sem erro.

`termos/models.py:_servidores_do_evento` monta o termo genérico a partir dos
servidores dos ofícios do evento; `termos/selectors.py` faz o `Prefetch` que o
`NOVO-08` criou para matar o N+1. Se qualquer um recortar pela área ativa, o termo
sai **sem servidores** e ninguém vê erro nenhum. E a geração documental roda em
worker, onde não há área ambiente — mas `CELERY_TASK_ALWAYS_EAGER` (`NOVO-20`) faz
a task rodar dentro do request nos testes, então esse caminho só é alcançável com
`sem_request()` explícito.

`cadastros/forms.py:clean_placa` é código do `DB-05` (#202): a área sai da
instância de propósito, para cobrir quem chama o form fora de request. Recortar de
novo desfaria aquele ID.
"""

from __future__ import annotations

from django.test import TestCase

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.tests.test_area_scoped_manager import com_request
from core.tests.test_area_scoped_manager import sem_request
from usuarios.models import AreaTrabalho


class RecorteChegaNosCincoModelosTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="C5-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="C5-B")

    def _par(self, criar):
        with sem_request():
            return criar(self.area), criar(self.outra)

    def _visiveis(self, modelo):
        with com_request(self.area):
            return set(modelo.objects.values_list("pk", flat=True))

    def test_unidade(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: Unidade.objects.create(area=area, nome=f"Unidade {next(contador)}"),
        )
        visiveis = self._visiveis(Unidade)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_cargo(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: Cargo.objects.create(area=area, nome=f"Cargo {next(contador)}"),
        )
        visiveis = self._visiveis(Cargo)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_combustivel(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: Combustivel.objects.create(area=area, nome=f"Comb {next(contador)}"),
        )
        visiveis = self._visiveis(Combustivel)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_servidor(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: Servidor.objects.create(area=area, nome=f"Servidor {next(contador)}"),
        )
        visiveis = self._visiveis(Servidor)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_viatura(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: Viatura.objects.create(area=area, placa=f"ABC{next(contador):04d}"),
        )
        visiveis = self._visiveis(Viatura)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_os_cinco_declaram_o_par_de_managers(self):
        for modelo in (Unidade, Cargo, Combustivel, Servidor, Viatura):
            with self.subTest(modelo=modelo.__name__):
                self.assertIs(modelo._default_manager, modelo.all_objects)
                self.assertEqual(modelo._meta.default_manager_name, "all_objects")


class PadraoUnicoPorAreaTests(TestCase):
    """`Cargo.save()` e `Combustivel.save()` rebaixam o padrão anterior da **área
    do registro**, que já vem no filtro. Recortado pela ativa, o antigo sobrevive
    e a gravação estoura em `cadastros_*_area_padrao_unique`."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="PAD-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="PAD-B")

    def test_cargo(self):
        with sem_request():
            antigo = Cargo.objects.create(area=self.outra, nome="Antigo", is_padrao=True)

        with com_request(self.area):
            Cargo.all_objects.create(area=self.outra, nome="Novo", is_padrao=True)

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao, msg="o padrão anterior da outra área não foi rebaixado")

    def test_combustivel(self):
        with sem_request():
            antigo = Combustivel.objects.create(area=self.outra, nome="Antigo", is_padrao=True)

        with com_request(self.area):
            Combustivel.all_objects.create(area=self.outra, nome="Novo", is_padrao=True)

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao)


class ChecagemDePlacaNaoPodeSerRecortadaTests(TestCase):
    """`DB-05` (#202) de novo, pelo outro lado."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="PLC-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="PLC-B")

    def test_o_form_recusa_placa_ja_usada_na_area_da_instancia(self):
        """Editando uma viatura de outra área, o form tem de continuar vendo as
        placas daquela área. Recortado, ele aceitaria a duplicata e o erro só
        apareceria como `IntegrityError` no INSERT."""
        from cadastros.forms import ViaturaForm

        with sem_request():
            Viatura.objects.create(area=self.outra, placa="XYZ9A99")
            editada = Viatura.objects.create(area=self.outra, placa="QRS1B22")

        with com_request(self.area):
            form = ViaturaForm(instance=editada)
            form.cleaned_data = {"placa": "XYZ9A99"}
            with self.assertRaises(Exception) as capturado:
                form.clean_placa()

        self.assertIn("placa", str(capturado.exception).lower())


class TermoNaoPerdeServidoresTests(TestCase):
    """As duas consultas que falham **vazias**, não com erro.

    Ambas alimentam a geração do termo, que roda em worker. Sem `sem_request()`
    estes testes passariam mesmo com o recorte errado, porque
    `CELERY_TASK_ALWAYS_EAGER` põe a task dentro do request (`NOVO-20`).
    """

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="TRM-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="TRM-B")

    def test_o_termo_generico_do_evento_mantem_os_servidores(self):
        from eventos.models import Evento
        from oficios.models import Oficio
        from termos.models import TermoAutorizacao

        with sem_request():
            evento = Evento.objects.create(area=self.outra, titulo="Evento")
            oficio = Oficio.objects.create(area=self.outra, evento=evento, numero=1, ano=2026)
            servidor = Servidor.objects.create(area=self.outra, nome="Fulano")
            oficio.servidores.add(servidor)
            termo = TermoAutorizacao.objects.create(area=self.outra, evento=evento)

        with com_request(self.area):
            encontrados = termo.servidores_efetivos()

        self.assertEqual(
            [s.pk for s in encontrados],
            [servidor.pk],
            msg="o termo genérico saiu sem servidores",
        )

    def test_o_prefetch_da_lista_mantem_os_servidores(self):
        from termos.models import TermoAutorizacao
        from termos.selectors import prefetch_servidores_efetivos

        with sem_request():
            servidor = Servidor.objects.create(area=self.outra, nome="Beltrano")
            termo = TermoAutorizacao.objects.create(area=self.outra)
            termo.servidores.add(servidor)

        with com_request(self.area):
            carregado = (
                TermoAutorizacao.all_objects.filter(pk=termo.pk)
                .prefetch_related(prefetch_servidores_efetivos())
                .first()
            )
            encontrados = [s.pk for s in carregado.servidores.all()]

        self.assertEqual(encontrados, [servidor.pk], msg="o prefetch veio vazio")
