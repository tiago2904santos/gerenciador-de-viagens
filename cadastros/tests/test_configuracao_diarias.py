"""A seção de valores de diária na tela de configurações (N-01, parte 3).

A tela é o ponto onde a decisão de produto vira interface: o operador digita
**um** valor e os outros dois aparecem. Estes testes garantem que a interface
não abre caminho de entrada que o modelo não aceite — 15% e 30% são derivados
no servidor, e nenhum POST consegue contradizê-los.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import TabelaDiaria
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class ConfiguracaoDiariasTests(TestCase):
    def setUp(self):
        # Sem senha: o acesso é por force_login, então uma senha aqui só
        # criaria um literal para o scanner de segredos reclamar.
        #
        # `DB-01`: superusuário porque a partir dele só um administrador do
        # sistema altera a tabela nacional de diárias. O que estes testes
        # cobrem é o **formulário** — 15% e 30% derivados no servidor, valor
        # zero recusado, vigência duplicada recusada —, não a permissão; quem
        # cobre a permissão é `test_portao_diarias.py`. Sem isto, todos eles
        # passariam a medir o 403 e parariam de medir a regra de dinheiro.
        self.user = get_user_model().objects.create_superuser(
            username="config_diarias", email="config@exemplo.gov.br"
        )
        self.area = AreaTrabalho.objects.create(nome="Área Config", sigla="CFG")
        VinculoUsuarioArea.objects.create(
            usuario=self.user, area=self.area, area_padrao=True, ativo=True
        )
        self.client.force_login(self.user)
        self.url = reverse("cadastros:configuracao_aba", kwargs={"aba": "roteiros"})

    def postar(self, **campos):
        dados = {"form_id": "diarias"}
        dados.update(campos)
        return self.client.post(self.url, dados)

    def test_a_tela_mostra_a_secao_e_as_vigencias_cadastradas(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valores de diária")
        # A semente da migração aparece na tabela.
        self.assertContains(response, "371,26")

    def test_gravar_uma_vigencia_deriva_os_percentuais_no_servidor(self):
        self.postar(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio="2026-09-01",
            valor_24h="400.00",
        )

        nova = TabelaDiaria.objects.get(
            faixa=TabelaDiaria.FAIXA_CAPITAL, vigencia_inicio=date(2026, 9, 1)
        )
        self.assertEqual(nova.valor_24h, Decimal("400.00"))
        self.assertEqual(nova.valor_15, Decimal("60.00"))
        self.assertEqual(nova.valor_30, Decimal("120.00"))

    def test_post_com_percentuais_forjados_nao_os_grava(self):
        """A interface não é a garantia — o servidor é.

        Mesmo que alguém envie valor_15 e valor_30 direto no POST, o modelo
        deriva do valor de 24 horas no save(). Sem isso, o campo "somente
        leitura" seria só uma sugestão para quem não abre o DevTools.
        """
        self.postar(
            faixa=TabelaDiaria.FAIXA_INTERIOR,
            vigencia_inicio="2026-09-01",
            valor_24h="100.00",
            valor_15="99.99",
            valor_30="88.88",
        )

        nova = TabelaDiaria.objects.get(
            faixa=TabelaDiaria.FAIXA_INTERIOR, vigencia_inicio=date(2026, 9, 1)
        )
        self.assertEqual(nova.valor_15, Decimal("15.00"))
        self.assertEqual(nova.valor_30, Decimal("30.00"))

    def test_valor_zero_e_recusado_com_mensagem(self):
        response = self.postar(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio="2026-09-01",
            valor_24h="0",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "maior que zero")
        self.assertFalse(
            TabelaDiaria.objects.filter(vigencia_inicio=date(2026, 9, 1)).exists()
        )

    def test_vigencia_duplicada_e_recusada_antes_do_banco(self):
        """O formulário explica; a constraint garante. Aqui vale a explicação."""
        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio=date(2026, 9, 1),
            valor_24h=Decimal("400.00"),
        )

        response = self.postar(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio="2026-09-01",
            valor_24h="500.00",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe uma vigência")
        self.assertEqual(
            TabelaDiaria.objects.get(
                faixa=TabelaDiaria.FAIXA_CAPITAL, vigencia_inicio=date(2026, 9, 1)
            ).valor_24h,
            Decimal("400.00"),
        )

    def test_gravar_diarias_nao_altera_as_outras_secoes(self):
        """Cada seção posta com seu próprio form_id e não pisa nas demais."""
        from cadastros.models import ConfiguracaoSistema

        config = ConfiguracaoSistema.get_for_area(self.area)
        config.nome_orgao = "Órgão Original"
        config.save()
        config.refresh_from_db()
        # O modelo normaliza o texto ao gravar; o que importa aqui é que o
        # valor gravado sobreviva ao POST da outra seção, seja ele qual for.
        antes = config.nome_orgao

        self.postar(
            faixa=TabelaDiaria.FAIXA_BRASILIA,
            vigencia_inicio="2026-09-01",
            valor_24h="500.00",
        )

        config.refresh_from_db()
        self.assertEqual(config.nome_orgao, antes)
        self.assertTrue(
            TabelaDiaria.objects.filter(
                faixa=TabelaDiaria.FAIXA_BRASILIA, vigencia_inicio=date(2026, 9, 1)
            ).exists()
        )
