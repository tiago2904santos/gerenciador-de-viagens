"""BE-09 — o contrato do `AreaScopedManager`.

Este arquivo não testa uma tela. Testa o mecanismo que as fatias seguintes vão
aplicar em mais 26 modelos, e por isso ele existe antes de qualquer um deles.

**A parte que a suíte não alcançaria sozinha:** `config/settings/test.py:64` liga
`CELERY_TASK_ALWAYS_EAGER = True`. Nos testes, a tarefa do Celery roda *dentro* do
request, com `core.middleware._local.request` populado — exatamente o contexto que
o worker de produção **não** tem. Um manager que recortasse fora de request faria
`gerar_pdf_oficio_cache` virar no-op silencioso em produção com a suíte verde. Daí
o `sem_request()`: é o único jeito de escrever o teste que pega isso.
"""

from __future__ import annotations

import contextlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django.test import RequestFactory
from django.test import TestCase

from core import middleware
from core.managers import AreaScopedManager
from core.tenancy import filter_queryset_by_area
from ordens_servico.models import OrdemServico
from termos.models import TermoAutorizacao
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


@contextlib.contextmanager
def sem_request():
    """Simula worker, comando ou shell: thread-local vazio.

    `CurrentRequestMiddleware` limpa `_local.request` num `finally`
    (`core/middleware.py:55`), então em teste normal já costuma estar vazio — mas
    depender disso torna o teste refém da ordem de execução. Aqui é explícito.
    """
    anterior = getattr(middleware._local, "request", None)
    middleware._local.request = None
    try:
        yield
    finally:
        middleware._local.request = anterior


@contextlib.contextmanager
def com_request(area):
    """Simula o ciclo de request com uma área ativa (ou `None`)."""
    anterior = getattr(middleware._local, "request", None)
    request = RequestFactory().get("/")
    request.area = area
    request.vinculo_area = None
    middleware._local.request = request
    try:
        yield request
    finally:
        middleware._local.request = anterior


class ContratoDoAreaScopedManagerTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="MGR-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="MGR-B")
        with sem_request():
            self.meu = TermoAutorizacao.objects.create(area=self.area)
            self.alheio = TermoAutorizacao.objects.create(area=self.outra)
            self.legado = TermoAutorizacao.objects.create(area=None)

    def _pks(self, queryset):
        return set(queryset.values_list("pk", flat=True))

    # ── o interruptor é a request, não a área ──

    def test_sem_request_objects_nao_recorta(self):
        """O teste que impede a regressão mais cara deste ID.

        Worker do Celery, comando de management, shell e script rodam aqui. Se
        `objects` recortasse, `documentos/tasks.py:33` devolveria `None` e a
        geração de PDF viraria no-op — sem log, sem retry e sem teste vermelho.
        """
        with sem_request():
            encontrados = self._pks(TermoAutorizacao.objects.all())

        self.assertEqual(encontrados, {self.meu.pk, self.alheio.pk, self.legado.pk})

    def test_com_request_na_area_a_objects_devolve_so_a(self):
        with com_request(self.area):
            encontrados = self._pks(TermoAutorizacao.objects.all())

        self.assertEqual(encontrados, {self.meu.pk})

    def test_com_request_sem_area_devolve_o_balde_legado(self):
        """Comportamento de hoje preservado à letra.

        `core/tenancy.py:70-71` devolve `area IS NULL` quando não há área ativa, e
        `usuarios/tests/test_area_legado_compat.py` depende disso. Mudar aqui seria
        antecipar o `DB-02` sem a migração que ele exige.
        """
        with com_request(None):
            encontrados = self._pks(TermoAutorizacao.objects.all())

        self.assertEqual(encontrados, {self.legado.pk})

    def test_all_objects_devolve_tudo_nos_tres_casos(self):
        esperado = {self.meu.pk, self.alheio.pk, self.legado.pk}

        with sem_request():
            self.assertEqual(self._pks(TermoAutorizacao.all_objects.all()), esperado)
        with com_request(self.area):
            self.assertEqual(self._pks(TermoAutorizacao.all_objects.all()), esperado)
        with com_request(None):
            self.assertEqual(self._pks(TermoAutorizacao.all_objects.all()), esperado)

    # ── o que o Django resolve sozinho continua irrestrito ──

    def test_default_manager_e_o_irrestrito(self):
        """Daqui saem admin, campos de FK auto-gerados, `validate_unique`,
        `UniqueConstraint.validate`, `dumpdata` e as relações reversas."""
        for modelo in (TermoAutorizacao, OrdemServico):
            with self.subTest(modelo=modelo.__name__):
                self.assertIs(modelo._default_manager, modelo.all_objects)
                self.assertNotIsInstance(modelo._base_manager, AreaScopedManager)

    def test_travessia_de_fk_atravessa_area(self):
        """`ForwardManyToOneDescriptor` usa `_base_manager`
        (`db/models/fields/related_descriptors.py:161`)."""
        with com_request(self.area):
            termo = TermoAutorizacao.all_objects.get(pk=self.alheio.pk)

            self.assertEqual(termo.area, self.outra)

    def test_relacao_reversa_nao_recorta(self):
        """Deriva de `_default_manager.__class__`
        (`db/models/fields/related_descriptors.py:642`), que aqui é o irrestrito."""
        with com_request(self.area):
            encontrados = self._pks(self.outra.termos_autorizacao.all())

        self.assertEqual(encontrados, {self.alheio.pk})

    def test_admin_continua_enxergando_todas_as_areas(self):
        """O admin é a ferramenta de emergência; recortá-lo o deixaria vazio para
        superusuário sem vínculo. `ModelAdmin.get_queryset` usa `_default_manager`
        (`contrib/admin/options.py:437`), que aqui é o irrestrito."""
        from django.contrib import admin

        with com_request(self.area) as request:
            request.user = get_user_model().objects.create_superuser(
                username="admin_be09", email="a@b.gov.br", password="x" * 24,
            )
            visiveis = admin.site._registry[TermoAutorizacao].get_queryset(request).count()

        self.assertEqual(visiveis, 3)

    def test_modelo_historico_de_migracao_vem_com_manager_puro(self):
        """`use_in_migrations = False` faz `db/migrations/state.py:905` trocar o
        manager por um shim limpo. Sem isso, toda `RunPython` recortaria."""
        historico = apps.get_model("termos", "TermoAutorizacao")

        self.assertFalse(AreaScopedManager.use_in_migrations)
        self.assertIsNotNone(historico)

    # ── os ~140 filtros explícitos não podem ter mudado de comportamento ──

    def test_filtro_explicito_continua_dando_o_mesmo_resultado(self):
        """`filter_queryset_by_area(Model.objects.all())` aparece em ~140 sites.
        Dentro de request filtra duas vezes pela mesma área; fora, o manager não faz
        nada e o filtro explícito continua devolvendo o balde legado. Idêntico ao
        que fazia antes deste ID."""
        casos = [
            (sem_request(), {self.legado.pk}),
            (com_request(self.area), {self.meu.pk}),
            (com_request(None), {self.legado.pk}),
        ]
        for contexto, esperado in casos:
            with contexto:
                encontrados = self._pks(
                    filter_queryset_by_area(TermoAutorizacao.objects.all()),
                )

                self.assertEqual(encontrados, esperado)


class LookupDeWorkerEnxergaTudoTests(TestCase):
    """A forma exata que toda tarefa do Celery usa, no contexto que ela tem.

    `documentos/tasks.py:33-35` e os 12 lookups de
    `integracoes/google_drive/tasks.py` são todos `Model.objects.filter(pk=...)
    .first()` seguidos de `if x is None: return` — o `None` é engolido pela própria
    task, sem log e sem retry. Aqui o alvo é `TermoAutorizacao` porque é um dos dois
    modelos que esta fatia migra; `Oficio` e `DocumentoGeracao` entram nas fatias 2
    e 4, e o mesmo formato vale para eles.
    """

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="TSK-A")
        with sem_request():
            self.termo = TermoAutorizacao.objects.create(area=self.area)

    def test_lookup_por_pk_sem_request_acha_registro_de_qualquer_area(self):
        with sem_request():
            encontrado = TermoAutorizacao.objects.filter(pk=self.termo.pk).first()

        self.assertEqual(
            encontrado,
            self.termo,
            msg="a tarefa assíncrona não acharia o registro e voltaria calada",
        )


class NumeracaoDeOrdemDeServicoTests(TestCase):
    """`ordens_servico/models.py:_assign_numero` usa `all_objects` de propósito.

    O escopo da numeração é o da própria OS (`self.area_id`), não o da área ativa.
    Isso quase nunca difere, porque `save()` preenche `self.area` com
    `get_current_area()` — mas difere quando a área vem explícita na chamada, e aí
    `objects` daria `area=ativa AND area=outra` = vazio: o número volta a 1, colide
    com o que já existe e o `UniqueConstraint` estoura depois de três tentativas.
    """

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="NUM-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="NUM-B")

    def test_a_sequencia_de_cada_area_e_independente(self):
        with com_request(self.area):
            primeira = OrdemServico.objects.create(area=self.area)
            segunda = OrdemServico.objects.create(area=self.area)
        with com_request(self.outra):
            da_outra = OrdemServico.objects.create(area=self.outra)

        self.assertEqual([primeira.numero, segunda.numero], [1, 2])
        self.assertEqual(da_outra.numero, 1)

    def test_area_explicita_diferente_da_ativa_continua_a_sequencia_certa(self):
        """O caso que `all_objects` protege, e o único alcançável.

        Com `objects` em `_assign_numero`, a segunda OS receberia número 1 de novo e
        a gravação estouraria em `ordens_servico_area_ano_numero_unique`.
        """
        with sem_request():
            ja_existe = OrdemServico.objects.create(area=self.outra)

        with com_request(self.area):
            criada_de_fora = OrdemServico.objects.create(area=self.outra)

        self.assertEqual(ja_existe.numero, 1)
        self.assertEqual(
            criada_de_fora.numero,
            2,
            msg="a numeração da outra área foi zerada pela área ativa do request",
        )


class RecorteChegaNasTelasTests(TestCase):
    """Sem `filter_queryset_by_area` na chamada — é o manager fazendo o trabalho.

    É o gate de `docs/PLANO_BACKEND.md:87` ("um teste de duas áreas por modelo
    migrado") para os dois modelos desta fatia.
    """

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="TEL-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="TEL-B")
        usuario = get_user_model().objects.create_user(username="be09", password="x" * 12)
        VinculoUsuarioArea.objects.create(usuario=usuario, area=self.area, area_padrao=True)
        self.client.force_login(usuario)

    def test_termo_de_outra_area_some_do_objects_durante_o_request(self):
        with sem_request():
            meu = TermoAutorizacao.objects.create(area=self.area)
            alheio = TermoAutorizacao.objects.create(area=self.outra)

        self.client.get("/")
        with com_request(self.area):
            visiveis = set(TermoAutorizacao.objects.values_list("pk", flat=True))

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_ordem_de_outra_area_some_do_objects_durante_o_request(self):
        with sem_request():
            minha = OrdemServico.objects.create(area=self.area)
            alheia = OrdemServico.objects.create(area=self.outra)

        with com_request(self.area):
            visiveis = set(OrdemServico.objects.values_list("pk", flat=True))

        self.assertIn(minha.pk, visiveis)
        self.assertNotIn(alheia.pk, visiveis)

    def test_os_dois_modelos_declaram_o_par_de_managers(self):
        for modelo in (TermoAutorizacao, OrdemServico):
            with self.subTest(modelo=modelo.__name__):
                self.assertIsInstance(modelo.objects, AreaScopedManager)
                self.assertIs(type(modelo.all_objects), models.Manager)
                self.assertEqual(modelo._meta.default_manager_name, "all_objects")
