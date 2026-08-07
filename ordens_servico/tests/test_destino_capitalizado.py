"""O nome do destino saía em CAIXA ALTA no documento da Ordem de Serviço.

`Cidade.save()` normaliza o nome para maiúsculas, então o banco guarda
"RIO BRANCO DO SUL". O documento é para leitura humana e assinatura: precisa
sair "Rio Branco do Sul/PR".

O resto do módulo já fazia isso — `format_document_display` é aplicado a nomes
de servidor e ao motivo. Só o destino tinha ficado de fora.

Rascunho #32, aberto em 07/07/2026 e confirmado ainda presente hoje.
"""

from __future__ import annotations

from datetime import date

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import area_de_teste

from ..docxtpl_context import build_os_docxtpl_context
from ..models import OrdemServico


class DestinoNoDocumentoTests(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(nome="PARANA", sigla="PR")
        self.ordem = OrdemServico.objects.create(area=area_de_teste(), 
            data_evento_inicio=date(2026, 8, 10),
            data_evento_fim=date(2026, 8, 12),
            motivo="evento institucional",
        )

    def _cidade(self, nome):
        return Cidade.objects.create(nome=nome, estado=self.estado, uf="PR")

    def _destino_no_documento(self):
        return build_os_docxtpl_context(self.ordem)["destino"]

    def test_um_destino_sai_capitalizado(self):
        cidade = self._cidade("Rio Branco do Sul")
        self.ordem.destinos.set([cidade])

        # O banco guarda em caixa alta; o documento, não.
        self.assertEqual(cidade.nome, "RIO BRANCO DO SUL")
        self.assertEqual(self._destino_no_documento(), "Rio Branco do Sul/PR")

    def test_dois_destinos_saem_capitalizados(self):
        self.ordem.destinos.set(
            [self._cidade("Campo Largo"), self._cidade("Almirante Tamandare")]
        )

        self.assertEqual(
            self._destino_no_documento(),
            "Almirante Tamandare/PR e Campo Largo/PR",
        )

    def test_tres_destinos_mantem_a_pontuacao_da_lista(self):
        self.ordem.destinos.set(
            [
                self._cidade("Curitiba"),
                self._cidade("Londrina"),
                self._cidade("Maringa"),
            ]
        )

        self.assertEqual(
            self._destino_no_documento(),
            "Curitiba/PR, Londrina/PR e Maringa/PR",
        )

    def test_sem_destino_o_documento_usa_o_texto_generico(self):
        self.assertEqual(self._destino_no_documento(), "")
