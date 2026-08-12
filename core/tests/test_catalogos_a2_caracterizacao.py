"""O que os catálogos de Ofícios, Eventos e Justificativas fazem hoje (`P-02`, A2).

Mesmo instrumento do arquivo equivalente em `planos_trabalho`: descrever o
comportamento antes de mexer, para que a migração para `core/catalog.py` só possa
passar se reproduzir tudo.

Os três variam entre si em detalhes que a fábrica precisa acomodar:

- **modelos de motivo** (ofícios) e **modelos de justificativa** têm "definir
  padrão" e um rótulo de volta que muda conforme a tela de origem;
- **tipos de evento** não tem padrão nem rótulo variável, mas carrega `?next=`;
- os três usam services próprios para gravar (`criar_modelo_motivo`,
  `criar_modelo_justificativa`), enquanto tipos de evento salva na mão.

Fica num arquivo de `core` porque cobre três apps de uma vez — é o contrato da
fábrica, não o de um app.

`ModeloMotivoOficio` e `ModeloJustificativa` gravam o `nome` em caixa alta; as
asserções comparam com o valor **gravado**, não com o digitado.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from eventos.models import TipoEvento
from justificativas.models import ModeloJustificativa
from oficios.models import ModeloMotivoOficio
from core.testing import area_de_teste
from core.testing import vincular_area


class _CatalogoMixin:
    def setUp(self):
        usuario = get_user_model().objects.create_user(username=f"a2_{self.url_index}")
        vincular_area(usuario)
        self.client.force_login(usuario)

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def _index(self, **params):
        url = reverse(self.url_index)
        if params:
            url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        return url


class ModelosMotivoTests(_CatalogoMixin, TestCase):
    url_index = "oficios:modelos_motivo_index"

    def _criar(self, titulo="Modelo A", **kwargs):
        return ModeloMotivoOficio.objects.create(area=area_de_teste(), 
            nome=titulo, texto="Texto do motivo.", **kwargs
        )

    def test_lista_abre_com_as_linhas(self):
        self._criar()

        response = self.client.get(self._index())

        self.assertEqual(response.status_code, 200)
        self.assertIn("MODELO A", [r["title"] for r in response.context["rows"]])
        self.assertEqual(response.context["page_title"], "Modelos de motivo")

    def test_a_busca_filtra(self):
        self._criar(titulo="Zebra")
        self._criar(titulo="Girafa")

        response = self.client.get(self._index(q="zebra"))

        self.assertEqual([r["title"] for r in response.context["rows"]], ["ZEBRA"])

    def test_criacao_avisa_e_redireciona(self):
        response = self.client.post(
            reverse(self.url_index), {"nome": "Novo modelo", "texto": "Texto."}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ModeloMotivoOficio.objects.filter(nome="NOVO MODELO").exists())
        self.assertIn("Modelo de motivo criado com sucesso.", self._mensagens(response))

    def test_edicao_inline_avisa(self):
        modelo = self._criar()

        response = self.client.post(
            reverse("oficios:modelo_motivo_update", args=[modelo.pk]),
            {"nome": "Modelo editado", "texto": "Outro texto."},
        )

        modelo.refresh_from_db()
        self.assertEqual(modelo.nome, "MODELO EDITADO")
        self.assertIn(
            "Modelo de motivo atualizado com sucesso.", self._mensagens(response)
        )

    def test_edicao_invalida_avisa_com_a_frase_unica(self):
        modelo = self._criar()

        response = self.client.post(
            reverse("oficios:modelo_motivo_update", args=[modelo.pk]),
            {"nome": "", "texto": ""},
        )

        self.assertIn(
            "Não foi possível salvar o modelo. Verifique os dados informados.",
            self._mensagens(response),
        )

    def test_definir_padrao_avisa(self):
        modelo = self._criar()

        response = self.client.post(
            reverse("oficios:modelo_motivo_definir_padrao", args=[modelo.pk])
        )

        modelo.refresh_from_db()
        self.assertTrue(modelo.is_padrao)
        self.assertIn("Modelo definido como padrão.", self._mensagens(response))

    def test_exclusao_por_post_e_por_get(self):
        modelo = self._criar()

        resposta_get = self.client.get(
            reverse("oficios:modelo_motivo_delete", args=[modelo.pk])
        )
        self.assertEqual(resposta_get.status_code, 200)
        self.assertTrue(ModeloMotivoOficio.objects.filter(pk=modelo.pk).exists())

        resposta_post = self.client.post(
            reverse("oficios:modelo_motivo_delete", args=[modelo.pk])
        )
        self.assertFalse(ModeloMotivoOficio.objects.filter(pk=modelo.pk).exists())
        self.assertIn(
            "Modelo de motivo excluído com sucesso.", self._mensagens(resposta_post)
        )

    def test_o_rotulo_de_volta_muda_conforme_a_origem(self):
        """Vindo da Ordem de Serviço, o botão diz outra coisa."""
        response = self.client.get(self._index(next=reverse("ordens_servico:index")))
        self.assertEqual(response.context["back_label"], "Voltar para a Ordem de Serviço")

        response = self.client.get(self._index())
        self.assertEqual(response.context["back_label"], "Voltar para o ofício")


class TiposEventoTests(_CatalogoMixin, TestCase):
    url_index = "eventos:tipos_index"

    def test_lista_criacao_edicao_e_exclusao(self):
        response = self.client.post(reverse(self.url_index), {"nome": "Seminario"})
        self.assertIn("Tipo de evento criado com sucesso.", self._mensagens(response))

        tipo = TipoEvento.objects.get(nome__iexact="Seminario")

        response = self.client.get(self._index())
        self.assertIn(tipo.nome, [r["title"] for r in response.context["rows"]])

        response = self.client.post(
            reverse("eventos:tipo_update", args=[tipo.pk]), {"nome": "Congresso"}
        )
        self.assertIn("Tipo de evento atualizado com sucesso.", self._mensagens(response))

        response = self.client.post(reverse("eventos:tipo_delete", args=[tipo.pk]))
        self.assertFalse(TipoEvento.objects.filter(pk=tipo.pk).exists())
        self.assertIn("Tipo de evento excluído com sucesso.", self._mensagens(response))

    def test_exclusao_protegida_avisa_sem_virar_erro_500(self):
        tipo = TipoEvento.objects.create(area=area_de_teste(), nome="Em uso")

        with patch.object(
            TipoEvento,
            "delete",
            side_effect=ProtectedError("vinculado", {tipo}),
        ):
            response = self.client.post(
                reverse("eventos:tipo_delete", args=[tipo.pk])
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TipoEvento.objects.filter(pk=tipo.pk).exists())
        self.assertIn(
            "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            self._mensagens(response),
        )

    def test_a_busca_filtra(self):
        TipoEvento.objects.create(area=area_de_teste(), nome="Zebra")
        TipoEvento.objects.create(area=area_de_teste(), nome="Girafa")

        response = self.client.get(self._index(q="zebra"))

        self.assertEqual(len(response.context["rows"]), 1)

    def test_o_next_vira_url_de_volta_e_do_quick_add(self):
        # A tela é aberta de dentro de um evento específico, então o `next` é a
        # URL daquele evento — sempre diferente da lista (`eventos:index`, o
        # fallback). Nesse caso, o único que ocorre na prática, a fábrica passa o
        # `next` adiante idêntico à view antiga.
        #
        # (Só na entrada degenerada `next == eventos:index` a fábrica normaliza
        # `quick_add_next_url` para "", como já fazia o catálogo de atividades —
        # a UI nunca produz essa entrada.)
        destino = "/eventos/5/guiado/1/"

        response = self.client.get(self._index(next=destino))

        self.assertEqual(response.context["back_url"], destino)
        self.assertEqual(response.context["quick_add_next_url"], destino)

    def test_edicao_invalida_avisa_com_a_frase_unica(self):
        tipo = TipoEvento.objects.create(area=area_de_teste(), nome="Seminario")

        response = self.client.post(
            reverse("eventos:tipo_update", args=[tipo.pk]), {"nome": ""}
        )

        self.assertIn(
            "Não foi possível salvar o tipo. Verifique os dados informados.",
            self._mensagens(response),
        )


class ModelosJustificativaTests(_CatalogoMixin, TestCase):
    url_index = "justificativas:modelos_index"

    def _criar(self, titulo="Modelo J", **kwargs):
        return ModeloJustificativa.objects.create(area=area_de_teste(), 
            nome=titulo, texto="Texto da justificativa.", **kwargs
        )

    def test_lista_abre_com_as_linhas(self):
        self._criar()

        response = self.client.get(self._index())

        self.assertEqual(response.status_code, 200)
        self.assertIn("MODELO J", [r["title"] for r in response.context["rows"]])

    def test_criacao_edicao_e_exclusao_avisam(self):
        response = self.client.post(
            reverse(self.url_index), {"nome": "Novo J", "texto": "Texto."}
        )
        self.assertIn(
            "Modelo de justificativa criado com sucesso.", self._mensagens(response)
        )

        modelo = ModeloJustificativa.objects.get(nome="NOVO J")

        response = self.client.post(
            reverse("justificativas:modelo_update", args=[modelo.pk]),
            {"nome": "J editado", "texto": "Outro."},
        )
        self.assertIn(
            "Modelo de justificativa atualizado com sucesso.", self._mensagens(response)
        )

        response = self.client.post(
            reverse("justificativas:modelo_delete", args=[modelo.pk])
        )
        self.assertFalse(ModeloJustificativa.objects.filter(pk=modelo.pk).exists())
        self.assertIn(
            "Modelo de justificativa excluido com sucesso.", self._mensagens(response)
        )

    def test_definir_padrao_avisa(self):
        modelo = self._criar()

        response = self.client.post(
            reverse("justificativas:modelo_definir_padrao", args=[modelo.pk])
        )

        modelo.refresh_from_db()
        self.assertTrue(modelo.is_padrao)
        self.assertIn("Modelo definido como padrao.", self._mensagens(response))

    def test_o_rotulo_de_volta_muda_conforme_a_origem(self):
        response = self.client.get(self._index(next=reverse("oficios:index")))
        self.assertEqual(response.context["back_label"], "Voltar para o ofício")

        response = self.client.get(self._index())
        self.assertEqual(response.context["back_label"], "Voltar para as justificativas")


class DefinirPadraoNaoAceitaGetTests(TestCase):
    """Definir padrão é escrita — um GET não pode gravar.

    As views antigas eram `@require_POST`. A primeira versão da fábrica não tinha
    guarda de método, então um GET passava a marcar o padrão: mutação de estado
    por navegação. Os testes de caracterização não pegaram porque só exercitavam
    o POST — a mesma cegueira que já tinha escondido o `NOVO-13`.
    """

    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(username="get_padrao")
        )

    def test_modelo_de_motivo_recusa_get(self):
        modelo = ModeloMotivoOficio.objects.create(area=area_de_teste(), nome="M", texto="T")

        response = self.client.get(
            reverse("oficios:modelo_motivo_definir_padrao", args=[modelo.pk])
        )

        self.assertEqual(response.status_code, 405)
        modelo.refresh_from_db()
        self.assertFalse(modelo.is_padrao)

    def test_modelo_de_justificativa_recusa_get(self):
        modelo = ModeloJustificativa.objects.create(area=area_de_teste(), nome="J", texto="T")

        response = self.client.get(
            reverse("justificativas:modelo_definir_padrao", args=[modelo.pk])
        )

        self.assertEqual(response.status_code, 405)
        modelo.refresh_from_db()
        self.assertFalse(modelo.is_padrao)
