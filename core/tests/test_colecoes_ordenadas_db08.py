"""`DB-08` — posição duplicada em coleção ordenada.

O enunciado citava cinco modelos e errava em três pontos, todos corrigidos por
medição antes de escrever uma linha de constraint:

1. **`eventos.EventoPlano` não existe** — o modelo é `planos_trabalho.EventoPlano`.
2. **`PlanoDestino` não é `(plano, ordem)`.** Um plano guarda ao mesmo tempo os
   destinos de rascunho (`evento IS NULL`) e as cópias por evento, e
   `services.py:968` copia `d.ordem` tal e qual ao comitar. `(plano, ordem)`
   reprovaria produção no primeiro commit de evento.
3. **Dois dos cinco não aceitam constraint simples.** `RoteiroTrecho`
   (`roteiro_logic.py:1629`) e `DiarioBordoTrecho` (`diario_services.py:282`)
   reaproveitam as linhas existentes por id e gravam `ordem` uma a uma — trocar
   duas posições colide no meio do laço. Ficam para a fatia 2, junto com a
   correção dos escritores para dois passos.

**Constraint adiada está fora**, e isso é medido, não estilo:
`connection.features.supports_deferrable_unique_constraints` é `False` no SQLite,
e a suíte roda nos dois bancos — uma constraint `DEFERRED` existiria só no
PostgreSQL e o SQLite passaria sem testar nada. É a armadilha do teste que passa
dos dois jeitos, no nível do schema.
"""

from __future__ import annotations

from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from cadastros.models import Cidade, Estado
from planos_trabalho.models import EventoPlano, PlanoDestino, PlanoTrabalho
from roteiros.models import RoteiroDestino, Roteiro
from usuarios.models import AreaTrabalho


class BaseColecoes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = AreaTrabalho.objects.create(nome="Área DB-08", sigla="DB08")
        cls.estado = Estado.objects.create(nome="Paraná", sigla="PR")
        cls.cidade = Cidade.objects.create(nome="Curitiba", estado=cls.estado)
        cls.cidade2 = Cidade.objects.create(nome="Londrina", estado=cls.estado)


class DestinoDeRoteiroTests(BaseColecoes):
    def setUp(self):
        self.roteiro = Roteiro.objects.create(area=self.area)

    def destino(self, ordem, cidade=None):
        return RoteiroDestino.objects.create(
            roteiro=self.roteiro,
            estado=self.estado,
            cidade=cidade or self.cidade,
            ordem=ordem,
        )

    def test_duas_posicoes_iguais_no_mesmo_roteiro_sao_recusadas(self):
        """O defeito: destino duplicado é contado duas vezes pelo motor de diárias."""
        self.destino(0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.destino(0, cidade=self.cidade2)

    def test_a_mesma_posicao_em_roteiros_diferentes_e_permitida(self):
        """A metade que impede a constraint de ser global demais."""
        outro = Roteiro.objects.create(area=self.area)
        self.destino(0)

        RoteiroDestino.objects.create(
            roteiro=outro, estado=self.estado, cidade=self.cidade, ordem=0,
        )

        self.assertEqual(RoteiroDestino.objects.filter(ordem=0).count(), 2)

    def test_o_caminho_de_producao_continua_funcionando(self):
        """Reordenar apaga tudo e recria — é por isso que a constraint pode ser simples.

        Se algum dia o escritor passar a reaproveitar linha e trocar posições, este
        teste continua verde e o de cima também: quem reprova é este, que reproduz
        o `delete()` + `create()` de `roteiro_logic.py:1581`.
        """
        self.destino(0)
        self.destino(1, cidade=self.cidade2)

        self.roteiro.destinos.all().delete()
        for ordem, cidade in enumerate([self.cidade2, self.cidade]):
            RoteiroDestino.objects.create(
                roteiro=self.roteiro, estado=self.estado, cidade=cidade, ordem=ordem,
            )

        self.assertEqual(
            [d.cidade_id for d in self.roteiro.destinos.order_by("ordem")],
            [self.cidade2.id, self.cidade.id],
        )


class DestinoDePlanoTests(BaseColecoes):
    def setUp(self):
        self.plano = PlanoTrabalho.objects.create(area=self.area)

    def destino(self, ordem, *, evento=None, cidade=None):
        return PlanoDestino.objects.create(
            plano=self.plano,
            evento=evento,
            estado=self.estado,
            cidade=cidade or self.cidade,
            ordem=ordem,
        )

    def test_rascunho_com_posicao_repetida_e_recusado(self):
        """**A armadilha do `DB-08`.**

        `PlanoDestino.evento` é anulável, e em SQL NULL é distinto de NULL num
        índice único. Uma constraint só sobre `(plano, evento, ordem)` ficaria
        verde aqui — e o rascunho é justamente o caso mais comum, o que o
        formulário do plano grava (`forms.py:_save_destinos`). É por isso que são
        duas constraints parciais e não uma.
        """
        self.destino(1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.destino(1, cidade=self.cidade2)

    def test_evento_com_posicao_repetida_e_recusado(self):
        evento = EventoPlano.objects.create(plano=self.plano, ordem=1)
        self.destino(1, evento=evento)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.destino(1, evento=evento, cidade=self.cidade2)

    def test_o_rascunho_e_a_copia_do_evento_convivem_na_mesma_posicao(self):
        """A metade que `(plano, ordem)` teria quebrado em produção.

        `services.py:968` copia `d.ordem` tal e qual ao comitar o evento, então o
        plano fica com duas linhas de `ordem=1` — uma de rascunho, uma do evento.
        Uma constraint sobre `(plano, ordem)` reprovaria o primeiro commit.
        """
        evento = EventoPlano.objects.create(plano=self.plano, ordem=1)
        rascunho = self.destino(1)

        copia = self.destino(1, evento=evento)

        self.assertIsNone(rascunho.evento_id)
        self.assertEqual(copia.evento_id, evento.id)
        self.assertEqual(self.plano.destinos.filter(ordem=1).count(), 2)

    def test_dois_eventos_do_mesmo_plano_na_mesma_posicao_sao_recusados(self):
        EventoPlano.objects.create(plano=self.plano, ordem=1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoPlano.objects.create(plano=self.plano, ordem=1)


class DesenhoDaConstraintTests(TestCase):
    """Por que simples e não adiada — a razão fica no teste, não só no comentário."""

    def test_o_sqlite_nao_suporta_constraint_adiada(self):
        """Se um dia suportar, a fatia 2 do `DB-08` fica mais simples.

        Enquanto não suportar, `deferrable=DEFERRED` significaria uma constraint que
        só existe no PostgreSQL — e a suíte do SQLite passaria sem testar nada.
        """
        if connection.vendor == "sqlite":
            self.assertFalse(connection.features.supports_deferrable_unique_constraints)
        else:
            self.assertTrue(connection.features.supports_deferrable_unique_constraints)

    def test_as_constraints_do_db08_estao_todas_no_lugar(self):
        esperado = {
            RoteiroDestino: {"roteiro_destino_ordem_unique"},
            PlanoDestino: {
                "plano_destino_rascunho_ordem_unique",
                "plano_destino_evento_ordem_unique",
            },
            EventoPlano: {"evento_plano_ordem_unique"},
        }

        for modelo, nomes in esperado.items():
            with self.subTest(modelo=modelo._meta.label):
                presentes = {c.name for c in modelo._meta.constraints}
                self.assertTrue(nomes <= presentes, f"faltou: {nomes - presentes}")
