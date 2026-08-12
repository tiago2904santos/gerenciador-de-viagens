"""BE-09, fatia 5b — `ConfiguracaoSistema`, o singleton por área.

Este modelo saiu em PR próprio porque o raio de explosão dele é outro. Ele é
`OneToOneField` com a área, então um recorte errado não devolve lista vazia:
**duplica linha e estoura o `unique`**. E toda página lê a configuração — nome do
órgão, sigla, sede, destinatário do ofício.

Duas coisas foram verificadas em código antes de escrever uma linha, e o resultado
inverteu a suposição do plano original do `BE-09`:

- **`get_singleton()` não precisa mudar.** A consulta `area IS NULL` dele parece o
  caso canônico de "consulta deliberadamente global", mas só é alcançada quando
  `get_current_area()` já devolveu `None`, por retorno antecipado. Aí o manager ou
  não recorta, ou recorta exatamente para `area IS NULL`. Redundante, nunca
  divergente. A primeira classe abaixo trava os três contextos.

- **`get_for_area()` precisa.** Ele recebe a área por argumento, e em produção ela
  **diverge** da ativa: `cadastros/selectors.py:208`, `planos_trabalho/services.py`
  e `prestacoes_contas/services.py:133` (a correção do `BE-06`) chamam com a área
  de outro registro.

A terceira classe cobre `PlanoTrabalho.proximo_numero`, que toma
`select_for_update()` sobre a configuração da área do plano. Recortado, o lock cai
em cima de nada, a função cai no fallback e emite número de outro contador —
**plano duplicado, sem erro**.
"""

from __future__ import annotations

from django.test import TestCase

from cadastros.models import ConfiguracaoSistema
from core.tests.test_area_scoped_manager import com_request
from core.tests.test_area_scoped_manager import sem_request
from usuarios.models import AreaTrabalho


class GetSingletonSobreviveAoRecorteTests(TestCase):
    """A linha que parece (b) e é (a). Se alguém a "consertar", isto reprova."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="CFG-A")

    def test_sem_request_acha_a_configuracao_legada(self):
        with sem_request():
            legada = ConfiguracaoSistema.all_objects.create(area=None, nome_orgao="LEGADA")
            achada = ConfiguracaoSistema.get_singleton()

        self.assertEqual(achada.pk, legada.pk)

    def test_com_request_sem_area_acha_a_configuracao_legada(self):
        """Request existe mas `request.area` é `None` — o manager recorta para
        `area IS NULL`, que é exatamente o que a consulta já pedia."""
        with sem_request():
            legada = ConfiguracaoSistema.all_objects.create(area=None, nome_orgao="LEGADA")

        with com_request(None):
            achada = ConfiguracaoSistema.get_singleton()

        self.assertEqual(achada.pk, legada.pk)

    def test_com_area_ativa_nem_chega_na_consulta_legada(self):
        """Retorno antecipado: com área corrente, `get_singleton` delega a
        `get_for_area` e a linha do `area IS NULL` não é alcançada."""
        with sem_request():
            ConfiguracaoSistema.all_objects.create(area=None, nome_orgao="LEGADA")

        with com_request(self.area):
            achada = ConfiguracaoSistema.get_singleton()

        self.assertEqual(achada.area_id, self.area.pk)
        self.assertNotEqual(achada.nome_orgao, "LEGADA")


class GetForAreaPrecisaDeAllObjectsTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="GFA-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="GFA-B")

    def test_acha_a_configuracao_de_outra_area_sem_duplicar(self):
        """O caso de produção: pedir a configuração da área do registro enquanto a
        ativa é outra. Recortado, o `get` viria vazio e o `create` estouraria o
        `OneToOneField`."""
        with sem_request():
            existente = ConfiguracaoSistema.get_for_area(self.outra)

        with com_request(self.area):
            achada = ConfiguracaoSistema.get_for_area(self.outra)

        self.assertEqual(achada.pk, existente.pk)
        self.assertEqual(
            ConfiguracaoSistema.all_objects.filter(area=self.outra).count(),
            1,
            msg="criou uma segunda configuração para a mesma área",
        )

    def test_o_recorte_normal_continua_valendo(self):
        """O manager não pode ter virado decoração: dentro de um request, a
        configuração de outra área não aparece em `objects`."""
        with sem_request():
            alheia = ConfiguracaoSistema.get_for_area(self.outra)
            minha = ConfiguracaoSistema.get_for_area(self.area)

        with com_request(self.area):
            visiveis = set(ConfiguracaoSistema.objects.values_list("pk", flat=True))

        self.assertIn(minha.pk, visiveis)
        self.assertNotIn(alheia.pk, visiveis)

    def test_declara_o_par_de_managers(self):
        self.assertIs(ConfiguracaoSistema._default_manager, ConfiguracaoSistema.all_objects)
        self.assertEqual(ConfiguracaoSistema._meta.default_manager_name, "all_objects")


class NumeracaoDePlanoDeTrabalhoTests(TestCase):
    """`proximo_numero(self.area)` — a área do plano, não a ativa."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="PTN-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="PTN-B")

    def test_a_consulta_com_lock_acha_a_linha_e_nao_cai_no_fallback(self):
        """O que se perde sem `all_objects` aqui é o **lock**, e não o número.

        Se a consulta travada vier vazia, `proximo_numero` cai no `get_for_area`
        da linha seguinte — que acha a configuração e devolve o número certo. O
        resultado final fica igual, e um teste de uma thread só não vê diferença
        nenhuma. Foi o que aconteceu na primeira versão deste teste.

        O que muda é que o `SELECT ... FOR UPDATE` deixa de existir, e duas
        requisições concorrentes voltam a poder reservar o mesmo número. Como
        concorrência de verdade não cabe aqui, observo o **caminho**: com o lock
        funcionando, o fallback nunca é chamado.
        """
        from unittest.mock import patch

        from planos_trabalho.models import PlanoTrabalho

        with sem_request():
            config = ConfiguracaoSistema.get_for_area(self.outra)
            config.pt_ultimo_numero = 7
            config.pt_ano = 2026
            config.save(update_fields=["pt_ultimo_numero", "pt_ano"])

        def nao_deveria_ser_chamado(area):
            raise AssertionError(
                "a consulta com `select_for_update` veio vazia e a numeração caiu "
                "no fallback — o lock não está sobre a linha da área do plano",
            )

        with com_request(self.area):
            with patch.object(
                ConfiguracaoSistema, "get_for_area", side_effect=nao_deveria_ser_chamado,
            ):
                numero, _ano, _sufixo = PlanoTrabalho.proximo_numero(self.outra)

        self.assertEqual(numero, 8)

    def test_o_contador_nao_e_compartilhado_entre_areas(self):
        """O recorte não pode ter desligado a separação que já existia."""
        from planos_trabalho.models import PlanoTrabalho

        with sem_request():
            config = ConfiguracaoSistema.get_for_area(self.outra)
            config.pt_ultimo_numero = 40
            config.pt_ano = 2026
            config.save(update_fields=["pt_ultimo_numero", "pt_ano"])

        with com_request(self.area):
            numero, _ano, _sufixo = PlanoTrabalho.proximo_numero(self.area)

        self.assertEqual(numero, 1, msg="a área A herdou o contador da área B")
