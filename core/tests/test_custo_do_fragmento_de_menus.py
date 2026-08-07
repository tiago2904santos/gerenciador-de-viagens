"""O fragmento de menus não pode voltar a fazer N+1 (`NOVO-38`).

O `PF-04` tirou os menus do HTML da lista e passou a servi-los por endpoint. O
endpoint chama o MESMO presenter que a lista — é isso que mantém a paridade por
construção —, mas com um registro só. E aí apareceu o preço: o presenter percorre
destinos e trechos do roteiro tocando `cidade` e `estado` de cada um, e os
selectors de registro único não tinham a carga que os de lista já tinham desde o
`NOVO-08`.

Eram 30 consultas para um card de Ofício e 28 para um de prestação.

Esta rede guarda o eixo certo: **dobrar o tamanho do registro não pode dobrar as
consultas do fragmento**. Contar um número fixo envelheceria no primeiro campo
novo; contar crescimento não.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from oficios.models import Oficio
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from core.testing import area_de_teste
from core.testing import vincular_area


class CustoDoFragmentoDeMenusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estado = Estado.objects.create(sigla="PR", nome="Parana")
        cls.cidade = Cidade.objects.create(nome="CURITIBA", estado=cls.estado, uf="PR")
        cls.cargo = Cargo.objects.create(area=area_de_teste(), nome="Analista")

    def setUp(self):
        usuario = get_user_model().objects.create_user(username="frag")
        vincular_area(usuario)
        self.client.force_login(usuario)

    def _oficio(self, *, destinos, servidores):
        roteiro = Roteiro.objects.create(area=area_de_teste(), 
            origem_estado=self.estado, origem_cidade=self.cidade
        )
        for ordem in range(destinos):
            RoteiroDestino.objects.create(
                roteiro=roteiro, estado=self.estado, cidade=self.cidade, ordem=ordem
            )
        oficio = Oficio.objects.create(area=area_de_teste(), 
            numero=Oficio.objects.count() + 1,
            ano=2026,
            roteiro=roteiro,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        for indice in range(servidores):
            oficio.servidores.add(
                Servidor.objects.create(area=area_de_teste(), 
                    nome=f"Servidor {oficio.pk}-{indice}",
                    cargo=self.cargo,
                    cpf=f"{oficio.pk:05d}{indice:06d}",
                )
            )
        return oficio

    def _consultas_do_fragmento(self, oficio):
        url = reverse("oficios:card_menus", args=[oficio.pk])
        self.client.get(url)  # aquece o cache de templates
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        # Sem isto o teste mediria um fragmento vazio e passaria sempre.
        self.assertIn(b"cv-action-menu", resposta.content)
        return len(capturadas.captured_queries)

    def test_dobrar_destinos_e_servidores_nao_dobra_as_consultas(self):
        pequeno = self._consultas_do_fragmento(self._oficio(destinos=1, servidores=1))
        grande = self._consultas_do_fragmento(self._oficio(destinos=4, servidores=4))

        self.assertEqual(
            pequeno,
            grande,
            "o custo do fragmento voltou a crescer com o tamanho do registro; "
            "é o N+1 do NOVO-38 de volta",
        )
