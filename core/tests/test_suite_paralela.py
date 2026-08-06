"""`--parallel` engolia a falha inteira por falta do `tblib` (NOVO-17).

O runner paralelo do Django roda cada subsuíte num processo filho e devolve o
resultado por `multiprocessing`, o que exige **picklar o `sys.exc_info()`** da
falha. Objeto `traceback` não é picklável pela stdlib; o `tblib` é justamente a
biblioteca que ensina o pickle a serializá-lo, e o Django o usa quando está
instalado (`django/test/runner.py:164`).

Ele **não estava** em `requirements/`. Medido com duas asserções triviais
falhando, `--parallel 4`:

| | sem `tblib` | com `tblib` |
|---|---|---|
| falhas relatadas (`FAIL:`) | **0** | **2** |
| saída | 125 linhas, terminando em `TypeError: cannot pickle 'traceback' object` | 53 linhas, terminando em `FAILED (failures=2)` |

Zero: a corrida **abortava** no primeiro erro e não relatava nenhuma falha no
formato de sempre. O Django até imprime "you should install tblib" e o nome do
teste — mas lá em cima, soterrado por ~100 linhas de `RemoteTraceback` do
`multiprocessing`. Quem lê o fim da saída vê só o `TypeError` e conclui
instabilidade de infraestrutura.

O enunciado original do `NOVO-17` culpava "asserção que falha carregando o
arquivo inteiro na mensagem". Não é o tamanho do payload: **qualquer** falha
fazia isso.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, runner

RAIZ = Path(settings.BASE_DIR)
TEST_TXT = RAIZ / "requirements" / "test.txt"
TEST_LOCK = RAIZ / "requirements" / "test-lock.txt"


class TblibChegaAoRunnerTests(SimpleTestCase):
    def test_o_runner_paralelo_do_django_enxerga_o_tblib(self):
        """`runner.tblib is None` é exatamente o estado que produzia o defeito."""
        self.assertIsNotNone(
            runner.tblib,
            "sem `tblib` importável, toda falha em `--parallel` vira "
            "`TypeError: cannot pickle 'traceback' object` e a corrida aborta "
            "sem dizer qual teste falhou",
        )

    def test_o_traceback_sobrevive_ao_pickle(self):
        """A capacidade em si, não só o import.

        Roda em subprocesso porque `pickling_support.install()` mexe no
        `copyreg` do processo inteiro — no runner isso acontece dentro do
        worker, e não vale contaminar o processo desta suíte para provar.
        """
        codigo = (
            "import pickle, sys\n"
            "import tblib.pickling_support as ps\n"
            "ps.install()\n"
            "try:\n"
            "    raise ValueError('falha de mentira')\n"
            "except ValueError:\n"
            "    tipo, exc, tb = sys.exc_info()\n"
            "vivo = pickle.loads(pickle.dumps((tipo, exc, tb)))\n"
            "assert vivo[2] is not None, 'o traceback voltou vazio do pickle'\n"
        )
        resultado = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            resultado.returncode,
            0,
            "o traceback não sobreviveu ao pickle:\n" + resultado.stderr,
        )


class TblibEstaDeclaradoTests(SimpleTestCase):
    """O CI instala de `test-lock.txt`, não do que está na máquina de quem roda.

    Sem esta rede, o defeito volta em silêncio: a suíte segue verde na máquina
    de quem já tem o pacote e o CI perde o relato de falha de novo.
    """

    def test_o_tblib_esta_na_fonte_das_dependencias_de_teste(self):
        self.assertIn("tblib", TEST_TXT.read_text(encoding="utf-8"))

    def test_o_tblib_esta_no_lock_que_o_ci_instala(self):
        # `assertRegex` sobre o arquivo inteiro despejaria as ~100 linhas de
        # hash do `coverage` na mensagem de falha. A busca fica aqui e a
        # asserção recebe só o veredito.
        fixado = re.search(
            r"^tblib==\d+\.\d+", TEST_LOCK.read_text(encoding="utf-8"), re.MULTILINE
        )
        self.assertIsNotNone(
            fixado,
            "`tests.yml` instala `requirements/test-lock.txt`; fora dali o "
            "pacote não chega ao CI",
        )
