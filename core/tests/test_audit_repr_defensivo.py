"""BE-07 — a trilha de auditoria não pode derrubar a exclusão que ela observa.

`core/audit.py` montava `object_repr` com `str(instance)[:255]` no sinal
`pre_delete`, conectado globalmente aos 11 apps auditados. Se o `__str__` do
modelo devolvesse `None`, o próprio `str()` levantava
`TypeError: __str__ returned non-string`.

Não era hipótese: `PrestacaoDocumentoAnexo.__str__` devolve
`self.nome_original or self.arquivo.name`, e a view de exclusão apagava o arquivo
— zerando `FieldFile.name` — **antes** de `anexo.delete()`. Com `nome_original`
vazio, que é o default do campo e o caso de anexo legado ou importado, os dois
lados viravam vazio e o `or` devolvia `None`.

O usuário levava 500 e sobrava registro órfão: o arquivo sumia do disco e a linha
continuava na tabela, aparecendo na tela como anexo existente e quebrando o
download.

São dois defeitos, e cada um tem sua correção: a auditoria passa a tolerar
`__str__` mal-comportado de qualquer modelo, e a view apaga o arquivo depois da
linha.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from core.audit import _repr_seguro
from prestacoes_contas.models import PrestacaoDocumentoAnexo
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin

from django.core.files.uploadedfile import SimpleUploadedFile

PDF = b"%PDF-1.4\n%%EOF\n"


class ExclusaoDeAnexoSemNomeOriginalTests(PrestacaoFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=1)
        self.ps = self.fixture.prestacoes_servidor[0]
        # `nome_original=""` é o default do campo — anexo legado ou importado.
        self.anexo = PrestacaoDocumentoAnexo.objects.create(
            prestacao=self.fixture.prestacao,
            servidor_prestacao=self.ps,
            tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
            arquivo=SimpleUploadedFile("legado.pdf", PDF, content_type="application/pdf"),
            nome_original="",
        )

    def test_exclusao_conclui_e_nao_deixa_registro_orfao(self):
        response = self.client.post(
            reverse(
                "prestacoes_contas:prestacao_documento_delete",
                args=[self.fixture.prestacao.pk, self.anexo.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PrestacaoDocumentoAnexo.objects.filter(pk=self.anexo.pk).exists(),
            msg="a linha sobreviveu à exclusão — registro órfão",
        )


class ReprSeguroTests(TestCase):
    def test_str_vazio_cai_para_rotulo_e_pk(self):
        """Perder o rótulo legível é aceitável; perder o rastro do objeto não."""
        anexo = PrestacaoDocumentoAnexo(pk=42)

        repr_gerado = _repr_seguro(anexo)

        self.assertIn("42", repr_gerado)
        self.assertIn("PrestacaoDocumentoAnexo", repr_gerado)

    def test_str_normal_continua_sendo_usado(self):
        anexo = PrestacaoDocumentoAnexo(pk=7, nome_original="Comprovante.pdf")

        self.assertEqual(_repr_seguro(anexo), "Comprovante.pdf")
