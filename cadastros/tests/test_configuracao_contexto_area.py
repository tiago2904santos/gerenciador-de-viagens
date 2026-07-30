"""Documentos devem usar a configuração da área do próprio registro.

Sem request (Celery, shell, testes isolados), `get_current_area()` é None e
`ConfiguracaoSistema.get_singleton()` cai na config legada `area=NULL`. Essa
config costuma ter o Destinatário/assinantes globais — não os "Assinantes
padrão por documento" da área ativa. Resultado: ofício, OS, plano etc. saem
com a chefia errada.
"""

from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase
from django.test import TestCase

from cadastros.models import AssinaturaConfiguracao
from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.selectors import build_configuracao_context
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio
from ordens_servico.docxtpl_context import build_os_docxtpl_context
from ordens_servico.models import OrdemServico
from planos_trabalho.docxtpl_context import build_plano_docxtpl_context
from planos_trabalho.models import PlanoTrabalho
from usuarios.models import AreaTrabalho


class ConfiguracaoContextPorAreaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = AreaTrabalho.objects.create(nome="Área Doc", sigla="DOC", ativa=True)
        cls.cargo_dest = Cargo.objects.create(nome="DELEGADO DESTINATARIO", area=cls.area)
        cls.cargo_ass = Cargo.objects.create(nome="ASSESSOR ASSINANTE", area=cls.area)
        cls.destinatario = Servidor.objects.create(
            nome="DESTINATARIO OFICIO",
            cargo=cls.cargo_dest,
            area=cls.area,
        )
        cls.assinante = Servidor.objects.create(
            nome="ASSINANTE DOCUMENTOS",
            cargo=cls.cargo_ass,
            area=cls.area,
        )

        cls.cfg_area = ConfiguracaoSistema.get_for_area(cls.area)
        cls.cfg_area.destinatario_oficio = cls.destinatario
        cls.cfg_area.destinatario_oficio_nome = cls.destinatario.nome
        cls.cfg_area.destinatario_oficio_cargo = cls.cargo_dest.nome
        cls.cfg_area.save()
        for tipo in (
            AssinaturaConfiguracao.OFICIO,
            AssinaturaConfiguracao.ORDEM_SERVICO,
            AssinaturaConfiguracao.PLANO_TRABALHO,
            AssinaturaConfiguracao.JUSTIFICATIVA,
        ):
            AssinaturaConfiguracao.objects.update_or_create(
                configuracao=cls.cfg_area,
                tipo=tipo,
                ordem=1,
                defaults={"servidor": cls.assinante, "ativo": True},
            )

        # Config legada sem área: assinantes = destinatário (o bug observado).
        cls.cfg_global, _ = ConfiguracaoSistema.objects.get_or_create(
            area=None,
            defaults={"prazo_justificativa_dias": 10},
        )
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cls.cfg_global,
            tipo=AssinaturaConfiguracao.OFICIO,
            ordem=1,
            defaults={"servidor": cls.destinatario, "ativo": True},
        )
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cls.cfg_global,
            tipo=AssinaturaConfiguracao.ORDEM_SERVICO,
            ordem=1,
            defaults={"servidor": cls.destinatario, "ativo": True},
        )
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cls.cfg_global,
            tipo=AssinaturaConfiguracao.PLANO_TRABALHO,
            ordem=1,
            defaults={"servidor": cls.destinatario, "ativo": True},
        )

    def test_sem_area_ainda_resolve_legado_global(self):
        inst = build_configuracao_context(area=None)
        nomes = [r["nome"] for r in (inst.get("assinaturas") or {}).get("ORDEM_SERVICO", [])]
        self.assertIn(self.destinatario.nome, nomes)

    def test_com_area_usa_assinante_padrao_da_area(self):
        inst = build_configuracao_context(area=self.area)
        nomes = [r["nome"] for r in (inst.get("assinaturas") or {}).get("ORDEM_SERVICO", [])]
        self.assertEqual(nomes, [self.assinante.nome])
        self.assertEqual(inst["destinatario_oficio_nome"], self.destinatario.nome)

    def test_os_sem_request_usa_area_da_ordem(self):
        ordem = OrdemServico.objects.create(
            area=self.area,
            data_evento_inicio=date(2026, 8, 10),
            data_evento_fim=date(2026, 8, 12),
            motivo="teste area",
        )
        ctx = build_os_docxtpl_context(ordem)
        self.assertEqual(ctx["nome_chefia"].casefold(), "Assinante Documentos".casefold())
        self.assertNotIn("Destinatario", ctx["nome_chefia"])

    def test_oficio_sem_request_usa_area_do_oficio(self):
        oficio = Oficio.objects.create(
            area=self.area,
            motivo="teste",
            data_criacao=date(2026, 8, 10),
        )
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["nome_chefia"].casefold(), "Assinante Documentos".casefold())
        self.assertEqual(ctx["nome_destinatario"].casefold(), "Destinatario Oficio".casefold())

    def test_plano_sem_request_usa_area_do_plano(self):
        plano = PlanoTrabalho.objects.create(
            area=self.area,
            data_evento_inicio=date(2026, 8, 10),
            data_evento_fim=date(2026, 8, 12),
        )
        ctx = build_plano_docxtpl_context(plano)
        self.assertEqual(ctx["nome_chefia"].casefold(), "Assinante Documentos".casefold())


class AssinaturaFallbackNaoUsaChefiaGenericaTests(SimpleTestCase):
    def test_assinatura_nome_cargo_sem_rows_nao_inventa_chefia_quando_fallback_off(self):
        from oficios.docxtpl_context import _assinatura_nome_cargo

        nome, cargo = _assinatura_nome_cargo(
            {"assinaturas": {}, "nome_chefia": "FALLBACK", "cargo_chefia": "CARGO"},
            "ORDEM_SERVICO",
            fallback_geral=False,
        )
        self.assertEqual(nome, "")
        self.assertEqual(cargo, "")
