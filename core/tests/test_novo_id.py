from __future__ import annotations

from datetime import UTC
from datetime import datetime

from django.test import SimpleTestCase

from scripts.novo_id import gerar_id


class NovoIdTests(SimpleTestCase):
    def test_formato_e_estavel_e_auto_ordenavel(self):
        instante = datetime(2026, 8, 12, 19, 4, 5, tzinfo=UTC)

        self.assertEqual(
            gerar_id(instante=instante, sufixo="a1b2c3d4e5f6"),
            "NOVO-20260812-190405-a1b2c3d4e5f6",
        )

    def test_sessoes_no_mesmo_segundo_nao_dependem_do_mesmo_contador(self):
        instante = datetime(2026, 8, 12, 19, 4, 5, tzinfo=UTC)

        primeiro = gerar_id(instante=instante, sufixo="000000000001")
        segundo = gerar_id(instante=instante, sufixo="000000000002")

        self.assertNotEqual(primeiro, segundo)

    def test_sufixo_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            gerar_id(sufixo="XYZ")
