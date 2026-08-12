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
        # estava **dentro de uma docstring**, porque a contagem era regex sobre o
        # texto do arquivo. O `NOVO-11` trocou a contagem para a arvore sintatica
        # (`contar_orm_no_codigo`); a troca nao mudou o numero — 29 por regex e
        # 29 por `ast`, mesmos apps, medido em 07/08 — porque hoje nenhum modulo
        # de view tem `.objects` em prosa. O teste abaixo garante que prosa nunca
        # mais entra na conta.
        #
        # 29 -> 24: o painel de `/` foi apagado a pedido do dono, e com ele as
        # cinco consultas que `core.views.dashboard` fazia por acesso — total de
        # oficios, oficios em rascunho, assinaturas pendentes, prestacoes
        # pendentes e as viagens dos proximos 30 dias. Era a rota que TODO login
        # abre (`LOGIN_REDIRECT_URL`), entao a divida mais cara do arquivo caiu
        # junto com a tela.
        #
        # 24 -> 33 (`BE-14` fatia 1, `NOVO-100`): **o numero subiu, e subiu de
        # proposito.** Prestacoes foi fatiada em modulos por tela como oficios e
        # planos, mas os cinco modulos nunca entraram em `P06_SPLIT_VIEW_MODULES`
        # — entao 11 acessos de manager nunca foram medidos. A regra 5 do
        # `AGENTS.md` proibe a catraca subir por regressao; esta subiu por
        # honestidade, ao passar a medir o que ja estava la. A propria fatia ja
        # devolveu 2 dos 11 (`rt_views.py` foi a zero), e o saldo entra como 9.
        #
        # 33 -> 31 (`BE-14` fatia 3): a persistencia dos anexos assinados saiu de
        # `document_views.py` para `anexo_services.py`, e com ela os dois acessos de
        # manager que restavam ali. Agora a catraca desce, que e o sentido normal.
        #
        # 31 -> 27 (`BE-14` fatia 4): `diario_views.py` foi a zero. Um acesso saiu
        # junto com a sincronizacao da previa do RT, dois `get_or_create` viraram
        # `diario_services.obter_ou_criar_diario` (get_or_create **grava**, entao vai
        # para service e nao para selector) e a consulta de oficios do
        # auto-preenchimento virou `selectors.oficios_para_prefill_de_motorista`.
        # Os 3 que sobram em prestacoes sao leituras de `model_views.py`, o CRUD dos
        # modelos de texto do RT — divida de `P-01`, nao do `BE-14`.
        self.assertEqual(counts["prestacoes_contas"], 3)
        self.assertEqual(sum(counts.values()), 27)

    def test_orm_em_prosa_nao_conta_e_orm_em_codigo_conta(self):
        """`NOVO-11` — a catraca mede código, não texto.

        Com a regex antiga este snippet contaria 4 (docstring e comentário
        inclusos) e o teste reprovaria; por `ast` contam só o acesso real e a
        expressão de f-string, que É código.
        """
        snippet = (
            '"""Antes montava isto de `Oficio.objects` cru na view."""\n'
            "def lista(request):\n"
            "    # nada de Roteiro.all_objects aqui\n"
            "    visiveis = Oficio.objects.count()\n"
            '    return f"{Roteiro.objects.count()} de {visiveis}"\n'
        )

        self.assertEqual(contar_orm_no_codigo(snippet), 2)

    def test_views_nao_executam_geradores_documentais_pesados(self):
        self.assertEqual(sync_document_generations_in_views(), [])
