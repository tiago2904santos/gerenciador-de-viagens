import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Unidade

from planos_trabalho.forms import PlanoIdentificacaoForm
from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import HorarioAtendimento
from planos_trabalho.models import PlanoDestino
from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa
from .helpers import criar_servidor


class PlanoWizardViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_pt", password="123456")
        self.client.force_login(self.user)
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)

    def test_index_renderiza(self):
        criar_plano_maringa(self.maringa)
        response = self.client.get(reverse("planos_trabalho:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20/2026/ASCOM")

    def test_novo_cria_rascunho_numerado_e_redireciona_para_etapa_1(self):
        response = self.client.get(reverse("planos_trabalho:novo"))
        plano = PlanoTrabalho.objects.latest("pk")
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
        )
        self.assertEqual(plano.numero, 1)
        self.assertEqual(plano.sufixo_numero, "ASCOM")
        self.assertEqual(plano.status, PlanoTrabalho.STATUS_RASCUNHO)

    def test_etapas_do_wizard_renderizam(self):
        plano = criar_plano_maringa(self.maringa)
        for name in (
            "planos_trabalho:wizard_identificacao",
            "planos_trabalho:wizard_efetivo_diarias",
            "planos_trabalho:wizard_atividades",
            "planos_trabalho:wizard_documentos",
        ):
            response = self.client.get(reverse(name, args=[plano.pk]))
            self.assertEqual(response.status_code, 200, msg=name)

    def test_get_identificacao_pre_preenche_textos_padrao(self):
        plano = criar_plano_maringa(self.maringa)
        response = self.client.get(reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]))
        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode("utf-8")
        self.assertIn("Maringá/PR", conteudo)
        self.assertIn("PCPR na Comunidade", conteudo)

    def test_edicao_manual_do_texto_nao_e_sobrescrita(self):
        plano = criar_plano_maringa(self.maringa)
        response = self.client.post(
            reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
            {
                "action": "save_draft",
                "programa": "",
                "programa_outros": "",
                "destino_estado": self.maringa.estado_id,
                "destino_cidade": self.maringa.pk,
                "data_evento_inicio": "2026-06-25",
                "data_evento_fim": "2026-06-27",
                "horario_atendimento": "09:00 até 17:00",
                "contextualizacao": "Texto que o usuário escreveu à mão.",
                "consideracao_final": "",
                "contextualizacao_auto": "0",
                "consideracao_auto": "1",
                "coordenador_adm_modo": "SERVIDOR",
                "coordenador_adm": "",
                "coordenador_adm_nome_manual": "",
                "coordenador_adm_cargo_manual": "",
                "coordenador_op_modo": "SERVIDOR",
                "coordenador_op": "",
                "coordenador_op_nome_manual": "",
                "coordenador_op_cargo_manual": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        plano.refresh_from_db()
        self.assertFalse(plano.contextualizacao_auto)
        self.assertEqual(plano.contextualizacao, "Texto que o usuário escreveu à mão.")
        # Considerações continuam automáticas e refletem o destino.
        self.assertTrue(plano.consideracao_auto)
        self.assertIn("Maringá/PR", plano.consideracao_final)

    def test_post_identificacao_salva_e_preenche_textos_padrao(self):
        plano = criar_plano_maringa(self.maringa)
        programa = ProgramaSolicitante.objects.get(nome="PROGRAMA JUSTIÇA NO BAIRRO")
        servidor = criar_servidor()
        response = self.client.post(
            reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
            {
                "action": "wizard_next",
                "programa": programa.pk,
                "programa_outros": "",
                "destino_estado": self.maringa.estado_id,
                "destino_cidade": self.maringa.pk,
                "data_evento_inicio": "2026-06-25",
                "data_evento_fim": "2026-06-27",
                "horario_atendimento": "09:00 até 17:00",
                "contextualizacao": "",
                "consideracao_final": "",
                "coordenador_adm_modo": "SERVIDOR",
                "coordenador_adm": servidor.pk,
                "coordenador_adm_nome_manual": "",
                "coordenador_adm_cargo_manual": "",
                "coordenador_op_modo": "SERVIDOR",
                "coordenador_op": "",
                "coordenador_op_nome_manual": "",
                "coordenador_op_cargo_manual": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[plano.pk]),
        )
        plano.refresh_from_db()
        self.assertIn("Maringá/PR", plano.contextualizacao)
        self.assertIn("Programa Justiça no Bairro", plano.contextualizacao)
        self.assertIn("Maringá/PR", plano.consideracao_final)
        self.assertEqual(plano.coordenador_adm_id, servidor.pk)

    def test_post_identificacao_aceita_programa_outro(self):
        plano = criar_plano_maringa(self.maringa)
        response = self.client.post(
            reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
            {
                "action": "wizard_next",
                "programa": PlanoIdentificacaoForm.PROGRAMA_OUTRO_VALUE,
                "programa_outros": "Programa piloto do interior",
                "destino_estado": self.maringa.estado_id,
                "destino_cidade": self.maringa.pk,
                "data_evento_inicio": "2026-06-25",
                "data_evento_fim": "2026-06-27",
                "horario_atendimento": "09:00 até 17:00",
                "contextualizacao": "",
                "consideracao_final": "",
                "coordenador_adm_modo": "SERVIDOR",
                "coordenador_adm": "",
                "coordenador_adm_nome_manual": "",
                "coordenador_adm_cargo_manual": "",
                "coordenador_op_modo": "SERVIDOR",
                "coordenador_op": "",
                "coordenador_op_nome_manual": "",
                "coordenador_op_cargo_manual": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[plano.pk]),
        )
        plano.refresh_from_db()
        self.assertIsNone(plano.programa)
        self.assertEqual(plano.programa_outros, "Programa piloto do interior")
        self.assertIn("Programa Piloto do Interior", plano.contextualizacao)

    def test_post_identificacao_aceita_coordenador_manual_quando_servidor_nao_existe(self):
        plano = criar_plano_maringa(self.maringa)
        cargo = Cargo.objects.create(nome="ANALISTA DE PROJETOS")
        response = self.client.post(
            reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
            {
                "action": "wizard_next",
                "programa": "",
                "programa_outros": "",
                "destino_estado": self.maringa.estado_id,
                "destino_cidade": self.maringa.pk,
                "data_evento_inicio": "2026-06-25",
                "data_evento_fim": "2026-06-27",
                "horario_atendimento": "09:00 até 17:00",
                "contextualizacao": "",
                "consideracao_final": "",
                "coordenador_adm_modo": "",
                "coordenador_adm": "",
                "coordenador_adm_nome_manual": "Maria da Silva",
                "coordenador_adm_cargo_manual": cargo.nome,
                "coordenador_op_modo": "",
                "coordenador_op": "",
                "coordenador_op_nome_manual": "",
                "coordenador_op_cargo_manual": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[plano.pk]),
        )
        plano.refresh_from_db()
        self.assertEqual(plano.coordenador_adm_modo, PlanoTrabalho.COORDENADOR_MODO_MANUAL)
        self.assertIsNone(plano.coordenador_adm)
        self.assertEqual(plano.coordenador_adm_nome_manual, "Maria da Silva")
        self.assertEqual(plano.coordenador_adm_cargo_manual, cargo.nome)

    def test_post_identificacao_salva_multiplos_destinos(self):
        plano = criar_plano_maringa(self.maringa)
        response = self.client.post(
            reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
            {
                "action": "wizard_next",
                "programa": "",
                "programa_outros": "",
                "destino_estado": self.maringa.estado_id,
                "destino_cidade": self.maringa.pk,
                "destino_estado_1": self.maringa.estado_id,
                "destino_cidade_1": self.curitiba.pk,
                "data_evento_inicio": "2026-06-25",
                "data_evento_fim": "2026-06-27",
                "horario_atendimento": "09:00 até 17:00",
                "contextualizacao": "",
                "consideracao_final": "",
                "coordenador_adm_modo": "SERVIDOR",
                "coordenador_adm": "",
                "coordenador_adm_nome_manual": "",
                "coordenador_adm_cargo_manual": "",
                "coordenador_op_modo": "SERVIDOR",
                "coordenador_op": "",
                "coordenador_op_nome_manual": "",
                "coordenador_op_cargo_manual": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[plano.pk]),
        )
        plano.refresh_from_db()
        destinos = list(PlanoDestino.objects.filter(plano=plano).order_by("ordem").values_list("cidade__nome", flat=True))
        self.assertEqual(destinos, ["MARINGÁ", "CURITIBA"])
        self.assertEqual(plano.destino_cidade, self.maringa)

    def test_autosave_identificacao(self):
        plano = criar_plano_maringa(self.maringa)
        url = reverse("planos_trabalho:identificacao_autosave", args=[plano.pk])
        payload = {
            "model": "plano_trabalho",
            "object_id": str(plano.pk),
            "dirty_fields": ["horario_atendimento"],
            "fields": {"horario_atendimento": "08:00 até 16:00"},
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        plano.refresh_from_db()
        self.assertEqual(plano.horario_atendimento, "08:00 até 16:00")

    def test_post_efetivo_diarias_salva_e_calcula_snapshot(self):
        plano = criar_plano_maringa(self.maringa, efetivo=6)
        efetivo = plano.efetivos.first()
        unidade = efetivo.unidade
        response = self.client.post(
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[plano.pk]),
            {
                "action": "wizard_next",
                "efetivo-TOTAL_FORMS": "1",
                "efetivo-INITIAL_FORMS": "1",
                "efetivo-MIN_NUM_FORMS": "1",
                "efetivo-MAX_NUM_FORMS": "1000",
                "efetivo-0-id": efetivo.pk,
                "efetivo-0-plano": plano.pk,
                "efetivo-0-unidade": unidade.pk,
                "efetivo-0-cargo": efetivo.cargo_id,
                "efetivo-0-quantidade": "6",
                "saida_sede_data": "2026-06-24",
                "saida_sede_hora": "07:00",
                "chegada_sede_data": "2026-06-28",
                "chegada_sede_hora": "14:00",
            },
        )
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_atividades", args=[plano.pk]),
        )
        plano.refresh_from_db()
        self.assertEqual(plano.diarias_composicao, "4 x 100% + 1 x 15%")
        self.assertEqual(str(plano.diarias_valor_total), "7234.68")

    def test_post_efetivo_diarias_aceita_multiplas_linhas_com_unidades_distintas(self):
        plano = criar_plano_maringa(self.maringa, efetivo=6)
        efetivo = plano.efetivos.first()
        unidade_extra = Unidade.objects.create(nome="Delegacia Regional", sigla="DR")
        cargo_extra = Cargo.objects.create(nome="Investigador")
        response = self.client.post(
            reverse("planos_trabalho:wizard_efetivo_diarias", args=[plano.pk]),
            {
                "action": "wizard_next",
                "efetivo-TOTAL_FORMS": "2",
                "efetivo-INITIAL_FORMS": "1",
                "efetivo-MIN_NUM_FORMS": "1",
                "efetivo-MAX_NUM_FORMS": "1000",
                "efetivo-0-id": efetivo.pk,
                "efetivo-0-plano": plano.pk,
                "efetivo-0-unidade": efetivo.unidade_id,
                "efetivo-0-cargo": efetivo.cargo_id,
                "efetivo-0-quantidade": "6",
                "efetivo-1-id": "",
                "efetivo-1-plano": plano.pk,
                "efetivo-1-unidade": unidade_extra.pk,
                "efetivo-1-cargo": cargo_extra.pk,
                "efetivo-1-quantidade": "2",
                "saida_sede_data": "2026-06-24",
                "saida_sede_hora": "07:00",
                "chegada_sede_data": "2026-06-28",
                "chegada_sede_hora": "14:00",
            },
        )
        self.assertRedirects(
            response,
            reverse("planos_trabalho:wizard_atividades", args=[plano.pk]),
        )
        plano.refresh_from_db()
        self.assertEqual(plano.efetivos.count(), 2)

    def test_api_calcular_diarias_ao_vivo(self):
        plano = criar_plano_maringa(self.maringa, efetivo=6)
        url = reverse("planos_trabalho:api_calcular_diarias", args=[plano.pk])
        payload = {
            "saida_sede_data": "2026-06-24",
            "saida_sede_hora": "07:00",
            "chegada_sede_data": "2026-06-28",
            "chegada_sede_hora": "14:00",
            "total_efetivo": 6,
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["composicao"], "4 x 100% + 1 x 15%")
        self.assertEqual(data["valor_total_display"], "7.234,68")

    def test_baixar_docx_gera_documento_e_marca_gerado(self):
        plano = self._plano_completo()
        response = self.client.get(
            reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:2], b"PK")
        plano.refresh_from_db()
        self.assertEqual(plano.status, PlanoTrabalho.STATUS_GERADO)

    def test_baixar_documento_bloqueado_quando_incompleto(self):
        plano = PlanoTrabalho.objects.create()
        response = self.client.get(
            reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
        )
        self.assertEqual(response.status_code, 302)

    def test_excluir_plano(self):
        plano = criar_plano_maringa(self.maringa)
        response = self.client.post(reverse("planos_trabalho:excluir", args=[plano.pk]))
        self.assertRedirects(response, reverse("planos_trabalho:index"))
        self.assertFalse(PlanoTrabalho.objects.filter(pk=plano.pk).exists())

    def _plano_completo(self):
        from planos_trabalho.services import aplicar_textos_padrao
        from planos_trabalho.services import atualizar_snapshot_diarias

        plano = criar_plano_maringa(self.maringa, efetivo=6)
        plano.coordenador_adm = criar_servidor()
        aplicar_textos_padrao(plano)
        plano.save()
        atualizar_snapshot_diarias(plano)
        return plano


class ProgramasCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_prog", password="123456")
        self.client.force_login(self.user)

    def test_seed_inicial_dos_programas(self):
        nomes = set(ProgramaSolicitante.objects.values_list("nome", flat=True))
        self.assertIn("PROGRAMA PARANÁ EM AÇÃO", nomes)
        self.assertIn("PROGRAMA JUSTIÇA NO BAIRRO", nomes)
        self.assertIn("PCPR NA COMUNIDADE", nomes)

    def test_crud_programa(self):
        response = self.client.post(
            reverse("planos_trabalho:programa_novo"),
            {"nome": "Operação Verão", "ativo": "on", "ordem": "50"},
        )
        self.assertRedirects(response, reverse("planos_trabalho:programas_index"))
        programa = ProgramaSolicitante.objects.get(nome="OPERAÇÃO VERÃO")

        response = self.client.post(
            reverse("planos_trabalho:programa_editar", args=[programa.pk]),
            {"nome": "Operação Verão Maior", "ativo": "on", "ordem": "55"},
        )
        self.assertRedirects(response, reverse("planos_trabalho:programas_index"))
        programa.refresh_from_db()
        self.assertEqual(programa.nome, "OPERAÇÃO VERÃO MAIOR")

        response = self.client.post(
            reverse("planos_trabalho:programa_excluir", args=[programa.pk]),
        )
        self.assertRedirects(response, reverse("planos_trabalho:programas_index"))
        self.assertFalse(ProgramaSolicitante.objects.filter(pk=programa.pk).exists())


class HorariosCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_horario", password="123456")
        self.client.force_login(self.user)

    def test_seed_inicial_dos_horarios(self):
        faixas = set(HorarioAtendimento.objects.values_list("faixa", flat=True))
        self.assertIn("09:00 até 17:00", faixas)
        self.assertIn("08:00 até 16:00", faixas)

    def test_crud_horario(self):
        response = self.client.post(
            reverse("planos_trabalho:horario_novo"),
            {"faixa": "11:00 até 19:00", "ativo": "on", "ordem": "40"},
        )
        self.assertRedirects(response, reverse("planos_trabalho:horarios_index"))
        horario = HorarioAtendimento.objects.get(faixa="11:00 até 19:00")

        response = self.client.post(
            reverse("planos_trabalho:horario_editar", args=[horario.pk]),
            {"faixa": "11:30 até 19:30", "ativo": "on", "ordem": "45"},
        )
        self.assertRedirects(response, reverse("planos_trabalho:horarios_index"))
        horario.refresh_from_db()
        self.assertEqual(horario.faixa, "11:30 até 19:30")

        response = self.client.post(
            reverse("planos_trabalho:horario_excluir", args=[horario.pk]),
        )
        self.assertRedirects(response, reverse("planos_trabalho:horarios_index"))
        self.assertFalse(HorarioAtendimento.objects.filter(pk=horario.pk).exists())
