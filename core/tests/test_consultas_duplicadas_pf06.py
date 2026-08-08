"""`PF-06` — a mesma consulta, idêntica, mais de uma vez na mesma requisição.

O enunciado chamava de "sintoma de consulta refeita em camada diferente", e
apontava `/usuarios/` e `/prestacoes-contas/`. A varredura das dez rotas de lista
mostrou que o pior caso era outro e não estava no enunciado: **`roteiros:index`,
com 11 consultas a mais**.

Os dois defeitos corrigidos aqui têm formas diferentes, e por isso dois testes:

1. **`roteiros`** — o presenter monta "Cidade/UF" com `cidade.estado.sigla`
   (`roteiros/presenters.py:19`) e o selector prefetchava só `destinos__cidade`.
   Cada acesso ao estado voltava ao banco.
2. **`usuarios`** — o badge da aba recontava `auth_user` depois de o `Paginator`
   ter contado o mesmo conjunto. É a "camada diferente" do enunciado, literal.

O teste conta **consultas idênticas**, não o total: um teto de total já existe em
`*/tests/test_orcamento_de_queries.py` e pega outra coisa. Aqui o alvo é a
repetição exata, que é sempre trabalho jogado fora.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cidade, Estado
from core.testing import area_de_teste, vincular_area
from roteiros.models import Roteiro, RoteiroDestino


def _duplicadas(client, url) -> dict[str, int]:
    """Quantas vezes cada SQL idêntico se repete além da primeira."""
    with CaptureQueriesContext(connection) as ctx:
        resposta = client.get(url)
    assert resposta.status_code == 200, f"{url} respondeu {resposta.status_code}"
    contagem = Counter(q["sql"] for q in ctx.captured_queries)
    return {sql: n - 1 for sql, n in contagem.items() if n > 1}


class ListaDeRoteirosTests(TestCase):
    """O pior caso, e o que o enunciado não tinha."""

    @classmethod
    def setUpTestData(cls):
        cls.area = area_de_teste(sigla="PF06")
        cls.user = get_user_model().objects.create_user(username="usuario_pf06")
        vincular_area(cls.user, cls.area, area_padrao=True)

        # Vários destinos por roteiro, e estados repetidos entre eles: é o que
        # fazia o mesmo `SELECT` de estado sair 3 ou 4 vezes.
        cls.estados = [
            Estado.objects.create(nome=f"Estado {i}", sigla=f"E{i}") for i in range(3)
        ]
        cls.cidades = [
            Cidade.objects.create(nome=f"Cidade {i}", estado=cls.estados[i % 3])
            for i in range(6)
        ]
        estados, cidades = cls.estados, cls.cidades
        # `saida_dt` no futuro: a aba padrão das listas é `futuras`
        # (`core/documento_abas.py`), e sem data o card não entra na página — a
        # primeira versão desta fixture renderizava **zero** cards e o teste
        # passava mesmo com o prefetch raso de volta.
        cls.futuro = futuro = timezone.now() + timedelta(days=3)
        for _numero in range(5):
            roteiro = Roteiro.objects.create(
                area=cls.area,
                origem_estado=estados[0],
                origem_cidade=cidades[0],
                saida_dt=futuro,
            )
            for ordem, cidade in enumerate(cidades[1:4]):
                RoteiroDestino.objects.create(
                    roteiro=roteiro, estado=cidade.estado, cidade=cidade, ordem=ordem,
                )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _consultas_de_estado(self):
        with CaptureQueriesContext(connection) as ctx:
            resposta = self.client.get(reverse("roteiros:index"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["cards"], "a lista renderizou zero cards")
        return [q for q in ctx.captured_queries if "cadastros_estado" in q["sql"]]

    def test_o_custo_de_estado_nao_cresce_com_o_numero_de_cards(self):
        """O defeito, na forma que importa: **por linha** contra **por página**.

        Sem `destinos__cidade__estado`, cada `cidade.estado.sigla` do presenter
        (`roteiros/presenters.py:19`) volta ao banco — então o custo é
        proporcional aos destinos da página. Com o prefetch, é constante.

        A asserção é sobre **crescimento**, não sobre um número absoluto, e isso
        é deliberado: `destinos__estado` e `destinos__cidade__estado` são dois
        prefetches legítimos que emitem SQL idêntico quando os ids coincidem.
        Exigir "zero consulta repetida" reprovaria a correção — foi o que
        aconteceu com a primeira versão deste teste.
        """
        poucos = len(self._consultas_de_estado())

        for _numero in range(15):
            roteiro = Roteiro.objects.create(
                area=self.area,
                origem_estado=self.estados[1],
                origem_cidade=self.cidades[2],
                saida_dt=self.futuro,
            )
            for ordem, cidade in enumerate(self.cidades[1:5]):
                RoteiroDestino.objects.create(
                    roteiro=roteiro, estado=cidade.estado, cidade=cidade, ordem=ordem,
                )

        muitos = len(self._consultas_de_estado())

        self.assertEqual(
            muitos,
            poucos,
            f"o custo de estado cresceu com a página: {poucos} → {muitos} consultas. "
            "O presenter voltou a resolver `cidade.estado` linha a linha.",
        )


class ListaDeUsuariosTests(TestCase):
    """A "camada diferente" do enunciado, literal: paginação e badge contando o mesmo."""

    @classmethod
    def setUpTestData(cls):
        cls.area = area_de_teste(sigla="PF06U")
        cls.user = get_user_model().objects.create_superuser(username="admin_pf06")
        vincular_area(cls.user, cls.area, area_padrao=True)
        for i in range(5):
            get_user_model().objects.create_user(username=f"colega{i}")

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_a_lista_nao_conta_usuarios_duas_vezes(self):
        repetidas = _duplicadas(self.client, reverse("usuarios:index"))

        contagens = {
            sql: n
            for sql, n in repetidas.items()
            if "COUNT(*)" in sql and "auth_user" in sql
        }
        self.assertEqual(
            contagens,
            {},
            f"`auth_user` foi contado duas vezes: {[sql[:70] for sql in contagens]}",
        )

    def test_com_busca_o_badge_continua_mostrando_o_total(self):
        """A metade que impede a correção de mentir.

        Com busca ativa o paginador conta o **filtrado** e o badge quer o
        **total**. Reaproveitar a contagem do paginador ali trocaria o número da
        aba pelo do filtro, em silêncio.
        """
        total = get_user_model().objects.count()

        resposta = self.client.get(reverse("usuarios:index") + "?q=colega1")

        self.assertEqual(resposta.context["total_usuarios"], total)
        self.assertLess(resposta.context["page_obj"].paginator.count, total)
