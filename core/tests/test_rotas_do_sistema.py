from __future__ import annotations

from django.test import SimpleTestCase
from django.urls import Resolver404
from django.urls import resolve

from scripts.rotas_do_sistema import ROTAS


class RotasDoSistemaTests(SimpleTestCase):
    def test_corpus_tem_as_43_telas_vivas_da_auditoria(self):
        self.assertEqual(len(ROTAS), 43)
        self.assertEqual(len({rota.slug for rota in ROTAS}), 43)
        self.assertEqual(len({rota.path for rota in ROTAS}), 43)

    def test_corpus_nao_carrega_as_rotas_dos_labs_removidos(self):
        self.assertFalse(any("ui-lab" in rota.path or "/dev/" in rota.path for rota in ROTAS))

    def test_toda_rota_do_corpus_existe_no_urlconf(self):
        invalidas: list[str] = []
        for rota in ROTAS:
            try:
                resolve(rota.path)
            except Resolver404:
                invalidas.append(rota.path)
        self.assertEqual(invalidas, [])

    def test_so_login_e_publica(self):
        publicas = [rota.slug for rota in ROTAS if not rota.requires_auth]
        self.assertEqual(publicas, ["login"])
