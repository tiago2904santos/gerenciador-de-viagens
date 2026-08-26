"""Guarda de `update_fields` no signal do Ofício.

`organizar_oficio` é caro mesmo quando não gera nada: percorre a árvore de
pastas do Drive pela API a cada execução. Um save que só carimbou o relógio não
pode custar isso.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from integracoes.google_drive import signals


def _oficio_finalizado():
    return SimpleNamespace(pk=7, status="finalizado", STATUS_RASCUNHO="rascunho")


@override_settings(GOOGLE_DRIVE={"MODO": "ativo", "UPLOAD_EM_MOCK": False})
class OrganizarOficioAoSalvarTests(SimpleTestCase):
    def _disparar(self, **kwargs):
        with patch.object(signals, "_agendar_apos_commit") as agendar:
            signals._organizar_oficio_ao_salvar(None, _oficio_finalizado(), **kwargs)
        return agendar

    def test_save_so_de_updated_at_nao_enfileira(self):
        agendar = self._disparar(update_fields=frozenset({"updated_at"}))
        agendar.assert_not_called()

    def test_save_completo_continua_enfileirando(self):
        agendar = self._disparar(update_fields=None)
        agendar.assert_called_once()

    def test_finalizacao_continua_enfileirando(self):
        agendar = self._disparar(
            update_fields=frozenset({"status", "data_criacao", "updated_at"}),
        )
        agendar.assert_called_once()

    def test_rascunho_nao_enfileira(self):
        oficio = SimpleNamespace(pk=7, status="rascunho", STATUS_RASCUNHO="rascunho")
        with patch.object(signals, "_agendar_apos_commit") as agendar:
            signals._organizar_oficio_ao_salvar(None, oficio, update_fields=None)
        agendar.assert_not_called()
