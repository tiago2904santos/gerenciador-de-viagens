from django.test import TestCase
from django.urls import reverse


class LoginPublicAccessTests(TestCase):
    def test_login_get_nao_redireciona_para_si_mesmo(self):
        response = self.client.get(reverse("core:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/login.html")

    def test_login_com_next_para_login_nao_entra_em_loop(self):
        response = self.client.get(reverse("core:login"), {"next": "/login/"})

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Location", ""), "/login/?next=/login/")
