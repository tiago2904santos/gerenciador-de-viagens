import copy
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase

from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import ConfiguracaoSistema
from oficios.models import Oficio
from usuarios.models import AreaTrabalho


class BackfillLegacyAreasConflictTests(TransactionTestCase):
    """`TransactionTestCase` por necessidade, não por preferência.

    DB-02: o comando existe para o banco PRÉ-migração — a VPS antes do deploy
    que aplica o NOT NULL. O banco de teste já nasce migrado e recusa o ofício
    órfão que é o objeto do teste, então o `setUp` afrouxa a coluna de volta ao
    estado que o comando atende. O schema editor do SQLite não roda dentro da
    transação que o `TestCase` abre, daí a classe sem transação e o restauro
    explícito no cleanup.
    """

    #: Prestações entram porque o `post_save` do ofício cria a prestação irmã,
    #: que herda a área (nula) do ofício órfão do fixture.
    _MODELOS_AFROUXADOS = None

    @classmethod
    def _modelos(cls):
        from prestacoes_contas.models import PrestacaoContas

        return (Oficio, PrestacaoContas)

    @classmethod
    def _alterar_null(cls, de_null, para_null):
        for modelo in cls._modelos():
            campo = copy.deepcopy(modelo._meta.get_field("area"))
            campo_antes = copy.deepcopy(campo)
            campo_antes.null = de_null
            campo.null = para_null
            with connection.schema_editor() as editor:
                editor.alter_field(modelo, campo_antes, campo)

    def _restaurar_not_null(self):
        for modelo in self._modelos():
            modelo._base_manager.filter(area__isnull=True).delete()
        self._alterar_null(True, False)

    def setUp(self):
        self._alterar_null(False, True)
        self.addCleanup(self._restaurar_not_null)

        self.area = AreaTrabalho.objects.create(
            nome="Área de destino",
            sigla="DST",
        )
        self.target_unit = Unidade.objects.create(
            area=self.area,
            nome="Unidade duplicada",
        )
        self.legacy_unit = Unidade.objects.create(area=None, nome="Unidade duplicada")
        self.target_config = ConfiguracaoSistema.objects.create(area=self.area)
        self.legacy_config = ConfiguracaoSistema.objects.create(
            area=None,
            unidade=self.legacy_unit,
            cidade_endereco="SEDE LEGADA",
        )
        self.target_server = Servidor.objects.create(
            area=self.area,
            nome="Nome oficial",
            cpf="12345678901",
            telefone="41999990000",
        )
        self.legacy_server = Servidor.objects.create(
            area=None,
            unidade=self.legacy_unit,
            nome="Nome legado",
            cpf="12345678901",
            telefone="41999990000",
        )
        self.existing_oficio = Oficio.objects.create(
            area=self.area,
            ano=2026,
            numero=10,
        )
        # Nasce com área e é rebaixado por `update()`, que não passa por
        # `save()`: o sinal de prestações lê `oficio.area`, e com `null=False`
        # esse acesso levanta `RelatedObjectDoesNotExist` num ofício órfão —
        # coisa que produção pós-migração nunca vê, mas este fixture veria.
        self.legacy_oficio = Oficio.objects.create(
            area=self.area,
            ano=2026,
            numero=999,  # provisório: o par (area, ano, 10) já é do existing_oficio
        )
        Oficio.all_objects.filter(pk=self.legacy_oficio.pk).update(area=None, numero=10)
        from prestacoes_contas.models import PrestacaoContas

        PrestacaoContas.all_objects.filter(oficio=self.legacy_oficio).update(area=None)
        self.legacy_oficio.refresh_from_db()
        self.legacy_oficio.servidores.add(self.legacy_server)

    def test_dry_run_nao_altera_dados(self):
        output = StringIO()

        call_command(
            "backfill_legacy_areas",
            area=self.area.sigla,
            resolve_conflicts=True,
            stdout=output,
        )

        self.assertTrue(Unidade.objects.filter(pk=self.legacy_unit.pk).exists())
        self.legacy_oficio.refresh_from_db()
        self.assertIsNone(self.legacy_oficio.area_id)
        self.assertEqual(self.legacy_oficio.numero, 10)
        self.assertIn("RENUMERAR", output.getvalue())

    def test_commit_consolida_identidade_e_renumera_sem_perder_relacoes(self):
        call_command(
            "backfill_legacy_areas",
            area=self.area.sigla,
            resolve_conflicts=True,
            commit=True,
            stdout=StringIO(),
        )

        self.assertFalse(Unidade.objects.filter(pk=self.legacy_unit.pk).exists())
        self.assertFalse(Servidor.objects.filter(pk=self.legacy_server.pk).exists())
        self.assertFalse(
            ConfiguracaoSistema.objects.filter(pk=self.legacy_config.pk).exists(),
        )
        self.target_config.refresh_from_db()
        self.assertEqual(self.target_config.unidade, self.target_unit)
        self.assertEqual(self.target_config.cidade_endereco, "SEDE LEGADA")
        self.legacy_oficio.refresh_from_db()
        self.assertEqual(self.legacy_oficio.area, self.area)
        self.assertGreater(self.legacy_oficio.numero, self.existing_oficio.numero)
        self.assertTrue(
            self.legacy_oficio.servidores.filter(pk=self.target_server.pk).exists(),
        )
