"""DB-01 — a tabela nacional de diárias não tinha portão de permissão.

`TabelaDiaria` **não tem** `area`, e isso é decisão documentada
(`cadastros/selectors.py:20-27`): os valores vêm de norma externa e valem para
todas as unidades, justamente para impedir que duas áreas cobrem valores
diferentes pela mesma viagem. O enunciado original do defeito pedia fragmentar a
tabela por área; a verificação de 05/08 inverteu isso — o problema não é a
tabela ser nacional, é **quem pode mexer nela**.

E qualquer um podia: `configuracao_sistema` (`cadastros/views.py:620`) não tinha
portão nenhum além do login, e `VinculoUsuarioArea.papel` nasce `EDITOR`
(`usuarios/models.py:52`). Ou seja, todo usuário novo do sistema, de qualquer
unidade, alterava o valor de diária de todo mundo.

Decisão do usuário: **só superusuário**. Não `PAPEL_ADMIN` de área — valor
nacional não é assunto de área nenhuma, nem da que está mais organizada.

A armadilha deste defeito, e o motivo de metade dos testes abaixo: a view é
**multi-aba**. `instituicao`, `oficio` e `roteiros` entram todas por
`configuracao_sistema`, e o portão precisa recair só sobre o POST de diárias.
Um decorador na view — que é o caminho óbvio — tiraria as configurações de
instituição e de ofício de todo mundo que não é superusuário.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import TabelaDiaria
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class PortaoDaTabelaDeDiariasTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="DI-A")
        Usuario = get_user_model()

        self.editor = Usuario.objects.create_user(username="editor_comum")
        VinculoUsuarioArea.objects.create(
            usuario=self.editor,
            area=self.area,
            area_padrao=True,
            papel=VinculoUsuarioArea.PAPEL_EDITOR,
        )
        self.admin_de_area = Usuario.objects.create_user(username="admin_da_area")
        VinculoUsuarioArea.objects.create(
            usuario=self.admin_de_area,
            area=self.area,
            area_padrao=True,
            papel=VinculoUsuarioArea.PAPEL_ADMIN,
        )
        self.super = Usuario.objects.create_superuser(
            username="super", email="super@exemplo.gov.br", password="x" * 24
        )
        VinculoUsuarioArea.objects.create(usuario=self.super, area=self.area, area_padrao=True)

        self.url = reverse("cadastros:configuracao_aba", args=["roteiros"])

    #: `cadastros/migrations/0024_tabeladiaria.py` semeia as tres faixas com
    #: vigencia 2000-01-01. Toda assercao aqui fala da vigencia que o proprio
    #: teste posta — contar linhas da tabela mediria o seed, nao o portao.
    VIGENCIA = date(2026, 9, 1)

    def _payload(self, valor="500.00"):
        return {
            "form_id": "diarias",
            "faixa": TabelaDiaria.FAIXA_INTERIOR,
            "valor_24h": valor,
            "vigencia_inicio": self.VIGENCIA.isoformat(),
        }

    def _gravadas(self):
        return TabelaDiaria.objects.filter(vigencia_inicio=self.VIGENCIA)

    # ── o portão ──

    def test_editor_nao_altera_valor_de_diaria(self):
        """O defeito: `papel` nasce EDITOR, então isto valia para todo mundo."""
        self.client.force_login(self.editor)

        resposta = self.client.post(self.url, self._payload())

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(
            self._gravadas().exists(),
            msg="um EDITOR gravou valor na tabela nacional de diárias",
        )

    def test_admin_de_area_tambem_nao_altera(self):
        """Decisão do usuário: valor nacional não é assunto de área nenhuma.

        Este teste é o que separa "portão de superusuário" de "portão de papel".
        Se alguém trocar por `require_area_role(PAPEL_ADMIN)`, ele reprova.
        """
        self.client.force_login(self.admin_de_area)

        resposta = self.client.post(self.url, self._payload())

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(self._gravadas().exists())

    def test_superusuario_altera(self):
        self.client.force_login(self.super)

        resposta = self.client.post(self.url, self._payload("512.34"))

        self.assertIn(resposta.status_code, (200, 302))
        self.assertEqual(
            self._gravadas().get().valor_24h,
            Decimal("512.34"),
            msg="o portão barrou quem deveria passar",
        )

    # ── a armadilha da view multi-aba ──

    def test_editor_continua_salvando_a_aba_instituicao(self):
        """Um decorador na view inteira quebraria isto — e é o caminho óbvio.

        `instituicao`, `oficio` e `roteiros` entram todas por
        `configuracao_sistema`. O portão vale só para o POST de diárias.
        """
        self.client.force_login(self.editor)

        resposta = self.client.post(
            reverse("cadastros:configuracao_aba", args=["instituicao"]),
            {"form_id": "instituicao", "nome_orgao": "Órgão de teste", "sigla_orgao": "OT"},
        )

        self.assertNotEqual(
            resposta.status_code,
            403,
            msg="o portão das diárias vazou para a aba de instituição",
        )

    def test_editor_continua_lendo_as_vigencias(self):
        """Ler o valor vigente é legítimo: ele entra em todo roteiro calculado."""
        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_INTERIOR,
            valor_24h=Decimal("400.00"),
            vigencia_inicio=date(2026, 1, 1),
        )
        self.client.force_login(self.editor)

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "400,00")

    # ── a tela não pode oferecer o que ela vai recusar ──

    def test_a_tela_nao_mostra_o_formulario_para_quem_nao_pode_salvar(self):
        """Deixar o formulário na tela e devolver 403 no submit é pior que não

        mostrar: a pessoa preenche, envia e perde o que digitou para uma tela de
        erro. O `403` continua existindo como portão de verdade — o que muda é
        não convidar para ele.
        """
        self.client.force_login(self.editor)

        resposta = self.client.get(self.url)

        self.assertFalse(
            resposta.context["pode_editar_diarias"],
            msg="o contexto disse que o editor pode editar",
        )
        self.assertNotContains(resposta, 'name="form_id" value="diarias"')

    def test_a_tela_mostra_o_formulario_para_o_superusuario(self):
        self.client.force_login(self.super)

        resposta = self.client.get(self.url)

        self.assertTrue(resposta.context["pode_editar_diarias"])
        self.assertContains(resposta, 'name="form_id" value="diarias"')
