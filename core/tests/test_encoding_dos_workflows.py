"""QA-11 — os workflows do GitHub Actions são UTF-8 sem BOM.

`reparar-producao.yml` estava em UTF-16LE com CRLF, único entre os quatro. O
GitHub documenta suporte a BOM UTF-8/16/32, então provavelmente funcionava — o
risco era não se ter certeza, e esse é justamente o workflow de **reparo manual
de produção**: o que se descobriria quebrado durante um incidente.

Pior: o texto dentro dele já estava com mojibake ("produ├º├úo"), sinal de arquivo
UTF-8 salvo como UTF-16 por editor do Windows. O nome do workflow aparece assim na
interface do Actions.

Este teste é a catraca. Um `.yml` novo salvo pelo editor errado reprova aqui, em
vez de só ser notado quando alguém precisar dele às pressas.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"


def _workflows():
    return sorted((Path(settings.BASE_DIR) / ".github" / "workflows").glob("*.yml"))


class EncodingDosWorkflowsTests(SimpleTestCase):
    def test_existem_workflows_para_conferir(self):
        """Guarda contra o teste virar vácuo se o diretório mudar de lugar."""
        self.assertGreater(len(_workflows()), 0)

    def test_todos_sao_utf8_sem_bom(self):
        problemas = []
        for arquivo in _workflows():
            bruto = arquivo.read_bytes()
            if bruto.startswith((BOM_UTF16_LE, BOM_UTF16_BE)):
                problemas.append(f"{arquivo.name}: UTF-16 (BOM)")
                continue
            if bruto.startswith(BOM_UTF8):
                problemas.append(f"{arquivo.name}: UTF-8 com BOM")
                continue
            try:
                bruto.decode("utf-8")
            except UnicodeDecodeError as exc:
                problemas.append(f"{arquivo.name}: não decodifica como UTF-8 ({exc.reason})")

        self.assertEqual(problemas, [], msg=f"workflows fora do padrão: {problemas}")

    def test_nenhum_tem_mojibake_de_dupla_codificacao(self):
        """`ç` virando `├º` é o rastro de UTF-8 relido como CP850.

        Não é cosmético: o nome do workflow aparece na interface do Actions, e o
        `description` dos inputs aparece no formulário de `workflow_dispatch` —
        exatamente onde alguém está sob pressão durante um incidente.
        """
        suspeitos = ("├", "Ã©", "Ã£", "Ãµ", "Ã§", "â€")
        problemas = [
            f"{arquivo.name}: {marca!r}"
            for arquivo in _workflows()
            for marca in suspeitos
            if marca in arquivo.read_text(encoding="utf-8", errors="replace")
        ]

        self.assertEqual(problemas, [], msg=f"texto com dupla codificação: {problemas}")
