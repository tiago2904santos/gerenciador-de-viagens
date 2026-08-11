"""BE-09, fatia 3 — `roteiros` e `eventos` passam a recortar sozinhos.

Três classes, e a do meio é a que justifica esta fatia existir.

`RecorteChegaNosQuatroModelosTests` é o gate de `docs/PLANO_BACKEND.md:87`.

`VazamentosQueOManagerFechaTests` cobre **defeitos reais**, não refatoração:
três consultas de `Roteiro` não tinham recorte nenhum e passavam a enxergar o
banco inteiro. Nenhuma delas está no catálogo — apareceram na varredura desta
fatia, e o manager as fecha sem uma linha de correção própria. É exatamente o
que o `BE-09` prometia: esquecer o filtro deixa de ser vazamento.

`EscopoExplicitoNaoPodeSerRecortadoTests` é o contrário — os seis sites que
passaram a `all_objects` porque o escopo é o do próprio registro. O mais sério é
`_limpar_rascunhos_vazios`, que é um **DELETE**: recortá-lo pela área ativa o
tornaria inerte, e a função voltaria a não varrer o órfão que existe para varrer
(o `DB-03` de novo, pelo outro lado).
"""

from __future__ import annotations

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from core.tests.test_area_scoped_manager import com_request
from core.tests.test_area_scoped_manager import sem_request
from eventos.models import Evento
from eventos.models import ModeloMotivoEvento
from eventos.models import TipoEvento
from oficios.models import Oficio
from roteiros.models import Roteiro
from usuarios.models import AreaTrabalho


class RecorteChegaNosQuatroModelosTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="RE3-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="RE3-B")

    def _par(self, criar):
        with sem_request():
            return criar(self.area), criar(self.outra)

    def _visiveis(self, modelo):
        with com_request(self.area):
            return set(modelo.objects.values_list("pk", flat=True))

    def test_roteiro(self):
        meu, alheio = self._par(lambda area: Roteiro.objects.create(area=area))
        visiveis = self._visiveis(Roteiro)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_evento(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: Evento.objects.create(area=area, titulo=f"Evento {next(contador)}"),
        )
        visiveis = self._visiveis(Evento)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_tipo_evento(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: TipoEvento.objects.create(area=area, nome=f"Tipo {next(contador)}"),
        )
        visiveis = self._visiveis(TipoEvento)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_modelo_motivo_evento(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: ModeloMotivoEvento.objects.create(
                area=area, nome=f"Motivo {next(contador)}", texto="…",
            ),
        )
        visiveis = self._visiveis(ModeloMotivoEvento)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_os_quatro_declaram_o_par_de_managers(self):
        for modelo in (Roteiro, Evento, TipoEvento, ModeloMotivoEvento):
            with self.subTest(modelo=modelo.__name__):
                self.assertIs(modelo._default_manager, modelo.all_objects)
                self.assertEqual(modelo._meta.default_manager_name, "all_objects")


class VazamentosQueOManagerFechaTests(TestCase):
    """Três consultas de `Roteiro` que enxergavam o banco inteiro."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="VAZ-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="VAZ-B")
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.sede = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")
        self.destino = Cidade.objects.create(nome="Londrina", estado=self.estado, uf="PR")

    def test_o_picker_de_roteiros_salvos_nao_lista_os_de_outra_area(self):
        """`roteiros/services/editor_state_builder.py:_get_roteiro_saved_routes` filtrava só por
        status. O ofício de uma área via os roteiros finalizados de todas."""
        from roteiros.services.editor_state_builder import _get_roteiro_saved_routes

        with sem_request():
            meu = Roteiro.objects.create(area=self.area, status=Roteiro.STATUS_FINALIZADO)
            alheio = Roteiro.objects.create(area=self.outra, status=Roteiro.STATUS_FINALIZADO)
            oficio = Oficio.objects.create(area=self.area, numero=1, ano=2026, assunto="X")

        with com_request(self.area):
            encontrados = {r.pk for r in _get_roteiro_saved_routes(oficio)}

        self.assertIn(meu.pk, encontrados)
        self.assertNotIn(alheio.pk, encontrados, msg="o picker ofereceu roteiro de outra área")

    def test_o_roteiro_submetido_de_outra_area_nao_e_aceito(self):
        """`editor_state_builder._build_roteiro_state_from_post` validava o id sem recorte: bastava
        submeter o pk de um roteiro alheio para ele ser aceito."""
        from roteiros.services.editor_state_builder import Roteiro as RoteiroNoLogic

        with sem_request():
            alheio = Roteiro.objects.create(area=self.outra)

        with com_request(self.area):
            encontrado = RoteiroNoLogic.objects.filter(pk=alheio.pk).first()

        self.assertIsNone(encontrado, msg="o roteiro de outra área foi aceito pelo pk submetido")

    def test_a_deteccao_de_duplicado_nao_oferece_roteiro_de_outra_area(self):
        """`encontrar_roteiro_duplicado` filtrava só por sede e destinos.

        O estrago não seria só ver: a tela usa o retorno para oferecer
        **sobrescrever** aquele roteiro.
        """
        from roteiros.models import RoteiroDestino
        from roteiros.services.roteiro_editor import encontrar_roteiro_duplicado

        with sem_request():
            alheio = Roteiro.objects.create(area=self.outra, origem_cidade=self.sede)
            RoteiroDestino.objects.create(
                roteiro=alheio, cidade=self.destino, estado=self.estado, ordem=1,
            )

        estado_atual = {"destinos_atuais": [{"cidade_id": self.destino.pk}]}
        with com_request(self.area):
            duplicado = encontrar_roteiro_duplicado({"sede_cidade": self.sede}, estado_atual)

        self.assertIsNone(duplicado, msg="ofereceu sobrescrever o roteiro de outra área")

    def test_a_deteccao_de_duplicado_continua_achando_o_da_propria_area(self):
        """O recorte não pode ter desligado a função."""
        from roteiros.models import RoteiroDestino
        from roteiros.services.roteiro_editor import encontrar_roteiro_duplicado

        with sem_request():
            meu = Roteiro.objects.create(area=self.area, origem_cidade=self.sede)
            RoteiroDestino.objects.create(
                roteiro=meu, cidade=self.destino, estado=self.estado, ordem=1,
            )

        estado_atual = {"destinos_atuais": [{"cidade_id": self.destino.pk}]}
        with com_request(self.area):
            duplicado = encontrar_roteiro_duplicado({"sede_cidade": self.sede}, estado_atual)

        self.assertEqual(duplicado, meu)


class EscopoExplicitoNaoPodeSerRecortadoTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="EXP-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="EXP-B")

    def test_a_limpeza_de_rascunhos_continua_varrendo_a_area_do_roteiro(self):
        """`_limpar_rascunhos_vazios` é um DELETE escopado pela área do roteiro
        que está sendo salvo — não pela ativa. Recortado, ficaria inerte e o
        `DB-03` voltaria pelo outro lado: a função pararia de varrer.
        """
        from datetime import timedelta

        from django.utils import timezone

        from roteiros.services.roteiro_editor import IDADE_MINIMA_RASCUNHO_ORFAO
        from roteiros.services.roteiro_editor import _limpar_rascunhos_vazios

        with sem_request():
            orfao = Roteiro.objects.create(area=self.outra)
            Roteiro.all_objects.filter(pk=orfao.pk).update(
                created_at=timezone.now() - IDADE_MINIMA_RASCUNHO_ORFAO - timedelta(minutes=1),
            )
            atual = Roteiro.objects.create(area=self.outra)

        with com_request(self.area):
            _limpar_rascunhos_vazios(atual)

        self.assertFalse(
            Roteiro.all_objects.filter(pk=orfao.pk).exists(),
            msg="a limpeza ficou inerte quando a área do roteiro difere da ativa",
        )

    def test_a_releitura_do_roteiro_recem_salvo_nao_levanta_does_not_exist(self):
        """`route_stale.py` relê o roteiro pelo pk logo depois de salvá-lo. Um
        `.get()` recortado seria `DoesNotExist` — 500, não resultado vazio."""
        with sem_request():
            roteiro = Roteiro.objects.create(area=self.outra)

        with com_request(self.area):
            # O contraste é a afirmação: `objects` levantaria, `all_objects` não.
            with self.assertRaises(Roteiro.DoesNotExist):
                Roteiro.objects.get(pk=roteiro.pk)
            relido = Roteiro.all_objects.get(pk=roteiro.pk)

        self.assertEqual(relido.pk, roteiro.pk)

    def test_marcar_padrao_desmarca_o_anterior_da_area_do_modelo(self):
        with sem_request():
            antigo = ModeloMotivoEvento.objects.create(
                area=self.outra, nome="Antigo", texto="…", is_padrao=True,
            )

        with com_request(self.area):
            ModeloMotivoEvento.all_objects.create(
                area=self.outra, nome="Novo", texto="…", is_padrao=True,
            )

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao, msg="o padrão anterior da outra área não foi desmarcado")
