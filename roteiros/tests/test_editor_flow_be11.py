"""`BE-11` — caracterização do editor de roteiro antes de unificar `novo` e `editar`.

`roteiros/views.py::novo` (89 linhas úteis) e `::editar` (86) têm **55 linhas idênticas**:
a mesma sequência de validar → decidir entre sobrescrever duplicado, atualizar ou criar →
montar contexto → renderizar, escrita duas vezes. O `BE-11` a extrai para
`roteiros/services/editor_flow.py`.

Estes testes existem porque, antes deles, `roteiros:editar` **não tinha um único POST
coberto** — nem o caminho do duplicado, que é justamente o que distingue estas duas views
do fluxo do ofício. Eles descrevem o comportamento de hoje, foram escritos e provados
verdes **antes** da refatoração, e o que travam é o que não pode mudar:

- as duas mensagens de sucesso do duplicado têm textos **diferentes** e continuam diferentes;
- a escolha de redirect (`?next=` → evento → índice) é da view, não do service;
- as chaves de contexto que só uma das duas páginas tem (`delete_url`, `page_description`)
  continuam só nela — o presenter único não pode preenchê-las com `""` na outra.
"""

from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import area_de_teste
from core.testing import vincular_area
from eventos.models import Evento
from roteiros import roteiro_logic
from roteiros.models import Roteiro


def _mensagens(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class EditorRoteiroCaracterizacaoTests(TestCase):
    """Comportamento observável de `roteiros:novo` e `roteiros:editar`, congelado."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="be11_tester", password="teste")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado_destino, _ = Estado.objects.get_or_create(
            sigla="SC", defaults={"nome": "SANTA CATARINA"}
        )
        self.sede, _ = Cidade.objects.get_or_create(
            nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"}
        )
        self.destino, _ = Cidade.objects.get_or_create(
            nome="FLORIANOPOLIS", estado=self.estado_destino, defaults={"uf": "SC"}
        )
        self.destino_2, _ = Cidade.objects.get_or_create(
            nome="LONDRINA", estado=self.estado, defaults={"uf": "PR"}
        )

    # -- payloads -----------------------------------------------------------

    def _post_valido(self, *, destino=None, observacoes=""):
        """Um trecho de ida mais o retorno — o roteiro mais simples que valida.

        O retorno **não** é um trecho: vai nos campos `retorno_*`. Sem eles o
        `_validate_roteiro_state` reprova com "Informe a saída do retorno".
        """
        destino = destino or self.destino
        dados = {
            "roteiro_modo": roteiro_logic.ROTEIRO_MODO_PROPRIO,
            "origem_estado": str(self.estado.pk),
            "origem_cidade": str(self.sede.pk),
            "observacoes": observacoes,
            "retorno_saida_data": "2026-09-03",
            "retorno_saida_hora": "14:00",
            "retorno_chegada_data": "2026-09-03",
            "retorno_chegada_hora": "18:00",
            "retorno_tempo_cru_estimado_min": "240",
            "retorno_tempo_adicional_min": "0",
            "retorno_duracao_estimada_min": "240",
        }
        trecho = {
            "origem_estado_id": self.estado.pk,
            "origem_cidade_id": self.sede.pk,
            "destino_estado_id": destino.estado_id,
            "destino_cidade_id": destino.pk,
            "saida_data": "2026-09-01",
            "saida_hora": "08:00",
            "chegada_data": "2026-09-01",
            "chegada_hora": "12:00",
            "tempo_cru_estimado_min": "240",
            "tempo_adicional_min": "0",
            "duracao_estimada_min": "240",
        }
        for chave, valor in trecho.items():
            dados[f"trecho_0_{chave}"] = str(valor)
        return dados

    def _criar_roteiro_pelo_editor(self, **kwargs):
        resposta = self.client.post(reverse("roteiros:novo"), data=self._post_valido(**kwargs))
        self.assertEqual(resposta.status_code, 302, _mensagens(resposta))
        return Roteiro.objects.order_by("-pk").first()

    # -- 1..4: redirect e mensagem de `editar` ------------------------------

    def test_1_editar_sem_duplicado_atualiza_e_volta_para_a_lista(self):
        roteiro = self._criar_roteiro_pelo_editor(observacoes="antes")

        resposta = self.client.post(
            reverse("roteiros:editar", args=[roteiro.pk]),
            data=self._post_valido(observacoes="depois"),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("roteiros:index"))
        self.assertIn("Roteiro atualizado com sucesso.", _mensagens(resposta))
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.observacoes, "DEPOIS")

    def test_2_editar_com_next_local_volta_para_o_next(self):
        roteiro = self._criar_roteiro_pelo_editor()
        destino = reverse("roteiros:index") + "?pagina=3"

        resposta = self.client.post(
            reverse("roteiros:editar", args=[roteiro.pk]) + "?next=" + destino,
            data=self._post_valido(observacoes="com next"),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], destino)

    def test_3_editar_com_next_externo_ignora_o_next(self):
        roteiro = self._criar_roteiro_pelo_editor()

        resposta = self.client.post(
            reverse("roteiros:editar", args=[roteiro.pk]) + "?next=https://exemplo.invalido/x",
            data=self._post_valido(observacoes="next hostil"),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta["Location"],
            reverse("roteiros:index"),
            "open redirect: `_next_url_seguro` tem de recusar host externo",
        )

    def test_4_editar_roteiro_de_evento_volta_para_a_etapa_2_do_evento(self):
        roteiro = self._criar_roteiro_pelo_editor()
        evento = Evento.objects.create(area=area_de_teste(), titulo="EVENTO BE-11")
        roteiro.evento = evento
        roteiro.tipo = Roteiro.TIPO_EVENTO
        roteiro.save(update_fields=["evento", "tipo"])

        resposta = self.client.post(
            reverse("roteiros:editar", args=[roteiro.pk]),
            data=self._post_valido(observacoes="do evento"),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta["Location"],
            reverse("eventos:guiado_etapa", args=[evento.pk, 2]),
        )

    def test_1b_editar_preserva_o_tipo_gravado_em_vez_de_deduzi_lo_do_evento(self):
        """`editar` chama `atualizar_roteiro`, nunca `criar_roteiro` — e isso é visível.

        As duas divergem em duas linhas: só `criar_roteiro` sobrescreve `evento` e deriva
        `tipo` dele; `atualizar_roteiro` preserva `instance.tipo`. Um roteiro **avulso
        vinculado a um evento** (é o que o wizard do ofício grava) separa as duas: sob
        `criar_roteiro` o `tipo` viraria `TIPO_EVENTO` em silêncio.

        Antes deste teste nada na suíte distinguia os dois caminhos.
        """
        roteiro = self._criar_roteiro_pelo_editor()
        evento = Evento.objects.create(area=area_de_teste(), titulo="EVENTO AVULSO BE-11")
        roteiro.evento = evento
        roteiro.tipo = Roteiro.TIPO_AVULSO
        roteiro.save(update_fields=["evento", "tipo"])

        resposta = self.client.post(
            reverse("roteiros:editar", args=[roteiro.pk]),
            data=self._post_valido(observacoes="continua avulso"),
        )

        self.assertEqual(resposta.status_code, 302)
        roteiro.refresh_from_db()
        self.assertEqual(
            roteiro.tipo,
            Roteiro.TIPO_AVULSO,
            "`editar` não pode redefinir o tipo a partir do evento vinculado",
        )
        self.assertEqual(roteiro.observacoes, "CONTINUA AVULSO")

    # -- 5 e 7: as duas mensagens de duplicado, que são diferentes ----------

    def test_5_editar_que_colide_grava_no_duplicado_e_descarta_este(self):
        alvo = self._criar_roteiro_pelo_editor(destino=self.destino, observacoes="alvo")
        outro = self._criar_roteiro_pelo_editor(destino=self.destino_2, observacoes="outro")
        self.assertNotEqual(alvo.pk, outro.pk)

        # Editar `outro` para ficar idêntico a `alvo`.
        resposta = self.client.post(
            reverse("roteiros:editar", args=[outro.pk]),
            data=self._post_valido(destino=self.destino, observacoes="virou o alvo"),
        )

        self.assertEqual(resposta.status_code, 302)
        mensagens = _mensagens(resposta)
        self.assertTrue(
            any(f"#{alvo.pk}" in m and "este registro foi descartado" in m for m in mensagens),
            f"a mensagem de `editar` tem de citar o duplicado e o descarte: {mensagens}",
        )
        alvo.refresh_from_db()
        self.assertEqual(alvo.observacoes, "VIROU O ALVO")
        self.assertFalse(
            Roteiro.all_objects.filter(pk=outro.pk).exists(),
            "o registro editado é descartado quando funde no duplicado",
        )

    def test_7_novo_com_duplicado_usa_texto_proprio_sem_falar_em_descarte(self):
        existente = self._criar_roteiro_pelo_editor(observacoes="primeira")

        resposta = self.client.post(
            reverse("roteiros:novo"), data=self._post_valido(observacoes="segunda")
        )

        self.assertEqual(resposta.status_code, 302)
        mensagens = _mensagens(resposta)
        self.assertTrue(
            any(
                f"#{existente.pk}" in m and "os dados foram atualizados nele." in m
                for m in mensagens
            ),
            f"a mensagem de `novo` é outra, e tem de continuar outra: {mensagens}",
        )
        self.assertTrue(
            all("descartado" not in m for m in mensagens),
            "só `editar` fala em descarte — em `novo` não havia registro a descartar",
        )
        self.assertEqual(Roteiro.objects.count(), 1)

    # -- 6 e 8: os dois caminhos de erro -----------------------------------

    def test_6_erro_de_validacao_rerenderiza_com_erro_nao_de_campo(self):
        roteiro = self._criar_roteiro_pelo_editor()
        dados = self._post_valido()
        dados.pop("trecho_0_saida_hora")

        resposta = self.client.post(reverse("roteiros:editar", args=[roteiro.pk]), data=dados)

        self.assertEqual(resposta.status_code, 200)
        erros = resposta.context["form"].errors.get("__all__") or []
        self.assertTrue(
            any("informe a saída" in e.lower() for e in erros),
            f"cada erro de `validated['errors']` vira erro não-de-campo do form: {erros}",
        )

    def test_8_sobrescrita_que_falha_vira_erro_no_form_e_nao_redirect(self):
        existente = self._criar_roteiro_pelo_editor(observacoes="primeira")

        from roteiros.services import editor_flow

        original = editor_flow.sobrescrever_roteiro_duplicado
        editor_flow.sobrescrever_roteiro_duplicado = lambda *a, **k: None
        try:
            resposta = self.client.post(
                reverse("roteiros:novo"), data=self._post_valido(observacoes="segunda")
            )
        finally:
            editor_flow.sobrescrever_roteiro_duplicado = original

        self.assertEqual(resposta.status_code, 200, "colisão sem saída não redireciona")
        erros = resposta.context["form"].errors.get("__all__") or []
        self.assertTrue(
            any(f"#{existente.pk}" in e and "Já existe um roteiro idêntico salvo" in e for e in erros),
            f"o erro tem de citar o pk do duplicado: {erros}",
        )

    # -- 9: as chaves de contexto de cada uma das duas páginas -------------

    def test_9_contexto_do_get_de_novo(self):
        contexto = self.client.get(reverse("roteiros:novo")).context

        self.assertEqual(contexto["page_title"], "Novo roteiro")
        self.assertEqual(
            contexto["page_description"],
            "Sede, destinos, trechos, retorno e diárias no mesmo fluxo do legacy.",
        )
        self.assertEqual(contexto["back_url"], reverse("roteiros:index"))
        self.assertEqual(contexto["wizard_back_label"], "Voltar para lista")
        self.assertEqual(contexto["wizard_back_url"], reverse("roteiros:index"))
        self.assertEqual(
            contexto["wizard_header"],
            {
                "title": "Novo roteiro",
                "description": "Roteiro e diárias",
                "status_label": "",
                "status_variant": "",
            },
        )
        self.assertEqual(contexto["wizard_page_steps"], [])
        self.assertTrue(contexto["roteiro_editor_oficio"])
        self.assertEqual(contexto["roteiro_form_action"], reverse("roteiros:novo"))
        self.assertNotIn(
            "delete_url",
            contexto,
            "não há o que excluir numa página de criação; a chave não pode surgir vazia",
        )

    def test_9_contexto_do_get_de_editar(self):
        roteiro = self._criar_roteiro_pelo_editor()
        url = reverse("roteiros:editar", args=[roteiro.pk])

        contexto = self.client.get(url).context

        self.assertEqual(contexto["page_title"], "Editar roteiro")
        self.assertEqual(
            contexto["page_description"], "Ajuste sede, destinos, trechos e retorno."
        )
        self.assertEqual(contexto["back_url"], reverse("roteiros:index"))
        self.assertEqual(contexto["delete_url"], reverse("roteiros:excluir", args=[roteiro.pk]))
        self.assertEqual(contexto["wizard_back_label"], "Voltar para lista")
        self.assertEqual(contexto["wizard_back_url"], reverse("roteiros:index"))
        self.assertEqual(
            contexto["wizard_header"],
            {
                "title": "Editar roteiro",
                "description": "Roteiro e diárias",
                "status_label": roteiro.get_status_display(),
                "status_variant": "active"
                if roteiro.status != Roteiro.STATUS_RASCUNHO
                else "draft",
            },
        )
        self.assertEqual(contexto["wizard_page_steps"], [])
        self.assertTrue(contexto["roteiro_editor_oficio"])
        self.assertEqual(contexto["roteiro_form_action"], url)

    def test_9_contexto_do_get_de_editar_com_next(self):
        """`?next=` troca `back_url`, `wizard_back_url`, o rótulo — e o `form_action`."""
        roteiro = self._criar_roteiro_pelo_editor()
        destino = reverse("roteiros:index") + "?pagina=2"
        url = reverse("roteiros:editar", args=[roteiro.pk]) + "?next=" + destino

        contexto = self.client.get(url).context

        self.assertEqual(contexto["back_url"], destino)
        self.assertEqual(contexto["wizard_back_url"], destino)
        self.assertEqual(contexto["wizard_back_label"], "Voltar")
        self.assertEqual(
            contexto["roteiro_form_action"],
            url,
            "o form tem de repostar com o `next`, senão o retorno se perde ao salvar",
        )
