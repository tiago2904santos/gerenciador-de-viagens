import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import clear_url_caches

import config.urls
import core.urls


class UILabRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ui-lab-tester",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def _reload_core_urls(self):
        importlib.reload(core.urls)
        importlib.reload(config.urls)
        clear_url_caches()

    @override_settings(DEBUG=True)
    def test_ui_lab_returns_200_when_debug_true(self):
        self._reload_core_urls()

        response = self.client.get("/dev/ui-lab/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dev/ui_lab/index.html")
        self.assertContains(response, "UI Lab")

    @override_settings(DEBUG=True)
    def test_ui_lab_subpages_return_200_for_valid_routes(self):
        self._reload_core_urls()

        valid_routes = [
            "/dev/ui-lab/structures/",
            "/dev/ui-lab/headers/",
            "/dev/ui-lab/buttons/",
            "/dev/ui-lab/fields/",
            "/dev/ui-lab/selects-filters/",
            "/dev/ui-lab/status/",
            "/dev/ui-lab/feedback/",
            "/dev/ui-lab/cards/",
            "/dev/ui-lab/overlays/",
            "/dev/ui-lab/tables/",
            "/dev/ui-lab/documents/",
            "/dev/ui-lab/signature/",
        ]

        for route in valid_routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_ui_lab_returns_404_for_invalid_route(self):
        self._reload_core_urls()

        response = self.client.get("/dev/ui-lab/invalid-section/")

        self.assertEqual(response.status_code, 404)

    def test_ui_lab_is_not_available_when_debug_false(self):
        self._reload_core_urls()

        response = self.client.get("/dev/ui-lab/")

        self.assertEqual(response.status_code, 404)
