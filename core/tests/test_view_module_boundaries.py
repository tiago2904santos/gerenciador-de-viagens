import importlib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from scripts.audit_django_architecture import contar_orm_em_views


APP_MODULES = {
    "planos_trabalho": (
        "view_helpers",
        "list_views",
        "identification_views",
        "per_diem_views",
        "activity_views",
        "document_views",
    ),
    "oficios": (
        "view_helpers",
        "list_views",
        "traveler_views",
        "route_views",
        "wizard_document_views",
        "api_views",
    ),
}


class ViewModuleBoundaryTests(SimpleTestCase):
    def test_facades_views_ficam_enxutas(self):
        root = Path(settings.BASE_DIR)
        for app in APP_MODULES:
            with self.subTest(app=app):
                lines = (root / app / "views.py").read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(len(lines), 160)

    def test_fluxos_sao_divididos_em_modulos_por_tela(self):
        root = Path(settings.BASE_DIR)
        for app, modules in APP_MODULES.items():
            for module in modules:
                with self.subTest(app=app, module=module):
                    imported = importlib.import_module(f"{app}.{module}")
                    lines = (root / app / f"{module}.py").read_text(encoding="utf-8").splitlines()
                    self.assertIsNotNone(imported)
                    self.assertLessEqual(len(lines), 500)

    def test_urls_continuam_apontando_para_a_fachada_publica(self):
        for app in APP_MODULES:
            views = importlib.import_module(f"{app}.views")
            urls = importlib.import_module(f"{app}.urls")
            public_callables = {
                value
                for name, value in vars(views).items()
                if not name.startswith("_") and callable(value)
            }
            for pattern in urls.urlpatterns:
                callback = pattern.callback
                with self.subTest(app=app, route_name=pattern.name):
                    self.assertIn(callback, public_callables)

    def test_fatiamento_nao_esconde_divida_orm_da_catraca(self):
        counts = contar_orm_em_views()

        self.assertEqual(counts["oficios"], 4)
        self.assertEqual(sum(counts.values()), 32)
