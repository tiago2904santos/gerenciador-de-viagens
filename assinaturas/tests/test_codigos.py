from __future__ import annotations

from django.test import TestCase

from assinaturas.services.codigos import CODIGO_RE
from assinaturas.services.codigos import codigo_tem_formato_valido
from assinaturas.services.codigos import gerar_codigo_verificacao
from assinaturas.services.codigos import normalizar_codigo_verificacao


class CodigosVerificacaoTests(TestCase):
    def test_codigo_gerado_bate_com_regex(self):
        c = gerar_codigo_verificacao()
        self.assertIsNotNone(CODIGO_RE.fullmatch(c))

    def test_codigo_gerado_e_unico(self):
        a = gerar_codigo_verificacao()
        b = gerar_codigo_verificacao()
        self.assertNotEqual(a, b)

    def test_normalizacao_remove_espacos_e_upper(self):
        self.assertEqual(normalizar_codigo_verificacao("  cv-2026-ab12cd-ef34  "), "CV-2026-AB12CD-EF34")

    def test_codigo_tem_formato_valido(self):
        self.assertTrue(codigo_tem_formato_valido("CV-2026-A1B2C3-D4E5"))
        self.assertFalse(codigo_tem_formato_valido("INVALID"))
