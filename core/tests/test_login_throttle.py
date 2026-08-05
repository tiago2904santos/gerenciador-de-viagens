"""QA-01 — as duas portas de login precisam ter o mesmo limite de tentativas.

`/admin/` concede superusuário e não passava por `core.views.LoginView`: o
`AdminSite` tem view de login própria. Medido antes da correção, 10 POSTs de
senha errada devolviam 200 dez vezes ali, enquanto o login da aplicação bloqueava
no sexto com 429. A política de senha era a única barreira.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils.crypto import get_random_string

from core import login_throttle


class LoginThrottleParidadeTests(TestCase):
    def setUp(self):
        cache.clear()
        # Gerada a cada execução, não commitada: uma senha literal com aparência de
        # credencial real é indistinguível de segredo de verdade para o scanner e
        # para quem lê. Mesmo critério do `S-01` do ciclo anterior, onde a tentativa
        # de manter literais "descartáveis" foi reprovada pelo GitGuardian.
        self.usuario = "chefe"
        self.senha = get_random_string(24)
        self.senha_errada = get_random_string(24)
        get_user_model().objects.create_superuser(
            username=self.usuario,
            email="chefe@exemplo.gov.br",
            password=self.senha,
        )

    def _credenciais(self, usuario=None, senha=None):
        """Monta o payload de login por variável, nunca com valores literais.

        O detector genérico de credencial do GitGuardian dispara pelo **padrão** —
        as duas chaves de login lado a lado com valores literais —, não pelo valor.
        Ele reprova mesmo quando a senha é obviamente descartável. Manter os valores
        em atributos resolve sem afrouxar nada.
        """
        return {
            "username": usuario or self.usuario,
            "password": senha or self.senha_errada,
        }

    def _tentar(self, url, vezes):
        return [self.client.post(url, self._credenciais()) for _ in range(vezes)]

    def test_login_do_admin_bloqueia_apos_o_limite(self):
        url = reverse("admin:login")

        respostas = self._tentar(url, login_throttle.LIMITE + 3)

        codigos = [r.status_code for r in respostas]
        self.assertNotIn(
            429,
            codigos[: login_throttle.LIMITE],
            msg=f"bloqueou antes do limite: {codigos}",
        )
        self.assertEqual(
            codigos[login_throttle.LIMITE :],
            [429] * 3,
            msg=f"esperava 429 depois de {login_throttle.LIMITE} falhas, veio: {codigos}",
        )

    def test_login_da_aplicacao_bloqueia_no_mesmo_ponto(self):
        url = reverse("core:login")

        codigos = [r.status_code for r in self._tentar(url, login_throttle.LIMITE + 1)]

        self.assertEqual(codigos[-1], 429, msg=f"veio: {codigos}")

    def test_o_balde_e_por_usuario_e_nao_tranca_conta_alheia(self):
        """Errar a senha de um usuário não pode trancar a porta de outro."""
        url = reverse("admin:login")
        self._tentar(url, login_throttle.LIMITE + 1)

        resposta = self.client.post(url, self._credenciais(usuario="outro"))

        self.assertNotEqual(resposta.status_code, 429)

    def test_login_correto_no_admin_continua_funcionando(self):
        resposta = self.client.post(
            reverse("admin:login"),
            self._credenciais(senha=self.senha),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.wsgi_request.user.is_authenticated)

    def test_a_url_do_admin_continua_reversivel_pelo_nome_do_django(self):
        """O wrapper não pode quebrar o `next` nem os redirects internos do admin."""
        self.assertEqual(reverse("admin:login"), "/admin/login/")
