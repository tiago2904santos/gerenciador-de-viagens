"""`PF-03` — toda requisição autenticada abria transação de escrita na sessão.

`SESSION_SAVE_EVERY_REQUEST = True` custava, no painel, 11 consultas com 2 em
`django_session` e 2 de `BEGIN`/`COMMIT`. Toda página, todo XHR de autosave, todo
polling de documento.

Desligar aquilo sozinho troca um custo por um defeito: a sessão passaria a expirar
8 h depois do **login**, não da última ação. `RenovacaoDeSessaoMiddleware` devolve
o deslizamento com uma escrita a cada `SESSION_RENOVACAO_INTERVALO` segundos.

Os testes cobrem as três coisas que podem dar errado, nesta ordem de gravidade:

1. **o usuário ser deslogado no meio do trabalho** — a renovação tem de acontecer;
2. **o cookie sobreviver ao fechamento do navegador** — a armadilha do
   `set_expiry`, que este desenho evita de propósito;
3. **o ganho não existir** — a contagem de consultas.
"""

from __future__ import annotations

import time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from core.middleware import CHAVE_RENOVACAO_DE_SESSAO
from core.testing import area_de_teste, vincular_area

ROTA = "core:dashboard"


class BaseSessao(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = area_de_teste(sigla="PF03")
        cls.user = get_user_model().objects.create_user(username="usuario_pf03")
        vincular_area(cls.user, cls.area, area_padrao=True)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse(ROTA)


class CustoDaSessaoTests(BaseSessao):
    def test_a_requisicao_nao_escreve_mais_na_tabela_de_sessao(self):
        """O defeito, medido: `django_session` sai do caminho de escrita.

        A primeira requisição ainda grava, porque é ela que marca a renovação.
        A segunda, dentro do intervalo, não pode gravar nada.
        """
        self.client.get(self.url)  # a que renova

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)

        sessao = [q for q in ctx.captured_queries if "django_session" in q["sql"]]
        self.assertEqual(
            sessao, [], f"ainda há escrita de sessão: {[q['sql'][:80] for q in sessao]}",
        )


class CustoDaTransacaoTests(TransactionTestCase):
    """Os `BEGIN`/`COMMIT`, que eram 2 das 11 consultas.

    **`TransactionTestCase` e não `TestCase`, e isso é o teste.** Dentro de
    `TestCase` tudo já roda numa transação, então um `atomic()` aninhado emite
    `SAVEPOINT` em vez de `BEGIN`/`COMMIT` e a asserção passa mesmo com
    `SESSION_SAVE_EVERY_REQUEST` ligado — medido: a primeira versão deste teste
    passava dos dois jeitos e não provava nada.
    """

    def setUp(self):
        self.area = area_de_teste(sigla="PF03T")
        self.user = get_user_model().objects.create_user(username="usuario_pf03_tx")
        vincular_area(self.user, self.area, area_padrao=True)
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse(ROTA)

    def test_a_requisicao_nao_abre_mais_transacao(self):
        self.client.get(self.url)  # a que renova

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)

        transacao = [
            q for q in ctx.captured_queries if q["sql"].strip().upper() in {"BEGIN", "COMMIT"}
        ]
        self.assertEqual(
            transacao, [], f"a requisição ainda abre transação: {len(transacao)} comandos",
        )


class RenovacaoTests(BaseSessao):
    """O que impede a economia de virar "usuário deslogado no meio do trabalho"."""

    def test_a_primeira_requisicao_marca_a_renovacao(self):
        self.client.get(self.url)

        self.assertIn(CHAVE_RENOVACAO_DE_SESSAO, self.client.session)

    def test_dentro_do_intervalo_nao_renova_de_novo(self):
        self.client.get(self.url)
        marca = self.client.session[CHAVE_RENOVACAO_DE_SESSAO]

        self.client.get(self.url)

        self.assertEqual(self.client.session[CHAVE_RENOVACAO_DE_SESSAO], marca)

    def test_passado_o_intervalo_renova(self):
        """**O teste que impede o deslogamento.**

        Sem esta renovação, `SESSION_SAVE_EVERY_REQUEST = False` faria a sessão
        contar a partir do login. Com ela, cada janela de intervalo empurra o
        `expire_date` para "agora + `SESSION_COOKIE_AGE`".
        """
        self.client.get(self.url)
        sessao = self.client.session
        sessao[CHAVE_RENOVACAO_DE_SESSAO] = time.time() - 10_000
        sessao.save()
        antiga = sessao[CHAVE_RENOVACAO_DE_SESSAO]

        self.client.get(self.url)

        self.assertGreater(self.client.session[CHAVE_RENOVACAO_DE_SESSAO], antiga)

    def test_a_renovacao_empurra_a_expiracao_no_banco(self):
        """O efeito que interessa não é a chave, é o `expire_date` da linha."""
        from django.contrib.sessions.models import Session

        self.client.get(self.url)
        chave = self.client.session.session_key
        sessao = self.client.session
        sessao[CHAVE_RENOVACAO_DE_SESSAO] = time.time() - 10_000
        sessao.save()
        antes = Session.objects.get(session_key=chave).expire_date

        self.client.get(self.url)

        depois = Session.objects.get(session_key=chave).expire_date
        self.assertGreater(depois, antes)

    @override_settings(SESSION_RENOVACAO_INTERVALO=0)
    def test_intervalo_zero_desliga_a_renovacao(self):
        """A saída de emergência, caso a renovação precise ser desligada em produção."""
        self.client.get(self.url)

        self.assertNotIn(CHAVE_RENOVACAO_DE_SESSAO, self.client.session)


class ExpiracaoAoFecharNavegadorTests(BaseSessao):
    """A armadilha que este desenho existe para evitar.

    A forma "óbvia" de renovar é `set_expiry(agora + idade)`. Ela funciona **e**
    escreve em `_session_expiry`, o que faz `get_expire_at_browser_close()`
    devolver `False` (`sessions/backends/base.py:403`): o cookie ganha `expires` e
    **sobrevive ao fechamento do navegador**, anulando
    `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` sem ninguém perceber.
    """

    def test_a_sessao_continua_expirando_ao_fechar_o_navegador(self):
        self.client.get(self.url)

        self.assertTrue(
            self.client.session.get_expire_at_browser_close(),
            "a renovação passou a escrever em `_session_expiry` e o cookie "
            "deixou de expirar ao fechar o navegador",
        )

    def test_o_cookie_nao_ganha_data_de_expiracao(self):
        """A outra metade, vista do cookie e não da sessão."""
        resposta = self.client.get(self.url)

        cookie = resposta.cookies.get("sessionid")
        if cookie is None:
            self.skipTest("esta requisição não regravou o cookie")
        self.assertEqual(cookie["expires"], "")
        self.assertEqual(cookie["max-age"], "")


class UsuarioAnonimoTests(TestCase):
    def test_visitante_anonimo_nao_ganha_linha_de_sessao(self):
        """Renovar sessão vazia criaria linha em `django_session` para todo visitante."""
        from django.contrib.sessions.models import Session

        Client().get(reverse("core:login"))

        self.assertEqual(Session.objects.count(), 0)
