"""O que as telas de catálogo do Plano de Trabalho fazem hoje, antes do `P-02`.

Os quatro catálogos (atividades, presets, programas, horários) repetem o mesmo
CRUD com variações pequenas: dois têm busca, um tem "definir padrão", dois
carregam `?next=` para voltar ao wizard, e cada um tem sua própria frase de
sucesso. A fábrica de `core/catalog.py` precisa reproduzir tudo isso — e a única
forma de saber que reproduziu é ter o comportamento fixado antes.

Este arquivo não julga se o comportamento atual é bom. Ele descreve.
As mensagens são comparadas literalmente de propósito: "Atividade cadastrada." e
"Programa cadastrado." não são a mesma frase, e trocar uma pela outra na
migração seria uma regressão silenciosa.

Dois fatos que os testes tiveram que absorver, e que a migração precisa manter:

- **os catálogos vêm semeados por migração de dados** — 11 atividades
  (`0008_seed_atividades_plano_trabalho`), 3 horários e 3 programas. Por isso as
  asserções são de presença e ausência, nunca de contagem absoluta;
- **`ProgramaSolicitante` e `PresetAtividadesPlanoTrabalho` gravam o nome em
  caixa alta** (`normalize_upper` no `save`); `AtividadePlanoTrabalho` e
  `HorarioAtendimento` não. As mensagens de sucesso citam o valor **gravado**.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from planos_trabalho.models import AtividadePlanoTrabalho
from planos_trabalho.models import HorarioAtendimento
from planos_trabalho.models import PresetAtividadesPlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante


class CatalogoCaracterizacaoMixin:
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(username=f"cat_{self.url_index}")
        )

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def _index(self, **params):
        url = reverse(self.url_index)
        if params:
            url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        return url


class AtividadesTests(CatalogoCaracterizacaoMixin, TestCase):
    url_index = "planos_trabalho:atividades_index"

    def _criar(self, nome="Palestra", meta="Meta X", recurso="Sala", codigo=None):
        # `codigo` e unico e o default e vazio: duas atividades sem codigo
        # colidem. A view gera o codigo a partir do nome; aqui e explicito.
        return AtividadePlanoTrabalho.objects.create(
            nome=nome,
            meta=meta,
            recurso_necessario=recurso,
            codigo=codigo or nome.split()[0].upper(),
        )

    def test_lista_abre_e_entrega_as_linhas(self):
        self._criar(nome="Zebra caracterizacao")

        response = self.client.get(self._index())

        self.assertEqual(response.status_code, 200)
        titulos = [linha["title"] for linha in response.context["linhas"]]
        self.assertIn("Zebra caracterizacao", titulos)
        self.assertEqual(response.context["page_title"], "Gerenciamento de atividades")

    def test_a_busca_filtra_por_nome(self):
        self._criar(nome="Zebra caracterizacao")
        self._criar(nome="Girafa caracterizacao")

        response = self.client.get(self._index(q="zebra"))

        self.assertEqual(
            [linha["title"] for linha in response.context["linhas"]],
            ["Zebra caracterizacao"],
        )

    def test_criacao_redireciona_e_avisa(self):
        response = self.client.post(
            reverse(self.url_index),
            {"nome": "Nova atividade", "meta": "Meta", "recurso_necessario": "Recurso"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(AtividadePlanoTrabalho.objects.filter(nome="Nova atividade").exists())
        self.assertIn("Atividade cadastrada.", self._mensagens(response))

    def test_edicao_inline_salva_e_avisa(self):
        atividade = self._criar(nome="Zebra caracterizacao")

        response = self.client.post(
            reverse("planos_trabalho:atividade_editar", args=[atividade.pk]),
            {"nome": "Zebra editada", "meta": "Meta", "recurso_necessario": "Sala"},
        )

        atividade.refresh_from_db()
        self.assertEqual(atividade.nome, "Zebra editada")
        self.assertIn("Atividade atualizada.", self._mensagens(response))

    def test_exclusao_por_post_remove_e_avisa(self):
        atividade = self._criar(nome="Zebra caracterizacao")

        response = self.client.post(
            reverse("planos_trabalho:atividade_excluir", args=[atividade.pk])
        )

        self.assertFalse(AtividadePlanoTrabalho.objects.filter(pk=atividade.pk).exists())
        self.assertIn(
            "Atividade “Zebra caracterizacao” excluída.", self._mensagens(response)
        )

    def test_exclusao_por_get_mostra_a_confirmacao(self):
        atividade = self._criar(nome="Zebra caracterizacao")

        response = self.client.get(
            reverse("planos_trabalho:atividade_excluir", args=[atividade.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(AtividadePlanoTrabalho.objects.filter(pk=atividade.pk).exists())

    def test_o_next_do_wizard_sobrevive_a_criacao(self):
        wizard = reverse("planos_trabalho:index")
        destino = "/planos-trabalho/9/atividades/"

        response = self.client.get(self._index(next=destino))
        self.assertEqual(response.context["back_url"], destino)
        self.assertEqual(response.context["quick_add_next_url"], destino)
        self.assertEqual(response.context["back_label"], "Voltar pra plano de trabalho")

        response = self.client.post(
            f"{reverse(self.url_index)}?next={destino}",
            {"nome": "Com next", "meta": "M", "recurso_necessario": "R", "next": destino},
        )
        self.assertIn("next=", response["Location"])

        # Sem `next`, o rótulo e a URL de volta são os da própria lista.
        response = self.client.get(self._index())
        self.assertEqual(response.context["back_url"], wizard)
        self.assertEqual(response.context["quick_add_next_url"], "")
        self.assertEqual(response.context["back_label"], "Voltar")


class PresetsTests(CatalogoCaracterizacaoMixin, TestCase):
    url_index = "planos_trabalho:presets_index"

    def _criar(self, nome="Preset A", **kwargs):
        return PresetAtividadesPlanoTrabalho.objects.create(nome=nome, **kwargs)

    def test_lista_abre_com_resumo_das_atividades(self):
        preset = self._criar()
        preset.atividades.set(
            [
                AtividadePlanoTrabalho.objects.create(
                    nome="Palestra caracterizacao", meta="M", codigo="PALESTRACAR"
                )
            ]
        )

        response = self.client.get(self._index())

        linha = response.context["linhas"][0]
        # O model grava o nome em caixa alta.
        self.assertEqual(linha["title"], "PRESET A")
        self.assertIn("Palestra caracterizacao", str(linha["meta"]))

    def test_criacao_avisa_com_a_frase_do_preset(self):
        atividade = AtividadePlanoTrabalho.objects.create(
            nome="Atividade do preset", meta="M", codigo="ATIVPRESET"
        )

        response = self.client.post(
            reverse(self.url_index),
            {"nome": "Preset novo", "atividades": [atividade.pk]},
        )

        self.assertIn("Preset cadastrado.", self._mensagens(response))
        self.assertTrue(
            PresetAtividadesPlanoTrabalho.objects.filter(nome="PRESET NOVO").exists()
        )

    def test_definir_padrao_marca_e_avisa(self):
        preset = self._criar()

        response = self.client.post(
            reverse("planos_trabalho:preset_definir_padrao", args=[preset.pk])
        )

        preset.refresh_from_db()
        self.assertTrue(preset.is_padrao)
        self.assertIn("Preset “PRESET A” definido como padrão.", self._mensagens(response))

    def test_o_padrao_perde_o_link_de_definir_padrao(self):
        self._criar(is_padrao=True)

        linha = self.client.get(self._index()).context["linhas"][0]

        self.assertIsNone(linha["set_default_url"])

    def test_exclusao_remove_e_avisa(self):
        preset = self._criar()

        response = self.client.post(
            reverse("planos_trabalho:preset_excluir", args=[preset.pk])
        )

        self.assertFalse(PresetAtividadesPlanoTrabalho.objects.filter(pk=preset.pk).exists())
        self.assertIn("Preset “PRESET A” excluído.", self._mensagens(response))


class ProgramasTests(CatalogoCaracterizacaoMixin, TestCase):
    url_index = "planos_trabalho:programas_index"

    def test_lista_abre_sem_busca(self):
        ProgramaSolicitante.objects.create(nome="PROGRAMA A", ordem=9)

        response = self.client.get(self._index())

        self.assertEqual(response.status_code, 200)
        self.assertIn("PROGRAMA A", [linha["title"] for linha in response.context["linhas"]])
        # Este catálogo não tem busca: o `q` do contexto é sempre vazio.
        self.assertEqual(response.context["q"], "")

    def test_criacao_e_edicao_avisam_com_as_frases_do_programa(self):
        response = self.client.post(
            reverse(self.url_index), {"nome": "Novo programa", "ativo": "on", "ordem": "1"}
        )
        self.assertIn("Programa cadastrado.", self._mensagens(response))

        programa = ProgramaSolicitante.objects.get(nome="NOVO PROGRAMA")
        response = self.client.post(
            reverse("planos_trabalho:programa_editar", args=[programa.pk]),
            {"nome": "Programa editado", "ativo": "on", "ordem": "2"},
        )
        self.assertIn("Programa atualizado.", self._mensagens(response))

    def test_inativo_ganha_selo(self):
        ProgramaSolicitante.objects.create(nome="INATIVO", ordem=1, ativo=False)

        linhas = self.client.get(self._index()).context["linhas"]
        linha = next(item for item in linhas if item["title"] == "INATIVO")

        self.assertEqual(len(linha["badges"]), 1)

    def test_exclusao_remove_e_avisa(self):
        programa = ProgramaSolicitante.objects.create(nome="PROGRAMA A", ordem=9)

        response = self.client.post(
            reverse("planos_trabalho:programa_excluir", args=[programa.pk])
        )

        self.assertFalse(ProgramaSolicitante.objects.filter(pk=programa.pk).exists())
        self.assertIn("Programa “PROGRAMA A” excluído.", self._mensagens(response))


class HorariosTests(CatalogoCaracterizacaoMixin, TestCase):
    url_index = "planos_trabalho:horarios_index"

    def test_lista_abre_com_a_faixa_como_titulo(self):
        HorarioAtendimento.objects.create(faixa="07:15 até 11:45", ordem=9)

        response = self.client.get(self._index())

        self.assertEqual(response.status_code, 200)
        self.assertIn("07:15 até 11:45", [linha["title"] for linha in response.context["linhas"]])

    def test_criacao_e_edicao_avisam_com_as_frases_do_horario(self):
        response = self.client.post(
            reverse(self.url_index), {"faixa": "07:20 até 12:40", "ativo": "on", "ordem": "9"}
        )
        self.assertIn("Horário cadastrado.", self._mensagens(response))

        horario = HorarioAtendimento.objects.get(faixa="07:20 até 12:40")
        response = self.client.post(
            reverse("planos_trabalho:horario_editar", args=[horario.pk]),
            {"faixa": "07:20 até 13:50", "ativo": "on", "ordem": "9"},
        )
        self.assertIn("Horário atualizado.", self._mensagens(response))

    def test_exclusao_remove_e_avisa(self):
        horario = HorarioAtendimento.objects.create(faixa="07:15 até 11:45", ordem=9)

        response = self.client.post(
            reverse("planos_trabalho:horario_excluir", args=[horario.pk])
        )

        self.assertFalse(HorarioAtendimento.objects.filter(pk=horario.pk).exists())
        self.assertIn("Horário “07:15 até 11:45” excluído.", self._mensagens(response))


class PresetDefinirPadraoNaoAceitaGetTests(TestCase):
    """O `preset_definir_padrao` antigo era `@require_POST`.

    A primeira versão da fábrica perdeu essa guarda, e o teste de caracterização
    não notou porque só fazia POST. Um GET não pode gravar.
    """

    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(username="get_padrao_preset")
        )

    def test_get_nao_define_o_padrao(self):
        preset = PresetAtividadesPlanoTrabalho.objects.create(nome="Preset G")

        response = self.client.get(
            reverse("planos_trabalho:preset_definir_padrao", args=[preset.pk])
        )

        self.assertEqual(response.status_code, 405)
        preset.refresh_from_db()
        self.assertFalse(preset.is_padrao)
