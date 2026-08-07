"""NOVO-31 — o check `core.E001` era cego para 20 dos 28 modelos com `area`.

`_OPERATIONAL_MODELS` era uma tupla fixa de oito nomes, escrita quando o sistema
tinha menos modelos, e nunca acompanhou. Ficavam de fora os seis de `cadastros`
— justamente os que os comandos de seed criam sem área — e os cinco de
`planos_trabalho`. Ou seja: nada bloqueava nem relatava um deploy com esses
modelos cheios de `area IS NULL`, e o `DB-02` não tinha como saber o tamanho do
backfill.

A varredura passou a ser por introspecção, com **duas severidades**. Promover os
vinte a `Error` de uma vez tornaria vermelho todo deploy até alguém rodar o
backfill, e essa não é decisão de um check.
"""

from __future__ import annotations

from django.test import TestCase

from cadastros.models import Servidor
from core.checks import check_operational_records_have_area
from core.models import AuditEvent
from usuarios.models import AreaTrabalho


def _por_id(problemas):
    return {p.id: p for p in problemas}


class VarreduraCobreTodoModeloComAreaTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="CHK-A")

    def test_a_linha_de_base_de_um_banco_novo_ja_tem_orfas(self):
        """O achado que o `NOVO-31` existia para produzir, e que muda o `DB-02`.

        Num banco **recém-migrado**, sem nenhum dado de usuário, cinco modelos já
        têm linha com `area IS NULL` — todas criadas por seed de migração:
        `TipoEvento` (5), `ConfiguracaoNumeracaoOficio` (1), `ProgramaSolicitante`
        (3), `HorarioAtendimento` (3) e `AtividadePlanoTrabalho` (11).

        Elas não são resíduo a sanear: são o **padrão global** da instalação. A de
        `ConfiguracaoNumeracaoOficio` é o piso de numeração de 2026
        (`numero_inicial=75`), do qual todo ofício deste ano depende — e
        `Oficio.get_next_available_numero` a busca de propósito com
        `Q(area=area) | Q(area__isnull=True)`.

        Ou seja: `area` NOT NULL **não** pode ser aplicado a estes cinco sem antes
        decidir o que fazer com o global. Registrado como `NOVO-34`.
        """
        problemas = _por_id(check_operational_records_have_area(None))

        self.assertNotIn("core.E001", problemas, msg="banco novo não pode ter pendência bloqueante")
        self.assertIn("core.W001", problemas)
        for semeado in ("eventos.TipoEvento", "oficios.ConfiguracaoNumeracaoOficio",
                        "planos_trabalho.ProgramaSolicitante"):
            self.assertIn(semeado, problemas["core.W001"].msg)

    def test_modelo_operacional_continua_bloqueando_o_deploy(self):
        # DB-02: o banco migrado recusa Oficio sem área, então o órfão de
        # verdade só existe na janela que o check vigia — o deploy que roda com
        # o código novo contra um banco ainda não migrado. Promove-se um modelo
        # anulável a "operacional" para exercitar a rota de severidade.
        from unittest import mock

        from core import checks as core_checks
        from eventos.models import TipoEvento

        TipoEvento.all_objects.create(area=None, nome="Órfão operacional")

        with mock.patch.object(core_checks, "_OPERATIONAL_MODELS", ("eventos.TipoEvento",)):
            problemas = _por_id(check_operational_records_have_area(None))

        self.assertIn("core.E001", problemas)
        self.assertRegex(problemas["core.E001"].msg, r"eventos\.TipoEvento=\d+")

    def test_modelo_de_cadastros_passa_a_ser_relatado(self):
        """O defeito: `cadastros.Servidor` não era olhado por check nenhum."""
        Servidor.all_objects.create(area=None, nome="Sem área")

        problemas = _por_id(check_operational_records_have_area(None))

        self.assertIn("core.W001", problemas)
        self.assertIn("cadastros.Servidor=1", problemas["core.W001"].msg)

    def test_o_relato_nao_bloqueia_o_deploy(self):
        """`check --deploy` só falha em ERROR; o aviso informa sem travar."""
        Servidor.all_objects.create(area=None, nome="Sem área")

        problemas = _por_id(check_operational_records_have_area(None))

        self.assertNotIn("core.E001", problemas)
        self.assertEqual(problemas["core.W001"].level, 30)  # WARNING

    def test_auditevent_fica_fora_por_projeto(self):
        """`AuditEvent.area` é `SET_NULL`: evento antigo perde a área quando ela é
        apagada, e a trilha tem de sobreviver a isso. Linha sem área ali é
        histórico, não pendência — e por isso não entra no `DB-02`."""
        AuditEvent.all_objects.create(
            area=None, action=AuditEvent.ACTION_CREATE, model_label="x.Y", object_id="1",
        )

        problemas = _por_id(check_operational_records_have_area(None))

        self.assertNotIn("core.E001", problemas)
        self.assertNotIn("core.AuditEvent", problemas["core.W001"].msg)

    def test_a_varredura_e_derivada_do_registro_de_apps(self):
        """A lista fixa foi o defeito. Este teste reprova se alguém a recongelar."""
        from core.checks import _modelos_com_area

        labels = {label for label, _ in _modelos_com_area()}

        self.assertGreaterEqual(len(labels), 20, msg="a varredura voltou a ser uma lista curta")
        for esperado in ("cadastros.Servidor", "cadastros.ConfiguracaoSistema",
                         "planos_trabalho.PlanoTrabalho", "justificativas.ModeloJustificativa"):
            self.assertIn(esperado, labels)
        self.assertNotIn("usuarios.VinculoUsuarioArea", labels)
        self.assertNotIn("core.AuditEvent", labels)
