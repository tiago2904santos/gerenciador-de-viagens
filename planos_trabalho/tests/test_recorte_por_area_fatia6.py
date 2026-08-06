"""BE-09, fatia 6 — os oito modelos que faltavam. A catraca chega a zero.

Fecha o `BE-09`: `planos_trabalho` (cinco modelos), `justificativas.ModeloJustificativa`,
`integracoes.DriveReorganizacaoJob` e `core.AuditEvent`.

Três coisas nesta fatia não apareceram nas anteriores.

**`core.AuditEvent`** é a trilha de auditoria. Recortá-la significa que a lista de
eventos passa a mostrar só a área ativa — que é o comportamento certo, e o mesmo
que as listas de todo o resto do sistema já têm. O que **não** pode acontecer é a
escrita parar de registrar: `core/audit.py:127` faz `create()`, que não passa pelo
`get_queryset` e portanto é indiferente ao manager. Há teste para os dois lados.

**`DriveReorganizacaoJob`** é atualizado de dentro de uma **thread de fundo**
(`integracoes/google_drive/views.py:_executar_reorganizacao`), onde não há área
ambiente. As três atualizações de progresso e desfecho usam `all_objects`: se
recortassem, o job nunca sairia de "em andamento" na tela.

**`PlanoTrabalho.proximo_numero`** volta aqui pelo outro lado. A fatia 5b tratou o
lock sobre a configuração; esta trata o `max(numero)` sobre os planos, que é o piso
real da numeração.
"""

from __future__ import annotations

from django.test import TestCase

from core.models import AuditEvent
from core.tests.test_area_scoped_manager import com_request
from core.tests.test_area_scoped_manager import sem_request
from integracoes.google_drive.models import DriveReorganizacaoJob
from justificativas.models import ModeloJustificativa
from planos_trabalho.models import AtividadePlanoTrabalho
from planos_trabalho.models import HorarioAtendimento
from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.models import PresetAtividadesPlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante
from usuarios.models import AreaTrabalho

OITO = (
    ProgramaSolicitante,
    HorarioAtendimento,
    AtividadePlanoTrabalho,
    PresetAtividadesPlanoTrabalho,
    PlanoTrabalho,
    ModeloJustificativa,
    DriveReorganizacaoJob,
    AuditEvent,
)


class RecorteChegaNosOitoModelosTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="F6-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="F6-B")
        self.contador = iter(range(1000))

    def _n(self):
        return next(self.contador)

    def _visiveis(self, modelo):
        with com_request(self.area):
            return set(modelo.objects.values_list("pk", flat=True))

    def _checar(self, modelo, criar):
        with sem_request():
            meu, alheio = criar(self.area), criar(self.outra)
        visiveis = self._visiveis(modelo)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis, msg=f"{modelo.__name__} vazou entre áreas")

    def test_programa_solicitante(self):
        self._checar(
            ProgramaSolicitante,
            lambda a: ProgramaSolicitante.objects.create(area=a, nome=f"Programa {self._n()}"),
        )

    def test_horario_atendimento(self):
        self._checar(
            HorarioAtendimento,
            lambda a: HorarioAtendimento.objects.create(area=a, faixa=f"Faixa {self._n()}"),
        )

    def test_atividade(self):
        self._checar(
            AtividadePlanoTrabalho,
            lambda a: AtividadePlanoTrabalho.objects.create(
                area=a, codigo=f"C{self._n():04d}", nome=f"Atividade {self._n()}",
            ),
        )

    def test_preset_de_atividades(self):
        self._checar(
            PresetAtividadesPlanoTrabalho,
            lambda a: PresetAtividadesPlanoTrabalho.objects.create(area=a, nome=f"Preset {self._n()}"),
        )

    def test_plano_trabalho(self):
        self._checar(PlanoTrabalho, lambda a: PlanoTrabalho.objects.create(area=a))

    def test_modelo_justificativa(self):
        self._checar(
            ModeloJustificativa,
            lambda a: ModeloJustificativa.objects.create(area=a, nome=f"Modelo {self._n()}", texto="…"),
        )

    def test_job_de_reorganizacao(self):
        self._checar(DriveReorganizacaoJob, lambda a: DriveReorganizacaoJob.objects.create(area=a))

    def test_audit_event(self):
        self._checar(
            AuditEvent,
            lambda a: AuditEvent.objects.create(
                area=a, action=AuditEvent.ACTION_CREATE, model_label="x.Y", object_id="1",
            ),
        )

    def test_os_oito_declaram_o_par_de_managers(self):
        for modelo in OITO:
            with self.subTest(modelo=modelo.__name__):
                self.assertIs(modelo._default_manager, modelo.all_objects)
                self.assertEqual(modelo._meta.default_manager_name, "all_objects")


class TrilhaDeAuditoriaContinuaGravandoTests(TestCase):
    """Recortar a **leitura** é o objetivo; parar a **escrita** seria desastre."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="AUD-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="AUD-B")

    def test_o_evento_e_gravado_mesmo_com_area_diferente_da_ativa(self):
        """`core/audit.py:127` faz `create()`, que não passa pelo `get_queryset` —
        indiferente ao manager. Este teste existe para que continue assim."""
        with com_request(self.area):
            evento = AuditEvent.objects.create(
                area=self.outra, action=AuditEvent.ACTION_UPDATE, model_label="x.Y", object_id="9",
            )

        self.assertIsNotNone(evento.pk)
        self.assertTrue(AuditEvent.all_objects.filter(pk=evento.pk).exists())


class JobDoDriveAtualizaDeThreadDeFundoTests(TestCase):
    """As três atualizações de `_executar_reorganizacao` rodam sem área ambiente."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="DRV-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="DRV-B")

    def test_o_progresso_do_job_de_outra_area_e_gravado(self):
        with sem_request():
            job = DriveReorganizacaoJob.objects.create(area=self.outra)

        with com_request(self.area):
            # O contraste é a afirmação: `objects` não atualiza linha nenhuma, e o
            # `update()` devolve 0 **sem erro** — por isso o job ficaria preso em
            # "em andamento" na tela, sem nada no log.
            self.assertEqual(
                DriveReorganizacaoJob.objects.filter(pk=job.pk).update(eventos_processados=1),
                0,
            )
            atualizadas = DriveReorganizacaoJob.all_objects.filter(pk=job.pk).update(
                eventos_processados=7, total_eventos=10,
            )

        job.refresh_from_db()
        self.assertEqual(atualizadas, 1, msg="o job ficaria preso em 'em andamento'")
        self.assertEqual(job.eventos_processados, 7)


class NumeracaoDePlanoUsaOPisoDaAreaDoPlanoTests(TestCase):
    """`proximo_numero` pela segunda vez: a 5b tratou o lock, esta trata o piso.

    `max(numero)` sobre os planos da área é o que impede reemitir número já usado
    quando o contador da configuração está atrasado — e é justamente o `max()` que
    um recorte pela área ativa zeraria.
    """

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="PIS-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="PIS-B")

    def test_o_piso_vem_dos_planos_da_area_pedida(self):
        from cadastros.models import ConfiguracaoSistema

        with sem_request():
            # Contador atrasado de propósito: quem segura o número é o banco.
            config = ConfiguracaoSistema.get_for_area(self.outra)
            config.pt_ultimo_numero = 0
            config.pt_ano = 2026
            config.save(update_fields=["pt_ultimo_numero", "pt_ano"])
            PlanoTrabalho.objects.create(area=self.outra, numero=30, ano=2026)

        with com_request(self.area):
            numero, _ano, _sufixo = PlanoTrabalho.proximo_numero(self.outra)

        self.assertEqual(
            numero,
            31,
            msg="a numeração não viu o plano 30 já emitido e reemitiria número usado",
        )


class PadraoUnicoPorAreaTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="PU6-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="PU6-B")

    def test_modelo_de_justificativa(self):
        """Recortado, o `NOVO-09` seria desfeito."""
        with sem_request():
            antigo = ModeloJustificativa.objects.create(
                area=self.outra, nome="Antigo", texto="…", is_padrao=True,
            )

        with com_request(self.area):
            ModeloJustificativa.all_objects.create(
                area=self.outra, nome="Novo", texto="…", is_padrao=True,
            )

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao)

    def test_preset_de_atividades(self):
        with sem_request():
            antigo = PresetAtividadesPlanoTrabalho.objects.create(
                area=self.outra, nome="Antigo", is_padrao=True,
            )

        with com_request(self.area):
            PresetAtividadesPlanoTrabalho.all_objects.create(
                area=self.outra, nome="Novo", is_padrao=True,
            )

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao)


class OIdEstaFechadoTests(TestCase):
    """A afirmação que o `BE-09` fez no começo, agora verificável por introspecção."""

    def test_todo_modelo_com_area_recorta_sozinho(self):
        from django.apps import apps
        from django.db import models

        from core.managers import AreaScopedManager

        #: A tabela de vínculo não é dado de tenant: `resolve_area_for_request` a
        #: consulta para descobrir qual é a área ativa, então recortá-la faria
        #: ninguém mais resolver área nenhuma.
        fora = {"usuarios.VinculoUsuarioArea"}

        pendentes = []
        for modelo in apps.get_models():
            if modelo._meta.label in fora:
                continue
            if not any(f.name == "area" for f in modelo._meta.concrete_fields):
                continue
            if (
                not isinstance(modelo._meta.managers_map.get("objects"), AreaScopedManager)
                or type(modelo._meta.managers_map.get("all_objects")) is not models.Manager
                or modelo._meta.default_manager_name != "all_objects"
            ):
                pendentes.append(modelo._meta.label)

        self.assertEqual(pendentes, [], msg="modelo com `area` sem o manager que recorta")
