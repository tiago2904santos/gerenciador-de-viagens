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

from datetime import date, time
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.test import TestCase

from cadastros.models import Cidade, Estado
from oficios.models import Oficio
from planos_trabalho.models import EventoPlano, PlanoDestino, PlanoTrabalho
from prestacoes_contas import diario_services
from prestacoes_contas.diario_services import sincronizar_trechos
from prestacoes_contas.models import DiarioBordo, DiarioBordoTrecho, PrestacaoContas
from roteiros import roteiro_logic
from roteiros.models import RoteiroDestino, Roteiro, RoteiroTrecho
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
            # Fatia 2:
            RoteiroTrecho: {"roteiro_trecho_ordem_unique"},
            DiarioBordoTrecho: {"diario_trecho_ordem_unique"},
        }

        for modelo, nomes in esperado.items():
            with self.subTest(modelo=modelo._meta.label):
                presentes = {c.name for c in modelo._meta.constraints}
                self.assertTrue(nomes <= presentes, f"faltou: {nomes - presentes}")


# ---------------------------------------------------------------------------
# `DB-08` fatia 2 — os dois modelos que a fatia 1 deixou de fora.
#
# `RoteiroTrecho` e `DiarioBordoTrecho` não puderam receber constraint na fatia 1
# porque os escritores reaproveitam a linha por `id` e gravam a posição uma a
# uma: trocar dois trechos de lugar colide no meio do laço, com uma linha que
# ainda não foi reposicionada nem apagada. A constraint só entra junto com a
# conversão dos dois escritores para dois passos.
# ---------------------------------------------------------------------------


class TrechoDeRoteiroTests(BaseColecoes):
    """A constraint em si, e as duas metades que ela não pode quebrar."""

    def setUp(self):
        self.roteiro = Roteiro.objects.create(
            area=self.area, origem_estado=self.estado, origem_cidade=self.cidade,
        )

    def trecho(self, ordem, *, tipo=RoteiroTrecho.TIPO_IDA, destino=None):
        return RoteiroTrecho.objects.create(
            roteiro=self.roteiro,
            ordem=ordem,
            tipo=tipo,
            origem_estado=self.estado,
            origem_cidade=self.cidade,
            destino_estado=self.estado,
            destino_cidade=destino or self.cidade2,
        )

    def test_duas_posicoes_iguais_no_mesmo_roteiro_sao_recusadas(self):
        """O defeito: a ordem passa a depender do desempate por `pk`.

        `trechos_ordenados` (`diario_services.py:214`) ordena por
        `(tipo, ordem, pk)`. Com duas linhas na mesma posição, quem decide o
        itinerário impresso é o `pk` — e o documento deixa de ser função do que
        está na tela.
        """
        self.trecho(0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.trecho(0, destino=self.cidade)

    def test_a_mesma_posicao_em_roteiros_diferentes_e_permitida(self):
        outro = Roteiro.objects.create(area=self.area)
        self.trecho(0)

        RoteiroTrecho.objects.create(
            roteiro=outro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade,
            destino_estado=self.estado,
            destino_cidade=self.cidade2,
        )

        self.assertEqual(RoteiroTrecho.objects.filter(ordem=0).count(), 2)

    def test_a_ida_e_o_retorno_convivem_porque_o_retorno_vem_uma_casa_acima(self):
        """A metade que `(roteiro, tipo, ordem)` teria deixado passar.

        Escolhi `(roteiro, ordem)` e não `(roteiro, tipo, ordem)` porque o
        escritor dá ao retorno `len(trechos_validated)` — uma casa acima de todas
        as de ida. Se um dia ele passar a repetir a posição da última ida, é este
        desenho que reprova, e é isso que se quer: as duas linhas sairiam
        empatadas no documento.
        """
        self.trecho(0)
        self.trecho(1)

        retorno = self.trecho(2, tipo=RoteiroTrecho.TIPO_RETORNO)

        self.assertEqual(self.roteiro.trechos.count(), 3)
        self.assertEqual(retorno.ordem, 2)


class EscritorDeTrechoEmDoisPassosTests(TestCase):
    """O laço real de `_salvar_roteiro_avulso_from_roteiro_state`, não uma imitação.

    Cada teste aqui reprova se o primeiro passo (o `UPDATE` que empurra as
    posições para o bloco livre) for removido — é o que a inversão tem de mostrar.
    """

    @classmethod
    def setUpTestData(cls):
        # `DB-02` grupo 1 tornou `area` obrigatória em `Roteiro` e `Oficio`
        # (`roteiros/0013_area_obrigatoria`); fixture sem área não grava mais.
        cls.area = AreaTrabalho.objects.create(nome="Área trechos", sigla="TRE")
        cls.estado = Estado.objects.create(nome="Santa Catarina", sigla="SC")
        cls.sede = Cidade.objects.create(nome="Florianópolis", estado=cls.estado)
        cls.destino_a = Cidade.objects.create(nome="Joinville", estado=cls.estado)
        cls.destino_b = Cidade.objects.create(nome="Blumenau", estado=cls.estado)
        cls.destino_c = Cidade.objects.create(nome="Chapecó", estado=cls.estado)

    def setUp(self):
        self.roteiro = Roteiro.objects.create(
            area=self.area,
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.sede,
        )

    def criar_trecho(self, ordem, destino, *, dia):
        return RoteiroTrecho.objects.create(
            roteiro=self.roteiro,
            ordem=ordem,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.sede,
            destino_estado=self.estado,
            destino_cidade=destino,
            saida_dt=f"2026-05-{dia:02d} 08:00",
            chegada_dt=f"2026-05-{dia:02d} 10:00",
        )

    def payload(self, trechos):
        """`(roteiro_state, validated)` no formato que o editor manda."""
        state = {
            "destinos_atuais": [
                {"estado_id": self.estado.pk, "cidade_id": t["destino"].pk}
                for t in trechos
            ],
            "retorno": {},
        }
        validated = {
            "trechos": [
                {
                    "id": t["id"],
                    "origem_estado_id": self.estado.pk,
                    "origem_cidade_id": self.sede.pk,
                    "destino_estado_id": self.estado.pk,
                    "destino_cidade_id": t["destino"].pk,
                    "saida_data": date(2026, 5, t["dia"]),
                    "saida_hora": time(8, 0),
                    "chegada_data": date(2026, 5, t["dia"]),
                    "chegada_hora": time(10, 0),
                }
                for t in trechos
            ],
            "retorno_saida_data": date(2026, 5, 20),
            "retorno_saida_hora": time(18, 0),
            "retorno_chegada_data": date(2026, 5, 20),
            "retorno_chegada_hora": time(20, 0),
        }
        return state, validated

    def salvar(self, trechos):
        state, validated = self.payload(trechos)
        roteiro_logic._salvar_roteiro_avulso_from_roteiro_state(
            self.roteiro, state, validated,
        )

    def test_trocar_dois_trechos_de_lugar_nao_colide(self):
        """**A razão de a fatia 1 ter deixado este modelo para trás.**

        Sem o primeiro passo, o `save()` que leva o segundo trecho para a posição
        0 encontra o primeiro ainda ocupando a 0 — e o banco recusa no meio do
        laço, com o roteiro meio gravado.
        """
        t1 = self.criar_trecho(0, self.destino_a, dia=1)
        t2 = self.criar_trecho(1, self.destino_b, dia=2)

        self.salvar([
            {"id": t2.pk, "destino": self.destino_b, "dia": 2},
            {"id": t1.pk, "destino": self.destino_a, "dia": 1},
        ])

        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual((t2.ordem, t1.ordem), (0, 1))

    def test_encolher_o_roteiro_poe_o_retorno_onde_havia_uma_ida(self):
        """A colisão que não é troca de lugar, e que eu não tinha visto.

        Três idas (0,1,2) e o retorno em 3. O payload novo traz duas idas, então
        o retorno passa a valer 2 — posição que a terceira ida ainda ocupa,
        porque o `delete()` das linhas que sobraram só roda no fim da função.
        """
        t1 = self.criar_trecho(0, self.destino_a, dia=1)
        t2 = self.criar_trecho(1, self.destino_b, dia=2)
        self.criar_trecho(2, self.destino_c, dia=3)
        RoteiroTrecho.objects.create(
            roteiro=self.roteiro,
            ordem=3,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.destino_c,
            destino_estado=self.estado,
            destino_cidade=self.sede,
        )

        self.salvar([
            {"id": t1.pk, "destino": self.destino_a, "dia": 1},
            {"id": t2.pk, "destino": self.destino_b, "dia": 2},
        ])

        posicoes = list(
            self.roteiro.trechos.order_by("ordem").values_list("ordem", "tipo"),
        )
        self.assertEqual(
            posicoes,
            [
                (0, RoteiroTrecho.TIPO_IDA),
                (1, RoteiroTrecho.TIPO_IDA),
                (2, RoteiroTrecho.TIPO_RETORNO),
            ],
        )

    def test_o_bloco_de_deslocamento_fica_vazio_no_fim(self):
        """O primeiro passo é um empréstimo; nenhuma linha pode ficar lá.

        Sem esta asserção, um escritor que esquecesse de reposicionar uma linha
        passaria nos testes acima — a constraint continuaria satisfeita, e o
        usuário veria um trecho com posição 1.000.002.
        """
        t1 = self.criar_trecho(0, self.destino_a, dia=1)
        t2 = self.criar_trecho(1, self.destino_b, dia=2)

        self.salvar([
            {"id": t2.pk, "destino": self.destino_b, "dia": 2},
            {"id": t1.pk, "destino": self.destino_a, "dia": 1},
        ])

        self.assertFalse(
            self.roteiro.trechos.filter(
                ordem__gte=roteiro_logic.DESLOCAMENTO_ORDEM_TRECHO,
            ).exists(),
        )

    def test_falha_entre_os_dois_passos_nao_deixa_posicao_no_bloco(self):
        """Por que a função virou `@transaction.atomic`.

        O caminho do autosave (`roteiros/services/autosave.py`) não abre transação
        nenhuma. A falha aqui é injetada **entre os dois passos** — o primeiro
        trecho já voltou do bloco, o segundo ainda não — que é o único instante em
        que existe linha estacionada. Sem o `atomic`, ela fica lá: posição
        1.000.001 na tela, e a próxima gravação não conserta sozinha, porque o
        primeiro passo soma outro deslocamento em cima.
        """
        self.criar_trecho(0, self.destino_a, dia=1)
        t2 = self.criar_trecho(1, self.destino_b, dia=2)

        original = RoteiroTrecho.save
        chamadas = []

        def falhar_na_segunda(self_trecho, *args, **kwargs):
            chamadas.append(self_trecho.pk)
            if len(chamadas) == 2:
                raise RuntimeError("falha entre os dois passos")
            return original(self_trecho, *args, **kwargs)

        with mock.patch.object(RoteiroTrecho, "save", falhar_na_segunda):
            with self.assertRaises(RuntimeError):
                self.salvar([
                    {"id": t2.pk, "destino": self.destino_b, "dia": 2},
                    {"id": self.roteiro.trechos.first().pk, "destino": self.destino_a, "dia": 1},
                ])

        self.assertFalse(
            self.roteiro.trechos.filter(
                ordem__gte=roteiro_logic.DESLOCAMENTO_ORDEM_TRECHO,
            ).exists(),
            "sobrou trecho estacionado no bloco de deslocamento",
        )
        self.assertEqual(
            sorted(self.roteiro.trechos.values_list("ordem", flat=True)), [0, 1],
        )


class TrechoDeDiarioTests(TestCase):
    """O diário de bordo é peça assinada de prestação de contas de combustível."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área diário", sigla="DIA")

    def diario(self):
        oficio = Oficio.objects.create(
            area=self.area,
            numero=900 + Oficio.all_objects.count(),
            ano=2026,
            protocolo="900000000",
        )
        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        return DiarioBordo.objects.create(prestacao=prestacao)

    def test_duas_posicoes_iguais_no_mesmo_diario_sao_recusadas(self):
        d = self.diario()
        DiarioBordoTrecho.objects.create(diario=d, ordem=0, km_inicial=100, km_final=200)

        with self.assertRaises(IntegrityError), transaction.atomic():
            DiarioBordoTrecho.objects.create(
                diario=d, ordem=0, km_inicial=200, km_final=300,
            )

    def test_a_mesma_posicao_em_diarios_diferentes_e_permitida(self):
        d1, d2 = self.diario(), self.diario()
        DiarioBordoTrecho.objects.create(diario=d1, ordem=0)

        DiarioBordoTrecho.objects.create(diario=d2, ordem=0)

        self.assertEqual(DiarioBordoTrecho.objects.filter(ordem=0).count(), 2)


class SincronizarTrechosEmDoisPassosTests(TestCase):
    """`sincronizar_trechos` reaproveita a linha por `id` para não perder o KM digitado.

    É o mesmo formato do escritor de roteiro, e a mesma colisão: quando o roteiro
    muda de ordem, a posição que está sendo gravada ainda pertence a outra linha.
    """

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área sincronia", sigla="SIN")
        self.estado = Estado.objects.create(nome="Bahia", sigla="BA")
        self.sede = Cidade.objects.create(nome="Salvador", estado=self.estado)
        self.destino_a = Cidade.objects.create(nome="Ilhéus", estado=self.estado)
        self.destino_b = Cidade.objects.create(nome="Juazeiro", estado=self.estado)
        self.roteiro = Roteiro.objects.create(
            area=self.area, origem_estado=self.estado, origem_cidade=self.sede,
        )
        self.oficio = Oficio.objects.create(
            area=self.area,
            numero=910 + Oficio.all_objects.count(),
            ano=2026,
            protocolo="910000000",
            roteiro=self.roteiro,
        )
        prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.diario = DiarioBordo.objects.create(prestacao=prestacao)
        self.t_a = self.trecho(0, self.destino_a)
        self.t_b = self.trecho(1, self.destino_b)

    def trecho(self, ordem, destino):
        return RoteiroTrecho.objects.create(
            roteiro=self.roteiro,
            ordem=ordem,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.sede,
            destino_estado=self.estado,
            destino_cidade=destino,
        )

    def test_reordenar_o_roteiro_troca_as_linhas_do_diario_sem_colidir(self):
        """A colisão real: as duas linhas trocam de posição no mesmo laço.

        Sem o primeiro passo em `sincronizar_trechos`, o `save()` que leva a linha
        de `t_b` para a posição 0 encontra a de `t_a` ainda lá.
        """
        sincronizar_trechos(self.diario)
        linhas = {lin.trecho_id: lin.pk for lin in self.diario.trechos.all()}
        self.diario.trechos.filter(trecho=self.t_a).update(km_inicial=1000, km_final=1100)

        # Reordena o roteiro do mesmo jeito que o escritor de produção faz: bloco
        # livre primeiro, posições finais depois.
        self.roteiro.trechos.update(ordem=F("ordem") + 1000)
        RoteiroTrecho.objects.filter(pk=self.t_b.pk).update(ordem=0)
        RoteiroTrecho.objects.filter(pk=self.t_a.pk).update(ordem=1)

        sincronizar_trechos(self.diario)

        depois = {lin.trecho_id: lin.ordem for lin in self.diario.trechos.all()}
        self.assertEqual(depois, {self.t_b.id: 0, self.t_a.id: 1})
        # A linha é a mesma de antes, não uma recriada — é isso que preserva o KM.
        self.assertEqual(
            self.diario.trechos.get(trecho=self.t_a).pk, linhas[self.t_a.id],
        )
        self.assertEqual(self.diario.trechos.get(trecho=self.t_a).km_inicial, 1000)

    def test_o_bloco_de_deslocamento_do_diario_fica_vazio_no_fim(self):
        """Duas sincronias, não uma — e a segunda é a que prova algo.

        Na primeira as linhas ainda não existem: nascem já na posição final e
        nunca passam pelo bloco. Só na segunda é que o primeiro passo tem o que
        empurrar, e só aí a asserção morde. Com uma sincronia só, este teste
        passava mesmo com o laço deixando tudo lá — medido por inversão.
        """
        sincronizar_trechos(self.diario)

        sincronizar_trechos(self.diario)

        self.assertFalse(
            self.diario.trechos.filter(
                ordem__gte=diario_services.DESLOCAMENTO_ORDEM_TRECHO,
            ).exists(),
        )

    def test_falha_entre_os_dois_passos_nao_deixa_linha_no_bloco(self):
        """Por que `sincronizar_trechos` virou `@transaction.atomic`.

        Nenhum dos chamadores abre transação — nem as três views de
        `diario_views.py`, nem `services.py:574`.
        """
        sincronizar_trechos(self.diario)
        original = DiarioBordoTrecho.save
        chamadas = []

        def falhar_na_segunda(self_linha, *args, **kwargs):
            chamadas.append(self_linha.pk)
            if len(chamadas) == 2:
                raise RuntimeError("falha entre os dois passos")
            return original(self_linha, *args, **kwargs)

        with mock.patch.object(DiarioBordoTrecho, "save", falhar_na_segunda):
            with self.assertRaises(RuntimeError):
                sincronizar_trechos(self.diario)

        self.assertFalse(
            self.diario.trechos.filter(
                ordem__gte=diario_services.DESLOCAMENTO_ORDEM_TRECHO,
            ).exists(),
            "sobrou linha de diário estacionada no bloco de deslocamento",
        )
        self.assertEqual(
            sorted(self.diario.trechos.values_list("ordem", flat=True)), [0, 1],
        )
