"""`DB-07` — o banco recusa período invertido e dinheiro negativo.

O sistema tinha 2 `CheckConstraint` para 54 modelos. O defeito não era um bug de
tela: era o banco não ser última linha de defesa de nada. Qualquer caminho que
escapasse do formulário — import, comando de gestão, migração de dados, correção
manual em produção — gravava fim antes do início, e o valor seguia dali para o
ofício e para a prestação assinada.

**Por que os testes escrevem por `update()` e não por `save()`.** É o caminho que
o defeito descreve. `Model.save()` passa por normalizações que podem corrigir o
valor antes de ele chegar ao banco; um teste que só usasse `save()` poderia passar
verde sem que constraint nenhuma existisse. `queryset.update()` monta o `UPDATE`
direto — se a linha entrar, é porque o banco aceitou.

**Cobertura por introspecção.** `TodasAsConstraintsTemTesteTests` compara a lista
de casos com `Model._meta.constraints` do projeto inteiro. Uma constraint nova sem
caso aqui reprova; um caso apontando para constraint que não existe mais, também.
Sem isso, esta suíte envelheceria em silêncio — que é como o `NOVO-31` aconteceu.
"""

from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Servidor
from cadastros.models import TabelaDiaria
from eventos.models import Evento
from oficios.models import Oficio
from ordens_servico.models import OrdemServico
from planos_trabalho.models import EventoPlano
from planos_trabalho.models import PlanoTrabalho
from prestacoes_contas.models import DiarioBordo
from prestacoes_contas.models import DiarioBordoTrecho
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.models import PrestacaoServidor
from roteiros.models import Roteiro
from roteiros.models import RoteiroTrecho
from termos.models import TermoAutorizacao

HOJE = date(2026, 8, 10)
AGORA = timezone.make_aware(datetime(2026, 8, 10, 8, 0))


class ConstraintsBase(TestCase):
    """Fábricas mínimas — cada uma devolve uma linha que **satisfaz** tudo."""

    def _roteiro(self):
        return Roteiro.objects.create(saida_dt=AGORA, chegada_dt=AGORA + timedelta(hours=2))

    def _roteiro_trecho(self):
        return RoteiroTrecho.objects.create(
            roteiro=self._roteiro(),
            ordem=1,
            saida_dt=AGORA,
            chegada_dt=AGORA + timedelta(hours=1),
        )

    def _evento(self):
        return Evento.objects.create(
            titulo="Evento DB-07", data_inicio=HOJE, data_fim=HOJE + timedelta(days=2),
        )

    def _termo(self):
        return TermoAutorizacao.objects.create(
            data_evento_inicio=HOJE, data_evento_fim=HOJE + timedelta(days=2),
        )

    def _plano(self):
        return PlanoTrabalho.objects.create(
            data_evento_inicio=HOJE, data_evento_fim=HOJE + timedelta(days=2),
        )

    def _evento_plano(self):
        return EventoPlano.objects.create(
            plano=self._plano(),
            ordem=1,
            data_evento_inicio=HOJE,
            data_evento_fim=HOJE + timedelta(days=1),
        )

    def _ordem_servico(self):
        return OrdemServico.objects.create(
            data_evento_inicio=HOJE, data_evento_fim=HOJE + timedelta(days=2),
        )

    def _prestacao_servidor(self):
        cargo = Cargo.objects.create(nome=f"Cargo {Cargo.objects.count()}")
        servidor = Servidor.objects.create(
            nome=f"Servidor DB07 {Servidor.objects.count()}",
            cargo=cargo,
            cpf=f"{Servidor.objects.count():011d}",
        )
        oficio = Oficio.objects.create(
            numero=800 + Oficio.all_objects.count(), ano=2026, protocolo="800000000",
        )
        oficio.servidores.add(servidor)
        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        ps = PrestacaoServidor.todos.get(prestacao=prestacao, servidor=servidor)
        PrestacaoServidor.todos.filter(pk=ps.pk).update(
            data_liberacao_diarias=HOJE, prazo_limite_saque=HOJE + timedelta(days=5),
        )
        return ps

    def _diario_trecho(self):
        ps = self._prestacao_servidor()
        diario = DiarioBordo.objects.create(prestacao=ps.prestacao)
        return DiarioBordoTrecho.objects.create(
            diario=diario, ordem=1, km_inicial=1000, km_final=1200,
        )

    def _tabela_diaria(self):
        # `vigencia_inicio` distinta a cada chamada: `uniq_tabela_diaria_faixa_vigencia`
        # já existia e reprovava a segunda fábrica do mesmo teste.
        return TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_INTERIOR,
            vigencia_inicio=HOJE - timedelta(days=TabelaDiaria.objects.count()),
            valor_24h=Decimal("300.00"),
        )

    def _gravar(self, obj, **campos):
        """`UPDATE` cru, sem passar pelo `save()`. Devolve nada; estoura se o banco recusar."""
        type(obj)._base_manager.filter(pk=obj.pk).update(**campos)

    def assert_banco_recusa(self, obj, **campos):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._gravar(obj, **campos)

    def assert_banco_aceita(self, obj, **campos):
        with transaction.atomic():
            self._gravar(obj, **campos)


#: `(fábrica, nome da constraint, campos que violam, campos que satisfazem no limite)`
#:
#: O terceiro item prova que a constraint **pega**; o quarto prova que ela não
#: pega demais — é onde `gte` se distingue de `gt`. Uma constraint sem o quarto
#: caso passaria com `gt` no lugar de `gte` e quebraria evento de um dia em
#: produção; provado por inversão, a troca reprova 22 destes casos.
#: `roteiro_ida_ordenada` voltou no `NOVO-36`, junto com a correção do produtor
#: que a reprovava. Foi esta lista que reprovou quando ela reapareceu sem caso —
#: era para isso que a régua de introspecção existia.
CASOS_ORDEM = [
    ("_roteiro", "roteiro_ida_ordenada",
     {"chegada_dt": AGORA - timedelta(hours=1)}, {"chegada_dt": AGORA}),
    ("_roteiro", "roteiro_permanencia_ordenada",
     {"chegada_dt": AGORA, "retorno_saida_dt": AGORA - timedelta(hours=1)},
     {"chegada_dt": AGORA, "retorno_saida_dt": AGORA}),
    ("_roteiro", "roteiro_volta_ordenada",
     {"retorno_saida_dt": AGORA + timedelta(days=1),
      "retorno_chegada_dt": AGORA + timedelta(hours=1)},
     {"retorno_saida_dt": AGORA + timedelta(days=1),
      "retorno_chegada_dt": AGORA + timedelta(days=1)}),
    ("_roteiro", "roteiro_periodo_ordenado",
     {"retorno_chegada_dt": AGORA - timedelta(days=1)},
     {"retorno_chegada_dt": AGORA}),
    ("_roteiro_trecho", "roteiro_trecho_ordenado",
     {"chegada_dt": AGORA - timedelta(hours=1)}, {"chegada_dt": AGORA}),
    ("_evento", "evento_periodo_ordenado",
     {"data_fim": HOJE - timedelta(days=1)}, {"data_fim": HOJE}),
    ("_termo", "termo_periodo_ordenado",
     {"data_evento_fim": HOJE - timedelta(days=1)}, {"data_evento_fim": HOJE}),
    ("_plano", "plano_periodo_ordenado",
     {"data_evento_fim": HOJE - timedelta(days=1)}, {"data_evento_fim": HOJE}),
    ("_evento_plano", "evento_plano_periodo_ordenado",
     {"data_evento_fim": HOJE - timedelta(days=1)}, {"data_evento_fim": HOJE}),
    ("_ordem_servico", "os_periodo_ordenado",
     {"data_evento_fim": HOJE - timedelta(days=1)}, {"data_evento_fim": HOJE}),
    ("_prestacao_servidor", "prest_serv_prazo_apos_liberacao",
     {"prazo_limite_saque": HOJE - timedelta(days=1)}, {"prazo_limite_saque": HOJE}),
    ("_diario_trecho", "diario_trecho_km_ordenado", {"km_final": 999}, {"km_final": 1000}),
]

CASOS_SINAL = [
    ("_roteiro", "roteiro_valor_diarias_nao_negativo",
     {"valor_diarias": Decimal("-0.01")}, {"valor_diarias": Decimal("0.00")}),
    ("_roteiro", "roteiro_distancia_calc_nao_negativa",
     {"rota_distancia_calculada_km": Decimal("-0.01")},
     {"rota_distancia_calculada_km": Decimal("0.00")}),
    ("_roteiro", "roteiro_distancia_manual_nao_negativa",
     {"rota_distancia_manual_km": Decimal("-0.01")},
     {"rota_distancia_manual_km": Decimal("0.00")}),
    ("_roteiro_trecho", "roteiro_trecho_distancia_nao_negativa",
     {"distancia_km": Decimal("-0.01")}, {"distancia_km": Decimal("0.00")}),
    ("_plano", "plano_diaria_unitaria_nao_negativa",
     {"diarias_valor_unitario": Decimal("-0.01")}, {"diarias_valor_unitario": Decimal("0.00")}),
    ("_plano", "plano_diaria_total_nao_negativa",
     {"diarias_valor_total": Decimal("-0.01")}, {"diarias_valor_total": Decimal("0.00")}),
    ("_plano", "plano_diaria_comb_unitaria_nao_negativa",
     {"diarias_combinada_valor_unitario": Decimal("-0.01")},
     {"diarias_combinada_valor_unitario": Decimal("0.00")}),
    ("_plano", "plano_diaria_comb_total_nao_negativa",
     {"diarias_combinada_valor_total": Decimal("-0.01")},
     {"diarias_combinada_valor_total": Decimal("0.00")}),
    ("_evento_plano", "evento_plano_diaria_unitaria_nao_negativa",
     {"diarias_valor_unitario": Decimal("-0.01")}, {"diarias_valor_unitario": Decimal("0.00")}),
    ("_evento_plano", "evento_plano_diaria_total_nao_negativa",
     {"diarias_valor_total": Decimal("-0.01")}, {"diarias_valor_total": Decimal("0.00")}),
    # Positivo, não apenas não-negativo: valor de diária que existe tem de valer
    # alguma coisa. Por isso o caso "no limite" é 0,01 e não zero.
    ("_tabela_diaria", "tabela_diaria_valor_15_positivo",
     {"valor_15": Decimal("0.00")}, {"valor_15": Decimal("0.01")}),
    ("_tabela_diaria", "tabela_diaria_valor_30_positivo",
     {"valor_30": Decimal("0.00")}, {"valor_30": Decimal("0.01")}),
    ("_prestacao_servidor", "prest_serv_diaria_recebida_positiva",
     {"diaria_valor_override": Decimal("0.00")}, {"diaria_valor_override": Decimal("0.01")}),
    ("_tabela_diaria", "tabela_diaria_valor_24h_positivo",
     {"valor_24h": Decimal("0.00")}, {"valor_24h": Decimal("0.01")}),
]


class OrdemDeDatasTests(ConstraintsBase):
    def test_banco_recusa_fim_antes_do_inicio(self):
        for fabrica, nome, viola, _ in CASOS_ORDEM:
            with self.subTest(constraint=nome):
                obj = getattr(self, fabrica)()
                self.assert_banco_recusa(obj, **viola)

    def test_banco_aceita_fim_igual_ao_inicio(self):
        """`gte`, não `gt`. Evento de um dia é o caso comum, não a exceção."""
        for fabrica, nome, _, limite in CASOS_ORDEM:
            with self.subTest(constraint=nome):
                obj = getattr(self, fabrica)()
                self.assert_banco_aceita(obj, **limite)

    def test_banco_aceita_com_um_dos_dois_nulo(self):
        """Preencher só uma ponta é legítimo em todas estas telas."""
        for fabrica, nome, viola, _ in CASOS_ORDEM:
            with self.subTest(constraint=nome):
                obj = getattr(self, fabrica)()
                self.assert_banco_aceita(obj, **{campo: None for campo in viola})


class SinalDeValoresTests(ConstraintsBase):
    def test_banco_recusa_valor_fora_da_regra(self):
        for fabrica, nome, viola, _ in CASOS_SINAL:
            with self.subTest(constraint=nome):
                obj = getattr(self, fabrica)()
                self.assert_banco_recusa(obj, **viola)

    def test_banco_aceita_o_menor_valor_valido(self):
        for fabrica, nome, _, limite in CASOS_SINAL:
            with self.subTest(constraint=nome):
                obj = getattr(self, fabrica)()
                self.assert_banco_aceita(obj, **limite)


class NuloContinuaPassandoTests(ConstraintsBase):
    """Rascunho com uma ponta só preenchida continua salvando — nas duas camadas.

    A condição não diz nada sobre nulo: `CHECK` cujo resultado é `NULL` passa em
    SQL, e o `Q.check()` que o `full_clean()` usa chega ao mesmo resultado. A
    primeira versão destas constraints trazia `Q(campo__isnull=True) |` na frente
    de cada condição "para o caminho Python"; **medido, os dois caminhos se
    comportam igual com e sem o ramo** — era código inerte com aparência de carga
    útil. Removido de lá, a garantia passou a morar aqui, onde é verificável e
    onde uma regressão de versão do Django apareceria.
    """

    def test_full_clean_aceita_so_uma_das_duas_datas(self):
        for kwargs in (
            {"data_inicio": HOJE, "data_fim": None},
            {"data_inicio": None, "data_fim": HOJE},
        ):
            with self.subTest(**kwargs):
                Evento(titulo="Rascunho", **kwargs).full_clean(exclude=["area"])

    def test_full_clean_recusa_periodo_invertido(self):
        from django.core.exceptions import ValidationError

        evento = Evento(titulo="Invertido", data_inicio=HOJE, data_fim=HOJE - timedelta(days=1))
        with self.assertRaises(ValidationError):
            evento.full_clean(exclude=["area"])

    def test_banco_aceita_valor_nulo(self):
        """Metade numérica da mesma garantia: campo de dinheiro em branco passa."""
        for fabrica, nome, viola, _ in CASOS_SINAL:
            campo = next(iter(viola))
            obj = getattr(self, fabrica)()
            if not type(obj)._meta.get_field(campo).null:
                continue  # `valor_15`/`valor_30`/`valor_24h` são NOT NULL
            with self.subTest(constraint=nome):
                self.assert_banco_aceita(obj, **{campo: None})


class ValidadorDeProducaoTests(ConstraintsBase):
    """`scripts/validar_constraints_db07.py` — a régua do limite 4 do `AGENTS.md`.

    É o que o operador roda contra produção antes do deploy, então errar para mais
    é tão ruim quanto errar para menos: régua que grita lobo faz corrigir linha sã,
    ou faz ignorar o aviso.

    A primeira versão usava `filter(~constraint.condition)` — a leitura óbvia de
    "quem não satisfaz", e errada. O ORM acrescenta `IS NOT NULL` ao negar uma
    comparação, para que `exclude()` se comporte de forma intuitiva em Python; o
    efeito era acusar toda linha com o campo em branco. Contra o banco de
    desenvolvimento foram **244 falsos positivos**, num banco onde a migração
    aplica sem erro nenhum.

    O caso "acha de verdade" usa uma condição **avulsa**, não instalada no banco —
    é assim que a régua roda em produção, antes de a migração existir, e evita
    precisar de DDL que o SQLite não suporta.
    """

    def _violacoes(self, modelo, constraint):
        import importlib.util
        import pathlib as _pathlib

        caminho = (
            _pathlib.Path(__file__).resolve().parents[2]
            / "scripts"
            / "validar_constraints_db07.py"
        )
        spec = importlib.util.spec_from_file_location("validar_db07", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo._violacoes(modelo, constraint)

    def _constraint(self, modelo, nome):
        return next(c for c in modelo._meta.constraints if c.name == nome)

    def test_linha_com_campo_nulo_nao_conta_como_violacao(self):
        """O falso positivo que a primeira versão produzia."""
        evento = self._evento()
        self._gravar(evento, data_fim=None)

        self.assertEqual(
            self._violacoes(Evento, self._constraint(Evento, "evento_periodo_ordenado")),
            0,
        )

    def test_linha_que_viola_e_contada(self):
        """O contraste. Sem ele, uma régua que devolvesse sempre zero passaria."""
        from django.db.models import CheckConstraint
        from django.db.models import F
        from django.db.models import Q

        self._evento()  # data_fim = data_inicio + 2 dias
        avulsa = CheckConstraint(
            condition=Q(data_fim__lt=F("data_inicio")), name="db07_condicao_avulsa",
        )

        self.assertEqual(self._violacoes(Evento, avulsa), 1)


class TodasAsConstraintsTemTesteTests(TestCase):
    """A régua que impede esta suíte de envelhecer.

    Um `CheckConstraint` novo em qualquer modelo do projeto reprova aqui até
    ganhar um caso acima — com o par "viola" e o par "no limite", que é o que
    distingue uma constraint testada de uma constraint apenas declarada.
    """

    def test_todo_check_constraint_do_projeto_esta_coberto(self):
        from django.apps import apps
        from django.db.models import CheckConstraint

        declaradas = {
            constraint.name
            for modelo in apps.get_models()
            for constraint in modelo._meta.constraints
            if isinstance(constraint, CheckConstraint)
        }
        cobertas = {nome for _, nome, _, _ in CASOS_ORDEM + CASOS_SINAL}

        self.assertEqual(
            declaradas - cobertas,
            set(),
            "`CheckConstraint` sem caso em CASOS_ORDEM/CASOS_SINAL",
        )
        self.assertEqual(
            cobertas - declaradas,
            set(),
            "caso apontando para `CheckConstraint` que não existe mais",
        )

    def test_o_projeto_saiu_de_duas_constraints(self):
        """O número do catálogo, virado teste.

        Não é catraca de estilo: é o enunciado do `DB-07` ("2 `CheckConstraint`
        em 54 modelos") preso a uma asserção, para que a regressão apareça como
        teste vermelho e não como auditoria futura.
        """
        from django.apps import apps
        from django.db.models import CheckConstraint

        total = sum(
            1
            for modelo in apps.get_models()
            for constraint in modelo._meta.constraints
            if isinstance(constraint, CheckConstraint)
        )
        self.assertGreaterEqual(total, 26)
