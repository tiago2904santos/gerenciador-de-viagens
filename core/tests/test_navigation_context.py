from unittest.mock import patch

from django.test import RequestFactory
from django.test import SimpleTestCase

from core.context_processors import navigation


class NavigationContextProcessorTests(SimpleTestCase):
    def test_componentes_reutilizam_navegacao_na_mesma_requisicao(self):
        """PF-05: Cotton invoca processadores de contexto a cada componente."""
        request = RequestFactory().get("/oficios/")
        items = [{"label": "Ofícios", "url": "/oficios/"}]

        with patch(
            "core.context_processors.build_navigation",
            return_value=items,
        ) as build:
            primeiro = navigation(request)
            segundo = navigation(request)

        self.assertEqual(primeiro, {"navigation_items": items})
        self.assertEqual(segundo, primeiro)
        build.assert_called_once_with(request)
