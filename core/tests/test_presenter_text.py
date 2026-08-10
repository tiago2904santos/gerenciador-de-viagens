from django.test import SimpleTestCase

from core.presenters.text import join_non_empty


class JoinNonEmptyTests(SimpleTestCase):
    def test_junta_somente_partes_com_conteudo(self):
        self.assertEqual(
            join_non_empty(["Protocolo 1", "", None, "10/08/2026", "Curitiba"]),
            "Protocolo 1 · 10/08/2026 · Curitiba",
        )

    def test_remove_espaco_externo_e_preserva_zero(self):
        self.assertEqual(join_non_empty(["  Cargo  ", "   ", 0]), "Cargo · 0")

    def test_aceita_separador_explicito_e_lista_vazia(self):
        self.assertEqual(join_non_empty(["A", "B"], sep=" / "), "A / B")
        self.assertEqual(join_non_empty([None, ""]), "")
