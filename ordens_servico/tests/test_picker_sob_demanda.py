"""NOVO-07 — o seletor de ofício da OS deixa de carregar a tabela no HTML.

Terceira das três telas que montavam o mesmo resumo pelo mesmo mecanismo. O
`json_script` passa a trazer só os ofícios **já vinculados** e os candidatos
chegam por `ordens_servico:api_buscar_oficios`.

O que é próprio daqui: o campo é múltiplo e o `queryset` exclui cancelados —
menos os já vinculados, que continuam válidos porque a OS existente depende
deles. O endpoint alimenta só a busca, então corta cancelado sem ressalva; o
teste de que uma OS com ofício cancelado ainda salva está no fim.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from oficios.models import Oficio
from oficios.picker import LIMITE_BUSCA
from ordens_servico.models import OrdemServico
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class SeletorDeOficioDaOrdemTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="OS-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="OS-B")
        self.user = get_user_model().objects.create_user(username="os_picker")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

        self.meus = [
            Oficio.objects.create(
                numero=n, ano=2026, area=self.area, assunto=f"Deslocamento {n}", protocolo=f"O{n}"
            )
            for n in range(1, 6)
        ]
        self.alheio = Oficio.objects.create(
            numero=99, ano=2026, area=self.outra, assunto="Deslocamento da área B"
        )

    def _payload(self, *pks):
        """`tipo_necessidade` é obrigatório; vai junto para que a única coisa em
        teste seja o campo `oficios`."""
        return {
            "oficios": list(pks),
            "motivo": "Apoio",
            "tipo_necessidade": OrdemServico.TIPO_CAMINHAO,
        }

    def _opcoes_do_seletor(self, html):
        """Só o miolo do `<select name="oficios">` — ver o mesmo helper em `termos`."""
        return html.split('name="oficios"', 1)[1].split("</select>", 1)[0]

    def _buscar(self, **params):
        resposta = self.client.get(reverse("ordens_servico:api_buscar_oficios"), params)
        self.assertEqual(resposta.status_code, 200)
        return json.loads(resposta.content)["resultados"]

    # ── o endpoint ──

    def test_a_busca_devolve_o_resumo_que_o_preenchimento_automatico_le(self):
        resultados = self._buscar(q="Deslocamento 1")

        self.assertTrue(resultados)
        for chave in ("id", "label", "data_inicio", "data_fim", "cidade_ids", "servidor_ids"):
            self.assertIn(chave, resultados[0], msg=f"o resumo perdeu a chave {chave!r}")

    def test_a_busca_manda_o_option_pronto_com_o_rotulo_acentuado(self):
        """`OficioMultiSelectWidget` escreve "Ofício"; `termos` escreve "Oficio".

        A diferença é anterior a este ID. O que importa é que a opção criada pela
        busca saia igual à que o Django renderiza **nesta** tela.
        """
        oficio = self.meus[0]
        resultado = next(r for r in self._buscar(q="Deslocamento 1") if r["id"] == oficio.pk)

        self.assertEqual(resultado["option"]["texto"], f"Ofício {oficio.numero_formatado}")
        self.assertIn(oficio.assunto, resultado["option"]["meta"])

    def test_a_busca_nao_devolve_oficio_de_outra_area(self):
        ids = {r["id"] for r in self._buscar(q="Deslocamento")}

        self.assertNotIn(self.alheio.pk, ids)
        self.assertEqual(ids, {o.pk for o in self.meus})

    def test_a_busca_nao_oferece_oficio_cancelado(self):
        """Espelha o filtro do campo: cancelado não vira vínculo novo."""
        cancelado = self.meus[0]
        cancelado.cancelado = True
        cancelado.save(update_fields=["cancelado"])

        self.assertNotIn(cancelado.pk, {r["id"] for r in self._buscar(q="Deslocamento")})

    def test_a_busca_respeita_o_teto(self):
        Oficio.objects.bulk_create(
            [
                Oficio(numero=1000 + n, ano=2026, area=self.area, assunto="Deslocamento em massa")
                for n in range(LIMITE_BUSCA + 10)
            ]
        )

        self.assertEqual(len(self._buscar(q="Deslocamento")), LIMITE_BUSCA)

    # ── o blob e o `<select>` deixaram de crescer ──

    def test_o_formulario_novo_nao_renderiza_um_option_por_oficio(self):
        opcoes = self._opcoes_do_seletor(
            self.client.get(reverse("ordens_servico:nova")).content.decode()
        )

        for oficio in self.meus:
            self.assertNotIn(f'value="{oficio.pk}"', opcoes)

    def test_o_blob_do_formulario_novo_vem_vazio(self):
        resposta = self.client.get(reverse("ordens_servico:nova"))

        self.assertEqual(resposta.context["os_oficios_summary"], {})

    def test_novo_viajante_e_acao_compacta_do_picker_de_equipe(self):
        resposta = self.client.get(reverse("ordens_servico:nova"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'class="picker__action field-with-action__action"')
        self.assertContains(resposta, 'aria-label="Novo viajante"')
        self.assertNotContains(resposta, "<span>Novo viajante</span>")
        self.assertNotContains(resposta, '<h2 class="form-block__title">Equipe</h2>')
        self.assertNotContains(resposta, "Viajantes da ordem de serviço.")

    def test_a_edicao_traz_no_blob_os_oficios_ja_vinculados(self):
        ordem = OrdemServico.objects.create(area=self.area)
        ordem.oficios.set(self.meus[:2])

        resposta = self.client.get(reverse("ordens_servico:editar", args=[ordem.pk]))

        self.assertEqual(
            sorted(resposta.context["os_oficios_summary"]),
            sorted(str(o.pk) for o in self.meus[:2]),
        )

    # ── a regressão que a mudança convida ──

    def test_o_formulario_aceita_um_oficio_que_nao_foi_renderizado(self):
        """O campo renderiza só o selecionado, mas tem de VALIDAR qualquer um da área."""
        escolhido = self.meus[3]

        resposta = self.client.post(reverse("ordens_servico:nova"), self._payload(escolhido.pk))

        self.assertEqual(
            resposta.status_code,
            302,
            msg=getattr(resposta, "context", None) and resposta.context["form"].errors.as_json(),
        )
        self.assertTrue(
            OrdemServico.objects.filter(oficios=escolhido).exists(),
            msg="o formulário recusou um ofício válido da área só porque não o renderizou",
        )

    def test_o_formulario_continua_recusando_oficio_de_outra_area(self):
        self.client.post(reverse("ordens_servico:nova"), self._payload(self.alheio.pk))

        self.assertFalse(OrdemServico.objects.filter(oficios=self.alheio).exists())

    def test_uma_os_com_oficio_cancelado_continua_editavel(self):
        """O endpoint corta cancelado, o `queryset` do campo não — de propósito.

        Se o corte valesse também na validação, reabrir e salvar uma OS antiga
        cujo ofício foi cancelado depois perderia o vínculo sem avisar.
        """
        ordem = OrdemServico.objects.create(area=self.area)
        vinculado = self.meus[2]
        ordem.oficios.set([vinculado])
        vinculado.cancelado = True
        vinculado.save(update_fields=["cancelado"])

        self.client.post(
            reverse("ordens_servico:editar", args=[ordem.pk]), self._payload(vinculado.pk)
        )

        self.assertEqual(list(ordem.oficios.values_list("pk", flat=True)), [vinculado.pk])
