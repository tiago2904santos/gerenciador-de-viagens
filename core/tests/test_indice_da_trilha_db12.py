"""`DB-12` — o índice de área cruzada com período na trilha de auditoria.

O enunciado dizia que `AuditEvent` não tinha "suporte para consulta por área ou
período". A verificação de 05/08 já tinha derrubado metade disso: são 10 índices,
com coluna única nos dois campos. O que faltava era o **composto**.

**Este arquivo existe mais para registrar o que a medição disse do que para
proteger código.** O índice não é escolhido pelo planner na escala de hoje — só
passa a ser por volta de 100 áreas (ver a migração `core/0004`). Ele entrou como
folga de crescimento, por decisão do usuário, e o teste abaixo garante só que ele
continua casando com a consulta que um dia vai usá-lo.

Um teste de plano seria mentira aqui: com poucas áreas ele reprovaria com o índice
presente e correto.
"""

from __future__ import annotations

from django.test import TestCase

from core.admin import AuditEventAdmin
from core.models import AuditEvent


class ContratoDoIndiceDaTrilhaTests(TestCase):
    def test_o_indice_cobre_area_seguida_da_ordenacao_do_modelo(self):
        """O índice tem de casar com o que o admin realmente pede.

        `AuditEventAdmin` filtra por `area` e a lista herda `Meta.ordering`. Um
        índice que não siga exatamente essa forma é peso morto: paga escrita e
        nunca é escolhido, nem quando as áreas crescerem.
        """
        esperado = ["area", *AuditEvent._meta.ordering]
        # `Meta.ordering` usa `-pk`; o índice precisa nomear a coluna concreta.
        esperado = [campo.replace("pk", "id") for campo in esperado]

        formas = [list(indice.fields) for indice in AuditEvent._meta.indexes]

        self.assertIn(
            esperado,
            formas,
            f"nenhum índice de `AuditEvent` cobre {esperado}. Declarados: {formas}",
        )

    def test_o_admin_ainda_filtra_por_area(self):
        """A outra ponta do contrato.

        Se `area` sair do `list_filter`, o índice acima perde o único consumidor
        que ele tem — e a linha do `DB-12` no catálogo passa a descrever outra
        coisa.
        """
        self.assertIn("area", AuditEventAdmin.list_filter)

    def test_a_trilha_nao_tem_leitor_em_codigo_de_aplicacao(self):
        """O que sustenta a frase acima, e que é fácil de esquecer.

        Se um dia uma view ou selector passar a ler `AuditEvent`, a análise do
        `DB-12` precisa ser refeita: o índice passaria a servir uma consulta com
        outra forma, e o número de áreas deixaria de ser o único gatilho.
        """
        from pathlib import Path

        from django.conf import settings

        raiz = Path(settings.BASE_DIR)
        permitidos = {"core/models.py", "core/audit.py", "core/admin.py", "core/checks.py"}
        achados = []
        for caminho in raiz.glob("*/*.py"):
            rel = caminho.relative_to(raiz).as_posix()
            if rel in permitidos or "/migrations/" in rel or "test" in rel:
                continue
            if "AuditEvent" in caminho.read_text(encoding="utf-8", errors="ignore"):
                achados.append(rel)

        self.assertEqual(
            achados,
            [],
            "`AuditEvent` ganhou leitor fora do admin — refaça a análise do `DB-12`",
        )
