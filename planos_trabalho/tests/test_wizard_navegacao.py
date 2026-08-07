"""BE-01 — os botões do wizard de plano de trabalho precisam fazer o que dizem.

`planos_trabalho/view_helpers.py` lia apenas `post.get("action")` e caía no
default. Os rodapés do wizard vêm de `components/ui/layouts/card_footer_actions.html`,
que emite `name="wizard_action"` — e não existe **nenhum** `name="action"` nos
templates do app. Resultado: o valor do botão nunca chegava.

Duas consequências, ambas visíveis para o usuário:

- em `wizard_documentos` (default `save_draft`), "Finalizar plano" caía no
  `redirect` final e **recarregava a mesma página, sem mensagem**;
- em `wizard_atividades` (default `wizard_next`), "Voltar" entrava no ramo de
  avançar e **empurrava o usuário para a etapa seguinte**.

`oficios/view_helpers.py` lê `wizard_action` primeiro, com comentário explicando
que `name="action"` colide com `form.action` no DOM. As duas cópias divergiram.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from planos_trabalho.models import PlanoTrabalho
from core.testing import vincular_area

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa


class WizardNavegacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="wizard_nav", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa)

    def test_voltar_nas_atividades_volta_para_efetivo_e_nao_avanca(self):
        response = self.client.post(
            reverse("planos_trabalho:wizard_atividades", args=[self.plano.pk]),
            {"wizard_action": "wizard_back"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[self.plano.pk]),
            msg="'Voltar' levou o usuário para a etapa seguinte",
        )

    def test_avancar_nas_atividades_continua_avancando(self):
        """A correção não pode inverter o botão que já funcionava."""
        response = self.client.post(
            reverse("planos_trabalho:wizard_atividades", args=[self.plano.pk]),
            {"wizard_action": "wizard_next"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("planos_trabalho:wizard_documentos", args=[self.plano.pk]),
        )

    def test_finalizar_marca_o_plano_como_gerado(self):
        # Um plano sem pendências: coordenador informado e diárias já calculadas.
        self.plano.coordenador_adm_nome_manual = "Coordenadora Administrativa"
        self.plano.coordenador_adm_cargo_manual = "Delegada"
        self.plano.diarias_valor_total = Decimal("1234.56")
        self.plano.save(
            update_fields=[
                "coordenador_adm_nome_manual",
                "coordenador_adm_cargo_manual",
                "diarias_valor_total",
            ]
        )
        self.assertNotEqual(self.plano.status, PlanoTrabalho.STATUS_GERADO)

        response = self.client.post(
            reverse("planos_trabalho:wizard_documentos", args=[self.plano.pk]),
            {"wizard_action": "finalizar"},
        )

        self.plano.refresh_from_db()
        self.assertEqual(
            self.plano.status,
            PlanoTrabalho.STATUS_GERADO,
            msg="'Finalizar plano' não finalizou — o plano continuou como estava",
        )
        self.assertEqual(response.status_code, 302)

    def test_finalizar_com_pendencia_explica_o_motivo_em_vez_de_recarregar_calado(self):
        """O sintoma real do BE-01 era o silêncio.

        Como a ação nunca chegava, o ramo `finalizar` era inalcançável: o clique
        recarregava a mesma página sem finalizar **e sem dizer por quê**. Agora, se
        houver pendência, o usuário lê qual é.
        """
        response = self.client.post(
            reverse("planos_trabalho:wizard_documentos", args=[self.plano.pk]),
            {"wizard_action": "finalizar"},
            follow=True,
        )

        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("coordenador" in m.lower() for m in mensagens),
            msg=f"esperava a pendência explicada ao usuário, veio: {mensagens}",
        )

    def test_voltar_nos_documentos_volta_para_atividades(self):
        response = self.client.post(
            reverse("planos_trabalho:wizard_documentos", args=[self.plano.pk]),
            {"wizard_action": "wizard_back"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("planos_trabalho:wizard_atividades", args=[self.plano.pk]),
        )

    def test_o_nome_legado_action_continua_sendo_aceito(self):
        """Compatibilidade: se algum template antigo ainda enviar `action`, vale."""
        response = self.client.post(
            reverse("planos_trabalho:wizard_atividades", args=[self.plano.pk]),
            {"action": "wizard_back"},
        )

        self.assertEqual(
            response["Location"],
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[self.plano.pk]),
        )
