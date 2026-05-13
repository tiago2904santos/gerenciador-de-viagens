import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import clear_url_caches

import config.urls
import core.urls


class DevUILabTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ui-lab-tester",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def _reload_urls(self):
        importlib.reload(core.urls)
        importlib.reload(config.urls)
        clear_url_caches()

    @override_settings(DEBUG=True)
    def test_ui_lab_returns_200_when_debug_true(self):
        self._reload_urls()

        response = self.client.get("/dev/ui-lab/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dev/ui_lab.html")

    @override_settings(DEBUG=False)
    def test_ui_lab_returns_404_when_debug_false(self):
        self._reload_urls()

        response = self.client.get("/dev/ui-lab/")

        self.assertEqual(response.status_code, 404)
