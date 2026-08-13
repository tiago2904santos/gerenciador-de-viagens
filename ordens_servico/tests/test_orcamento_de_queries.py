"""Caracterização do custo de banco das telas de Ordem de Serviço, antes do `P-01`.

Mesmo raciocínio dos testes equivalentes em `eventos` e `termos`: a camada de
selectors muda *onde* a consulta mora, não *qual* consulta roda.

O app já tem `test_list_performance.py`, mas ele responde a outra pergunta — se o
custo **cresce** com o volume, com teto de 140 para uma página que custa bem
menos. Um refactor que enfiasse um N+1 dentro dessa folga passaria lá e falha
aqui, porque aqui a comparação é de igualdade.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from oficios.models import Oficio
from ordens_servico.models import OrdemServico
from core.testing import area_de_teste
from core.testing import vincular_area


class OrcamentoDeQueriesOrdemServicoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(nome="Parana", sigla="PR")
        cidades = [
            Cidade.objects.create(nome=nome, estado=estado, uf="PR")
            for nome in ("Curitiba", "Londrina")
        ]
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Investigador")
        unidade = Unidade.objects.create(area=area_de_teste(), nome="Unidade", sigla="UN")
        servidores = [
            Servidor.objects.create(area=area_de_teste(), 
                nome=f"Servidor {numero}",
                cargo=cargo,
                unidade=unidade,
                cpf=f"2222222222{numero}",
                rg=f"765432{numero}",
            )
            for numero in range(3)
        ]

        inicio = timezone.localdate() - timedelta(days=3)
        for numero in range(1, 26):
            ordem = OrdemServico.objects.create(area=area_de_teste(), 
                numero=numero,
                ano=2026,
                motivo="Apoio logistico ao evento institucional.",
                data_evento_inicio=inicio,
                data_evento_fim=inicio + timedelta(days=1),
            )
            # O card le destinos, servidores e oficios vinculados. Sem os tres
            # o teste nao exercita os `prefetch_related` da lista — foi essa
            # cegueira que escondeu o `NOVO-13` na lista de Plano de Trabalho.
            ordem.servidores.set(servidores)
            ordem.destinos.set(cidades)
            oficio = Oficio.objects.create(area=area_de_teste(), motorista=servidores[0])
            ordem.oficios.set([oficio])
            if numero == 1:
                cls.ordem = ordem

    def setUp(self):
        user = get_user_model().objects.create_user(username="os_orcamento")
        self.client.force_login(user)
        vincular_area(user)
        # Aquecimento: a primeira leitura do singleton de configuracao e da
        # sessao custa queries que nao sao da tela medida.
        self.client.get(reverse("ordens_servico:index") + "?aba=atuais")

    def _contar(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(queries), queries

    def test_a_lista_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("ordens_servico:index") + "?aba=atuais")

        self.assertEqual(
            total,
            self.QUERIES_LISTA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_lista_com_busca_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(
            reverse("ordens_servico:index") + "?aba=atuais&q=Apoio"
        )

        self.assertEqual(
            total,
            self.QUERIES_LISTA_BUSCA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_o_formulario_de_edicao_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(
            reverse("ordens_servico:editar", args=[self.ordem.pk])
        )

        self.assertEqual(
            total,
            self.QUERIES_EDITAR,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    # Medidos no `main`. A primeira leitura (P-01) era 138/138/27 com este
    # fixture; o `NOVO-07` derrubou a lista para 22 ao parar de consultar por
    # card. O numero so desce daqui: se subir, alguem devolveu uma consulta
    # para dentro do laco dos cards.

    # `PF-03` (07/08/2026): a sessão saiu do caminho de escrita de toda requisição
    # (`cached_db` + `SESSION_SAVE_EVERY_REQUEST = False` + renovação periódica).
    # Em regime, some 1 leitura + 1 escrita + 2 comandos de transação = **-4**.
    # Onde o corte é **-1**, o teste mede a **primeira** requisição depois do
    # login: ali `core/tenancy.py:52` grava a área na sessão, que por isso é
    # salva de qualquer jeito, e só a leitura é economizada.
    # NOVO-50: as quatro contagens de aba são uma agregação, -3 consultas.
    QUERIES_LISTA = 12
    QUERIES_LISTA_BUSCA = 12
    # 26 -> 30 na edicao, sem N+1: a lista segue em 22, entao nada voltou para
    # dentro do laco dos cards. Os quatro sao custo constante da previa de
    # destinos, que resolve a sede das Configuracoes e rele o singleton por
    # request (4x ConfiguracaoSistema + 4x AreaTrabalho). Registrado NOVO-27.
    QUERIES_EDITAR = 20
