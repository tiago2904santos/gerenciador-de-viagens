"""`BE-14` fatia 5 — rede para o rascunho de roteiro do ofício.

`wizard_roteiro_autosave_criar` existe para resolver um defeito de percepção: sem ele,
desmarcar o roteiro do evento e começar um roteiro próprio não sobrevive a um reload,
porque `oficio.roteiro_id` fica `None` até o save final e a próxima visita volta a sugerir
o roteiro do evento. A view conserta isso **criando o roteiro e vinculando na hora**.

São duas gravações em objetos diferentes, sem transação: o `Roteiro` nasce
(`build_roteiro_draft` + `apply_roteiro_autosave`) e depois o `Oficio` recebe o vínculo.
Se a segunda falhar, sobra um **roteiro órfão** no banco — sem ofício, sem evento, sem tela
que o alcance — e o ofício volta a se comportar como se o usuário nunca tivesse desmarcado
nada. Isto é, a falha reintroduz exatamente o defeito que a view foi escrita para corrigir,
e ainda deixa lixo atrás.

Diferente das outras fatias, aqui o dano não é "meia gravação num objeto": é **um objeto
inteiro sem dono**. Vale o mesmo remédio.
"""

from __future__ import annotations

import json

from unittest import expectedFailure
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.testing import area_de_teste
from core.testing import vincular_area
from oficios.models import Oficio
from roteiros.models import Roteiro


class RascunhoDeRoteiroDoOficioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_be14_of", password="123456"
        )
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.oficio = Oficio.objects.create(area=area_de_teste(), motivo="Motivo BE-14")

    def url(self):
        return reverse("oficios:wizard_roteiro_autosave_criar", args=[self.oficio.pk])

    def criar(self):
        return self.client.post(
            self.url(),
            data=json.dumps(
                {
                    "model": "roteiro",
                    "object_id": "",
                    "dirty_fields": ["observacoes"],
                    "fields": {"observacoes": "Rascunho proprio do oficio"},
                    "snapshots": {},
                }
            ),
            content_type="application/json",
        )

    def test_criar_vincula_o_rascunho_ao_oficio(self):
        """Caminho feliz — sem ele o cenário de falha seria verde por omissão."""
        resposta = self.criar()

        corpo = resposta.json()
        self.assertTrue(corpo["ok"])
        self.assertTrue(corpo["created"])
        self.oficio.refresh_from_db()
        self.assertEqual(self.oficio.roteiro_id, corpo["object_id"])

    @expectedFailure
    def test_falha_ao_vincular_nao_deixa_roteiro_orfao(self):
        """O defeito. **Reprova antes da correção.**

        O roteiro é criado e gravado; o vínculo com o ofício é a gravação seguinte. Sem
        transação, uma falha no vínculo deixa um `Roteiro` no banco sem ofício e sem
        evento — inalcançável por qualquer tela — enquanto o ofício continua com
        `roteiro_id` nulo, voltando a sugerir o roteiro do evento na próxima visita.

        A falha entra em `Oficio.save`, que é a última gravação do caminho antes e
        depois da extração — o mesmo critério das fatias 3 e 4: injetar no
        comportamento, não no nome do módulo.
        """
        antes = Roteiro.all_objects.count()

        def falhar(*args, **kwargs):
            raise RuntimeError("falha ao vincular o roteiro ao ofício")

        with mock.patch.object(Oficio, "save", falhar):
            with self.assertRaises(RuntimeError):
                self.criar()

        self.oficio.refresh_from_db()
        self.assertIsNone(self.oficio.roteiro_id)
        self.assertEqual(
            Roteiro.all_objects.count(),
            antes,
            "sobrou um roteiro órfão: sem ofício, sem evento e sem tela que o alcance",
        )
