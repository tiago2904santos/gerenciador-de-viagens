"""`BE-13` fatia 3 — rede para o gravador do editor, antes de ele sair do módulo.

`_salvar_roteiro_avulso_from_roteiro_state` e as duas funções que só ela chama vão para
`roteiros/services/editor_persistence.py`.

**O plano desta fatia partia de uma premissa errada, e a apuração a derrubou.** Eu ia
"cobrir as 6 linhas descobertas" do trio. Escrevi cinco cenários, e **três passavam com o
código quebrado** — a prova por inversão os reprovou como vazios. Investigando o porquê:

    tempo_adicional_min = -30 no POST   ->  chega ao gravador como 0
    duracao_estimada_min = "" no POST   ->  chega ao gravador como 285 (já derivada)
    trecho que duplica o retorno        ->  chega ao gravador já removido

`_build_roteiro_state_from_post` e `dedupe_roteiro_loop_retorno_final` **já normalizam**
tudo isso a montante. As guardas correspondentes dentro do gravador são cópias defensivas
de regra que roda antes — e é por isso que `coverage` nunca as alcançou. Não é lacuna de
teste: é ramo inalcançável pelo caminho público. Ficou registrado no catálogo em vez de
virar teste de mentira.

A garantia mais importante da fatia — o gravador ser atômico — já tem teste desde o
`DB-08`, em
`core/tests/test_colecoes_ordenadas_db08.py::test_falha_entre_os_dois_passos_nao_deixa_posicao_no_bloco`.
Conferi por inversão que ele reprova sem o `@transaction.atomic`, em vez de duplicá-lo.

Sobram aqui os dois cenários que mordem, ambos pela fachada pública
`roteiros.services.atualizar_roteiro` — que é como produção chega ao gravador, e o que faz
a rede sobreviver à mudança de arquivo.
"""

from decimal import Decimal

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import area_de_teste
from roteiros.forms import RoteiroForm
from roteiros.models import Roteiro
from roteiros.models import RoteiroTrecho
from roteiros.services import atualizar_roteiro


class GravadorDoEditorTests(TestCase):
    """O que o gravador escreve, pela fachada que produção usa."""

    def setUp(self):
        self.estado = Estado.objects.create(nome="Parana GRV", sigla="GV")
        self.sede = Cidade.objects.create(nome="Curitiba GRV", estado=self.estado)
        self.destino = Cidade.objects.create(nome="Londrina GRV", estado=self.estado)

    def _roteiro(self):
        return Roteiro.objects.create(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.sede,
        )

    def _post(self, *, trechos, retorno=None):
        """POST do editor, como o navegador manda — o estado sai do parser real.

        Montar `roteiro_state`/`validated` à mão daria strings onde o gravador espera
        `date`/`time`: quem converte é `_validate_roteiro_state`. Passar por ele é o que
        torna este teste fiel ao caminho de produção — e foi o que revelou que as guardas
        do gravador são inalcançáveis.
        """
        from urllib.parse import urlencode

        from django.http import QueryDict

        retorno = retorno or {}
        dados = {
            "roteiro_modo": "ROTEIRO_PROPRIO",
            "origem_estado": str(self.estado.pk),
            "origem_cidade": str(self.sede.pk),
            "retorno_saida_data": retorno.get("saida_data", "2026-09-10"),
            "retorno_saida_hora": retorno.get("saida_hora", "14:00"),
            "retorno_chegada_data": retorno.get("chegada_data", "2026-09-10"),
            "retorno_chegada_hora": retorno.get("chegada_hora", "18:00"),
            "retorno_tempo_cru_estimado_min": retorno.get("tempo_cru_estimado_min", "240"),
            "retorno_tempo_adicional_min": retorno.get("tempo_adicional_min", "0"),
            "retorno_duracao_estimada_min": retorno.get("duracao_estimada_min", ""),
            "retorno_distancia_km": retorno.get("distancia_km", ""),
        }
        for idx, trecho in enumerate(trechos):
            for chave, valor in trecho.items():
                dados[f"trecho_{idx}_{chave}"] = str(valor)
        return QueryDict(urlencode(dados))

    def _trecho(self, *, origem, destino, dia, **extra):
        base = {
            "origem_estado_id": self.estado.pk,
            "origem_cidade_id": origem.pk,
            "destino_estado_id": self.estado.pk,
            "destino_cidade_id": destino.pk,
            "saida_data": f"2026-09-{dia:02d}",
            "saida_hora": "08:00",
            "chegada_data": f"2026-09-{dia:02d}",
            "chegada_hora": "12:00",
            "tempo_cru_estimado_min": "240",
            "tempo_adicional_min": "0",
            "duracao_estimada_min": "240",
        }
        base.update(extra)
        return base

    def _gravar(self, roteiro, *, trechos, retorno=None):
        """Valida e grava pela fachada, como as views fazem."""
        from roteiros.services import validar_submissao_editor_roteiro

        post = self._post(trechos=trechos, retorno=retorno)
        state, validated, diarias = validar_submissao_editor_roteiro(post, {}, roteiro=roteiro)
        self.assertTrue(validated["ok"], validated.get("errors"))
        form = RoteiroForm(post, instance=roteiro)
        self.assertTrue(form.is_valid(), form.errors)
        return atualizar_roteiro(roteiro, form, state, validated, diarias)

    def test_distancia_do_trecho_e_do_retorno_sao_gravadas(self):
        """As duas pontas: a distância da ida e a do retorno.

        Provado por inversão — apagar a atribuição de `distancia_km` do retorno reprova.
        """
        roteiro = self._roteiro()

        self._gravar(
            roteiro,
            trechos=[
                self._trecho(origem=self.sede, destino=self.destino, dia=1, distancia_km="381,5")
            ],
            retorno={"distancia_km": "377,2"},
        )

        ida = roteiro.trechos.exclude(tipo=RoteiroTrecho.TIPO_RETORNO).first()
        volta = roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).first()
        self.assertEqual(ida.distancia_km, Decimal("381.5"))
        self.assertEqual(volta.distancia_km, Decimal("377.2"))

    def test_gravar_de_novo_substitui_os_destinos_em_vez_de_acumular(self):
        """O gravador apaga os destinos e recria: salvar duas vezes não duplica nada.

        É a garantia que o `DB-08` protegeu com constraint, e a que mais importa preservar
        quando a função muda de arquivo.
        """
        roteiro = self._roteiro()
        outro = Cidade.objects.create(nome="Maringa GRV", estado=self.estado)

        self._gravar(roteiro, trechos=[self._trecho(origem=self.sede, destino=self.destino, dia=1)])
        self._gravar(roteiro, trechos=[self._trecho(origem=self.sede, destino=outro, dia=1)])

        self.assertEqual(
            list(roteiro.destinos.order_by("ordem").values_list("cidade_id", flat=True)),
            [outro.pk],
            "o segundo save substitui o destino, não empilha",
        )
        self.assertEqual(roteiro.trechos.exclude(tipo=RoteiroTrecho.TIPO_RETORNO).count(), 1)
        self.assertEqual(roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).count(), 1)
