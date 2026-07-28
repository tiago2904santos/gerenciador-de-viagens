"""Fatia 4/6 de T-01 — relatório técnico e valor de diária por servidor.

Primeira fatia em que **dinheiro** aparece. É a rede que a Etapa 3 vai precisar:
o `N-01` (tabela de diárias fixada no código, sem vigência) mexe justamente no
valor que chega aqui, e sem estes testes a mudança seria feita no escuro.

Duas coisas ficam registradas, ambas caracterizadas e não corrigidas:

* o valor de diária por servidor é **texto livre** — `CharField` sem validação,
  só `normalize_spaces`. Qualquer string persiste e chega ao documento e ao
  texto de WhatsApp (`NOVO-10`);
* os campos de custeio do RT têm dois regimes: os de lista fechada só aceitam
  valor do conjunto permitido, os livres aceitam qualquer texto.
"""

from __future__ import annotations

import json

from django.test import TestCase
from django.urls import reverse

from prestacoes_contas.models import PrestacaoServidor
from prestacoes_contas.models import RelatorioTecnico
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin


class DiariaOverrideTests(PrestacaoFixturesMixin, TestCase):
    """O valor que difere do padrão, por servidor."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=1)
        self.ps = self.fixture.prestacoes_servidor[0]
        self.relatorio = RelatorioTecnico.objects.create(prestacao=self.fixture.prestacao)

    def autosave_rt(self, relatorio=None, **campos):
        relatorio = relatorio or self.relatorio
        payload = {
            "model": "relatorio_tecnico",
            "object_id": str(relatorio.pk),
            "dirty_fields": list(campos),
            "fields": campos,
        }
        return self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[relatorio.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_override_persiste_por_servidor_sem_afetar_os_demais(self):
        outro_servidor = self.criar_servidor("Segundo Servidor")
        dupla = self.criar_prestacao(numero=2, servidores=[self.ps.servidor, outro_servidor])
        relatorio = RelatorioTecnico.objects.create(prestacao=dupla.prestacao)
        ps_a, ps_b = dupla.prestacoes_servidor

        self.autosave_rt(relatorio, **{f"ps-{ps_a.pk}-diaria_valor_override": "  350,00  "})

        ps_a.refresh_from_db()
        ps_b.refresh_from_db()
        self.assertEqual(ps_a.diaria_valor_override, "350,00")
        self.assertEqual(ps_b.diaria_valor_override, "")

    def test_override_aceita_qualquer_texto_sem_validacao(self):
        """Caracteriza `NOVO-10`, deliberadamente — não é aprovação.

        `diaria_valor_override` é CharField sem validador. Um erro de digitação
        vira o valor de diária impresso no relatório técnico do servidor e no
        texto enviado por WhatsApp, sem nada avisar.
        """
        for entrada in ("abc", "R$ mil reais", "-90", "350,00,00"):
            with self.subTest(entrada=entrada):
                self.autosave_rt(
                    **{f"ps-{self.ps.pk}-diaria_valor_override": entrada}
                )
                self.ps.refresh_from_db()
                self.assertEqual(self.ps.diaria_valor_override, entrada)

    def test_override_em_branco_volta_a_usar_o_valor_compartilhado(self):
        self.autosave_rt(**{f"ps-{self.ps.pk}-diaria_valor_override": "500,00"})
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.diaria_valor_override, "500,00")

        self.autosave_rt(**{f"ps-{self.ps.pk}-diaria_valor_override": "   "})

        self.ps.refresh_from_db()
        self.assertEqual(self.ps.diaria_valor_override, "")

    def test_override_nao_alcanca_servidor_de_outra_prestacao(self):
        """O `filter(prestacao=prestacao)` impede escrita cruzada entre ofícios."""
        vizinha = self.criar_prestacao(numero=3)
        ps_vizinho = vizinha.prestacoes_servidor[0]

        self.autosave_rt(
            **{f"ps-{ps_vizinho.pk}-diaria_valor_override": "999,00"}
        )

        ps_vizinho.refresh_from_db()
        self.assertEqual(ps_vizinho.diaria_valor_override, "")

    def test_autosave_de_rt_de_outra_area_responde_404(self):
        alheia = self.criar_prestacao(numero=90, area=self.outra_area)
        relatorio_alheio = RelatorioTecnico.objects.create(prestacao=alheia.prestacao)

        response = self.autosave_rt(relatorio_alheio, motivo="INVASAO")

        self.assertEqual(response.status_code, 404)
        relatorio_alheio.refresh_from_db()
        self.assertEqual(relatorio_alheio.motivo, "")


class RelatorioTecnicoCamposTests(PrestacaoFixturesMixin, TestCase):
    """Os campos do RT: texto livre e custeio de lista fechada."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=1)
        self.relatorio = RelatorioTecnico.objects.create(prestacao=self.fixture.prestacao)

    def autosave_rt(self, **campos):
        payload = {
            "model": "relatorio_tecnico",
            "object_id": str(self.relatorio.pk),
            "dirty_fields": list(campos),
            "fields": campos,
        }
        return self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[self.relatorio.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_campos_narrativos_persistem_normalizados(self):
        self.autosave_rt(
            motivo="  Operação   conjunta  ",
            atividade="Fiscalização",
            conclusao="Concluída",
        )

        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.motivo, "Operação conjunta")
        self.assertEqual(self.relatorio.atividade, "Fiscalização")
        self.assertEqual(self.relatorio.conclusao, "Concluída")

    def test_campo_fora_da_lista_permitida_e_ignorado(self):
        """`filter_allowed_fields` é a fronteira: só passa o que está declarado."""
        self.autosave_rt(motivo="Guardado", campo_inventado="Ignorado")

        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.motivo, "Guardado")
        self.assertFalse(hasattr(self.relatorio, "campo_inventado"))

    def test_campo_nao_marcado_como_sujo_nao_e_gravado(self):
        """O autosave só grava o que o formulário declarou alterado."""
        payload = {
            "model": "relatorio_tecnico",
            "object_id": str(self.relatorio.pk),
            "dirty_fields": [],
            "fields": {"motivo": "Nao deveria entrar"},
        }
        self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[self.relatorio.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.motivo, "")

    def test_payload_de_outro_modelo_e_recusado(self):
        response = self.client.post(
            reverse("prestacoes_contas:rt_autosave", args=[self.relatorio.pk]),
            data=json.dumps({"model": "prestacao_servidor", "fields": {"motivo": "X"}}),
            content_type="application/json",
        )

        self.assertFalse(response.json()["ok"])
        self.relatorio.refresh_from_db()
        self.assertEqual(self.relatorio.motivo, "")
