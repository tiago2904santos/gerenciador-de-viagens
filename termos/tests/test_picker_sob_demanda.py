"""NOVO-07 — o seletor de ofício do termo deixa de carregar a tabela no HTML.

Mesma mudança que `justificativas/tests/test_picker_sob_demanda.py` cobre, na
tela de formulário do termo: o `json_script` passa a trazer só o ofício **já
vinculado** e os candidatos chegam por `termos:api_buscar_oficios`.

Aqui o campo é de escolha **única**, e isso traz uma armadilha que a tela de
justificativas não tem: um `<select>` sem `multiple` e sem opção vazia faz o
navegador selecionar a primeira opção sozinho. Se a opção vazia sumisse junto
com as demais, desmarcar o ofício no seletor voltaria a marcá-lo — e o termo
gravaria um vínculo que ninguém pediu. O teste está aqui embaixo.
"""

from __future__ import annotations

import json

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado

from oficios.models import Oficio
from oficios.picker import LIMITE_BUSCA
from termos.models import TermoAutorizacao
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class SeletorDeOficioDoTermoTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="TM-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="TM-B")
        self.user = get_user_model().objects.create_user(username="termo_picker")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

        self.meus = [
            Oficio.objects.create(
                numero=n, ano=2026, area=self.area, assunto=f"Deslocamento {n}", protocolo=f"T{n}"
            )
            for n in range(1, 6)
        ]
        self.alheio = Oficio.objects.create(
            numero=99, ano=2026, area=self.outra, assunto="Deslocamento da área B"
        )
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")

    def _payload(self, oficio_pk):
        """Destino e datas são obrigatórios quando o ofício não tem roteiro.

        Vão explícitos para que a única coisa em teste aqui seja o campo
        `oficio` — um formulário inválido por outro motivo passaria de graça.
        """
        return {
            "oficio": oficio_pk,
            "destino_estado": self.estado.pk,
            "destino_cidade": self.cidade.pk,
            "data_evento_inicio": date(2026, 9, 1).isoformat(),
            "data_evento_fim": date(2026, 9, 2).isoformat(),
        }

    def _opcoes_do_seletor(self, html):
        """Só o miolo do `<select name="oficio">`.

        Procurar `value="N"` na página inteira é ruído: qualquer estado, cidade
        ou servidor com o mesmo pk casaria e o teste passaria a mentir nas duas
        direções.
        """
        return html.split('name="oficio"', 1)[1].split("</select>", 1)[0]

    def _buscar(self, **params):
        resposta = self.client.get(reverse("termos:api_buscar_oficios"), params)
        self.assertEqual(resposta.status_code, 200)
        return json.loads(resposta.content)["resultados"]

    # ── o endpoint ──

    def test_a_busca_devolve_o_resumo_que_o_preenchimento_automatico_le(self):
        """Os campos de data e destino são o que o termo preenche sozinho."""
        resultados = self._buscar(q="Deslocamento 1")

        self.assertTrue(resultados)
        for chave in ("id", "label", "data_inicio", "data_fim", "estado_id", "cidade_id"):
            self.assertIn(chave, resultados[0], msg=f"o resumo perdeu a chave {chave!r}")

    def test_a_busca_manda_o_option_pronto_com_main_e_meta(self):
        """`OficioSelectSingle` decora a opção; a que a busca cria tem de casar.

        Sem `main`/`meta` a opção vinda do servidor apareceria sem protocolo nem
        assunto, na mesma lista em que as demais aparecem com.
        """
        oficio = self.meus[0]
        resultado = next(r for r in self._buscar(q="Deslocamento 1") if r["id"] == oficio.pk)

        self.assertEqual(resultado["option"]["texto"], f"Oficio {oficio.numero_formatado}")
        self.assertEqual(resultado["option"]["main"], f"Oficio {oficio.numero_formatado}")
        self.assertIn(oficio.assunto, resultado["option"]["meta"])

    def test_a_busca_nao_devolve_oficio_de_outra_area(self):
        ids = {r["id"] for r in self._buscar(q="Deslocamento")}

        self.assertNotIn(self.alheio.pk, ids)
        self.assertEqual(ids, {o.pk for o in self.meus})

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
        opcoes = self._opcoes_do_seletor(self.client.get(reverse("termos:novo")).content.decode())

        for oficio in self.meus:
            self.assertNotIn(f'value="{oficio.pk}"', opcoes)

    def test_o_blob_do_formulario_novo_vem_vazio(self):
        resposta = self.client.get(reverse("termos:novo"))

        self.assertEqual(resposta.context["oficios_summary"], {})

    def test_a_edicao_traz_no_blob_o_oficio_ja_vinculado(self):
        """O preenchimento inicial continua imediato: o vinculado vai no HTML."""
        termo = TermoAutorizacao.objects.create(area=self.area, oficio=self.meus[1])

        resposta = self.client.get(reverse("termos:editar", args=[termo.pk]))

        self.assertEqual(list(resposta.context["oficios_summary"]), [str(self.meus[1].pk)])
        self.assertContains(resposta, f'value="{self.meus[1].pk}"')

    # ── a armadilha do campo de escolha única ──

    def test_a_opcao_vazia_continua_existindo(self):
        """Sem ela, desmarcar no seletor faria o navegador remarcar o ofício."""
        termo = TermoAutorizacao.objects.create(area=self.area, oficio=self.meus[1])

        html = self.client.get(reverse("termos:editar", args=[termo.pk])).content.decode()

        self.assertIn('value=""', self._opcoes_do_seletor(html))

    # ── a regressão que a mudança convida ──

    def test_o_formulario_aceita_um_oficio_que_nao_foi_renderizado(self):
        """O campo renderiza só o selecionado, mas tem de VALIDAR qualquer um da área.

        Se o `queryset` fosse estreitado junto com o `choices`, salvar pelo
        seletor pararia de funcionar — e nenhuma tela mostraria isso antes do
        submit.
        """
        escolhido = self.meus[3]

        resposta = self.client.post(reverse("termos:novo"), self._payload(escolhido.pk))

        self.assertEqual(
            resposta.status_code,
            302,
            msg=getattr(resposta, "context", None) and resposta.context["form"].errors.as_json(),
        )
        self.assertTrue(
            TermoAutorizacao.objects.filter(oficio=escolhido).exists(),
            msg="o formulário recusou um ofício válido da área só porque não o renderizou",
        )

    def test_o_formulario_continua_recusando_oficio_de_outra_area(self):
        self.client.post(reverse("termos:novo"), self._payload(self.alheio.pk))

        self.assertFalse(TermoAutorizacao.objects.filter(oficio=self.alheio).exists())
