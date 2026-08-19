"""Contrato das ações da linha individual de termo por servidor."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from termos.presenters import apresentar_linha_lista_simples_termo_servidor


class TermoServidorPresenterTests(SimpleTestCase):
    def test_preserva_url_de_exclusao_para_o_botao_v2(self):
        termo = SimpleNamespace(
            destino_display="PR",
            periodo_display="Periodo nao informado",
            oficio_id=None,
            viatura_id=None,
        )
        servidor = SimpleNamespace(
            pk=7,
            nome="ALAN GRUBA BARBOSA",
            cargo_id=None,
            unidade_id=None,
        )

        row = apresentar_linha_lista_simples_termo_servidor(
            termo,
            servidor,
            delete_url="/termos/12/excluir/",
        )

        self.assertEqual(row["delete_url"], "/termos/12/excluir/")
        self.assertTrue(row["delete_modal"])
