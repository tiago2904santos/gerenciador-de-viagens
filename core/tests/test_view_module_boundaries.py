import importlib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from scripts.audit_django_architecture import contar_orm_em_views
from scripts.audit_django_architecture import contar_orm_no_codigo
from scripts.audit_django_architecture import sync_document_generations_in_views


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
        # 32 → 30: NOVO-24 zerou `usuarios` e NOVO-25 tirou das views de
        # Eventos, Termos e OS as tres copias do rotulo da sede. O numero
        # so desce (AGENTS.md, regra 5).
        #
        # 30 → 29 (`NOVO-07`): saiu a unica ocorrencia de `justificativas` — que
        # estava dentro de uma docstring, o que motivou o `NOVO-11`. Desde ele a
        # contagem e por AST; a coincidencia de o numero nao mudar na troca foi
        # medida: em 07/08 nenhuma docstring de view citava `.objects`.
        self.assertEqual(sum(counts.values()), 29)

    def test_a_catraca_conta_codigo_e_ignora_prosa(self):
        # `NOVO-11`: a versao por regex casava `.objects` em docstring e
        # comentario. Prosa segurava a catraca no alto (numero maior do que o
        # ORM real) e, no sentido inverso, explicar em texto um ORM recem
        # removido fazia o CI reprovar um PR correto.
        so_prosa = (
            '"""a versao anterior montava isto de `Oficio.objects` cru."""\n'
            "# e este comentario cita Roteiro.objects.filter(...)\n"
            "x = 1\n"
        )
        self.assertEqual(contar_orm_no_codigo(so_prosa), 0)

        codigo_real = (
            "def lista(request):\n"
            '    """explica o Evento.objects que saiu daqui."""\n'
            "    a = Oficio.objects.filter(ativo=True)\n"
            "    b = Roteiro.all_objects.count()\n"
            "    return a, b\n"
        )
        self.assertEqual(contar_orm_no_codigo(codigo_real), 2)

    def test_views_nao_executam_geradores_documentais_pesados(self):
        self.assertEqual(sync_document_generations_in_views(), [])
