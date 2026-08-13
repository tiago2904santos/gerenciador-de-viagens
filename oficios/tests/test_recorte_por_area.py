"""BE-09, fatia 2 — os quatro modelos de `oficios` passam a recortar sozinhos.

Duas classes, e elas testam coisas opostas.

`RecorteChegaNosQuatroModelosTests` é o gate de `docs/PLANO_BACKEND.md:87`: um
teste de duas áreas por modelo migrado, **sem** `filter_queryset_by_area` na
chamada — é o manager fazendo o trabalho.

`NumeracaoNaoPodeSerRecortadaTests` é o contrário: prova que os onze sites que
passaram a usar `all_objects` **precisam** dele. Todos têm a mesma forma — o
escopo é o da área do próprio registro, que já vem explícita no filtro, e não o
da área ativa do request. Recortar de novo esvazia a consulta sempre que as duas
divergirem, e o estrago é silencioso: número reiniciado, conflito não detectado,
lacuna que sobrevive ao uso.

O caso mais caro é o piso global (`oficios/models.py:get_next_available_numero`):
`ConfiguracaoNumeracaoOficio` com `area IS NULL` é o padrão que serve a quem não
tem configuração própria, e a consulta busca a união dele com a da área **de
propósito**. Sob `objects`, `area=A AND (area=A OR area IS NULL)` colapsa em
`area=A`, a linha global some e `piso` cai para 1.
"""

from __future__ import annotations

from django.conf import settings
from django.test import TestCase

from cadastros.models import Combustivel
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.testing import com_request
from core.testing import sem_request
from oficios.forms import OficioDadosViajantesForm
from oficios.forms import OficioForm
from oficios.forms import OficioTransporteForm
from oficios.models import ConfiguracaoNumeracaoOficio
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from oficios.models import OficioNumeroLacuna
from roteiros.models import Roteiro
from usuarios.models import AreaTrabalho


class RecorteChegaNosQuatroModelosTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="OFC-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="OFC-B")

    def _par(self, criar):
        with sem_request():
            return criar(self.area), criar(self.outra)

    def _visiveis(self, modelo):
        with com_request(self.area):
            return set(modelo.objects.values_list("pk", flat=True))

    def test_oficio(self):
        meu, alheio = self._par(
            lambda area: Oficio.objects.create(numero=1, ano=2026, area=area, assunto="X"),
        )
        visiveis = self._visiveis(Oficio)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_configuracao_numeracao(self):
        meu, alheio = self._par(
            lambda area: ConfiguracaoNumeracaoOficio.objects.create(
                area=area, ano=2026, numero_inicial=10,
            ),
        )
        visiveis = self._visiveis(ConfiguracaoNumeracaoOficio)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_numero_lacuna(self):
        meu, alheio = self._par(
            lambda area: OficioNumeroLacuna.objects.create(area=area, ano=2026, numero=7),
        )
        visiveis = self._visiveis(OficioNumeroLacuna)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_modelo_motivo(self):
        contador = iter(range(100))
        meu, alheio = self._par(
            lambda area: ModeloMotivoOficio.objects.create(
                area=area, nome=f"Motivo {next(contador)}", texto="…",
            ),
        )
        visiveis = self._visiveis(ModeloMotivoOficio)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_os_quatro_declaram_o_par_de_managers(self):
        for modelo in (Oficio, ConfiguracaoNumeracaoOficio, OficioNumeroLacuna, ModeloMotivoOficio):
            with self.subTest(modelo=modelo.__name__):
                self.assertIs(modelo._default_manager, modelo.all_objects)
                self.assertEqual(modelo._meta.default_manager_name, "all_objects")


class ModelFormsRecortamRelacoesTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área Form A", sigla="FRM-A")
        self.outra = AreaTrabalho.objects.create(nome="Área Form B", sigla="FRM-B")
        with sem_request():
            for area, sufixo in ((self.area, "A"), (self.outra, "B")):
                Unidade.objects.create(area=area, nome=f"Unidade {sufixo}")
                Combustivel.objects.create(area=area, nome=f"Combustível {sufixo}")
                Servidor.objects.create(area=area, nome=f"Servidor {sufixo}")
                Viatura.objects.create(area=area, placa=f"ABC000{sufixo}")
                Roteiro.objects.create(area=area)

    def assert_so_area_ativa(self, field):
        self.assertEqual(
            set(field.queryset.values_list("area_id", flat=True)),
            {self.area.pk},
        )

    def test_oficio_form_recorta_as_seis_relacoes(self):
        with com_request(self.area):
            form = OficioForm()

        for nome in (
            "roteiro",
            "solicitante",
            "servidores",
            "servidores_termo_autorizacao",
            "viatura",
            "motorista",
        ):
            with self.subTest(campo=nome):
                self.assert_so_area_ativa(form.fields[nome])

    def test_forms_do_wizard_recortam_relacoes_herdadas_e_transporte(self):
        with com_request(self.area):
            dados = OficioDadosViajantesForm()
            transporte = OficioTransporteForm()

        for form, nomes in (
            (dados, ("servidores", "servidores_termo_autorizacao", "viatura")),
            (transporte, ("viatura", "motorista", "transporte_combustivel_manual")),
        ):
            for nome in nomes:
                with self.subTest(form=form.__class__.__name__, campo=nome):
                    self.assert_so_area_ativa(form.fields[nome])


class NumeracaoNaoPodeSerRecortadaTests(TestCase):
    """Os onze sites de `all_objects`, um teste por consequência.

    Cinco em `oficios/models.py`, cinco em `oficios/services.py`, um em
    `oficios/forms.py`. Os dois de `services.py` que desmarcam o modelo de motivo
    padrão duplicam o que `ModeloMotivoOficio.save()` já faz, e o teste do `save()`
    cobre os três; o do lock de numeração só roda no fallback de banco sem
    advisory lock e está coberto pelos testes de numeração concorrente que já
    existiam.
    """

    #: `oficios/migrations/0017` semeia o piso global de **2026** com
    #: `numero_inicial=75`. Criar outro global para 2026 aqui estouraria
    #: `oficios_numeracao_global_ano_unique`, e afirmar sobre 2026 mediria o seed.
    #: O ano do seed tem teste próprio, no fim desta classe.
    ANO = 2027

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="NUM-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="NUM-B")

    def test_suite_exerce_a_mesma_configuracao_de_producao(self):
        self.assertTrue(settings.OFICIO_NUMERACAO_USAR_CONFIGURACAO)

    # ── o piso global: o site mais perigoso do ID ──

    def test_o_piso_global_sobrevive_ao_recorte(self):
        """`ConfiguracaoNumeracaoOficio` com `area IS NULL` é o padrão de todos.

        Com `objects`, a união `Q(area=area) | Q(area__isnull=True)` colapsa em
        `area=A` dentro de um request, a linha global some e o próximo número
        volta a 1 — numeração de documento oficial reiniciando em silêncio.
        """
        with sem_request():
            ConfiguracaoNumeracaoOficio.objects.create(area=None, ano=self.ANO, numero_inicial=500)

        with com_request(self.area):
            proximo = Oficio.get_next_available_numero(ano=self.ANO, area=self.area)

        self.assertEqual(
            proximo,
            500,
            msg="o piso global sumiu e a numeração reiniciou",
        )

    def test_o_piso_da_propria_area_continua_ganhando_do_global(self):
        """O recorte não pode ter atropelado a precedência que já existia:
        `order_by(F("area_id").desc(nulls_last=True))` põe a área na frente."""
        with sem_request():
            ConfiguracaoNumeracaoOficio.objects.create(area=None, ano=self.ANO, numero_inicial=500)
            ConfiguracaoNumeracaoOficio.objects.create(area=self.area, ano=self.ANO, numero_inicial=800)

        with com_request(self.area):
            proximo = Oficio.get_next_available_numero(ano=self.ANO, area=self.area)

        self.assertEqual(proximo, 800)

    def test_a_numeracao_enxerga_os_numeros_ja_usados_da_area_pedida(self):
        """`cls.all_objects.filter(ano=...)` seguido do recorte por `area`.

        Pedir o próximo número de uma área **diferente** da ativa é o caso que
        `objects` esvaziaria — e o número devolvido colidiria com o que já existe.
        """
        with sem_request():
            Oficio.objects.create(numero=41, ano=self.ANO, area=self.outra, assunto="X")

        with com_request(self.area):
            proximo = Oficio.get_next_available_numero(ano=self.ANO, area=self.outra)

        self.assertEqual(proximo, 42, msg="a numeração não viu o 41 já usado na outra área")

    def test_a_lacuna_da_area_pedida_e_reaproveitada(self):
        """`OficioNumeroLacuna.all_objects` — mesma forma, outro modelo."""
        with sem_request():
            Oficio.objects.create(numero=41, ano=self.ANO, area=self.outra, assunto="X")
            OficioNumeroLacuna.objects.create(area=self.outra, ano=self.ANO, numero=12)

        with com_request(self.area):
            proximo = Oficio.get_next_available_numero(ano=self.ANO, area=self.outra)

        self.assertEqual(proximo, 12, msg="a lacuna da outra área não foi reaproveitada")

    # ── a lacuna consumida some ──

    def test_salvar_oficio_consome_a_lacuna_da_propria_area(self):
        """`Oficio.save()` apaga a lacuna que o número acabou de ocupar.

        Recortada pela área ativa, a lacuna sobreviveria e o mesmo número voltaria
        a ser oferecido como disponível estando em uso.
        """
        with sem_request():
            OficioNumeroLacuna.objects.create(area=self.outra, ano=self.ANO, numero=12)

        with com_request(self.area):
            Oficio.all_objects.create(numero=12, ano=self.ANO, area=self.outra, assunto="X")

        self.assertFalse(
            OficioNumeroLacuna.all_objects.filter(area=self.outra, numero=12).exists(),
            msg="a lacuna sobreviveu ao número ter sido ocupado",
        )

    # ── o padrão único por área ──

    def test_marcar_padrao_desmarca_o_anterior_da_mesma_area(self):
        """`ModeloMotivoOficio.save()` — com `objects`, o padrão antigo de uma área
        diferente da ativa sobreviveria e a gravação estouraria em
        `oficios_motivo_area_padrao_unique`."""
        with sem_request():
            antigo = ModeloMotivoOficio.objects.create(
                area=self.outra, nome="Antigo", texto="…", is_padrao=True,
            )

        with com_request(self.area):
            ModeloMotivoOficio.all_objects.create(
                area=self.outra, nome="Novo", texto="…", is_padrao=True,
            )

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao, msg="o padrão anterior da outra área não foi desmarcado")

    # ── os sites de `services.py` e `forms.py` ──

    def test_excluir_oficio_registra_a_lacuna_na_area_do_oficio(self):
        """`excluir_oficio` faz `get_or_create(area=area, ...)` com a área explícita.

        Com `objects` e área diferente da ativa, o `get` não acharia uma lacuna
        existente e o `create` estouraria em
        `oficios_lacuna_area_ano_numero_unique`.
        """
        from oficios.services import excluir_oficio

        with sem_request():
            oficio = Oficio.objects.create(numero=33, ano=self.ANO, area=self.outra, assunto="X")
            # A lacuna **já existe**: é isso que obriga o `get` a encontrá-la. Sem
            # ela o teste passaria com `objects` também — o `get` viria vazio, o
            # `create` funcionaria, e nada denunciaria o recorte.
            #
            # E ela vem **depois** do ofício de propósito: `Oficio.save()` apaga a
            # lacuna do número que acabou de ocupar, então criá-la antes seria o
            # mesmo que não criá-la.
            OficioNumeroLacuna.objects.create(area=self.outra, ano=self.ANO, numero=33)

        with com_request(self.area):
            excluir_oficio(oficio)

        self.assertEqual(
            OficioNumeroLacuna.all_objects.filter(
                area=self.outra, ano=self.ANO, numero=33,
            ).count(),
            1,
            msg="o `get_or_create` não achou a lacuna existente e duplicou",
        )

    def test_o_formulario_recusa_numero_ja_usado_na_area_do_oficio(self):
        """`OficioDadosViajantesForm.clean_numero` monta o conflito com o escopo da
        instância. Recortado pela área ativa, o formulário aceitaria um número
        duplicado e o erro só apareceria como `IntegrityError` no INSERT."""
        from oficios.forms import OficioDadosViajantesForm

        with sem_request():
            Oficio.objects.create(numero=55, ano=self.ANO, area=self.outra, assunto="Existente")
            editado = Oficio.objects.create(area=self.outra, ano=self.ANO, assunto="Em edição")

        with com_request(self.area):
            form = OficioDadosViajantesForm(instance=editado)
            form.cleaned_data = {"numero": 55}
            with self.assertRaises(Exception) as capturado:
                form.clean_numero()

        self.assertIn("55", str(capturado.exception))

    # ── o piso global que existe de verdade em produção ──

    def test_o_piso_global_semeado_pela_migracao_continua_valendo(self):
        """A versão mais forte do primeiro teste: o dado é o de produção.

        `oficios/migrations/0017` cria `(area=None, ano=2026, numero_inicial=75)`.
        Nenhuma área tem configuração própria hoje, então **todo** ofício de 2026
        depende dessa linha. Sob `objects`, ela sumiria dentro de qualquer request
        com área e a numeração de 2026 recomeçaria em 1 — em cima de números já
        emitidos.
        """
        with com_request(self.area):
            proximo = Oficio.get_next_available_numero(ano=2026, area=self.area)

        self.assertEqual(proximo, 75, msg="o piso global de produção sumiu")
