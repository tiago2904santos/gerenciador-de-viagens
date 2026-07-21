"""Abas temporais/estado das listas de documentos (core.documento_abas).

Exercita a lógica compartilhada através da lista de Ofícios: recorte temporal
(futuras × atuais), aba derivada de Finalizados (prestação finalizada) e
precedência de Cancelados.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Q
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import documento_abas as tabs
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from prestacoes_contas.models import PrestacaoServidor
from roteiros.models import Roteiro


class DocumentoAbasOficioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="abas", password="x")
        self.client.force_login(self.user)

    def _oficio(self, numero, *, saida_offset=None, cancelado=False):
        roteiro = None
        if saida_offset is not None:
            saida = timezone.now() + timedelta(days=saida_offset)
            roteiro = Roteiro.objects.create(saida_dt=saida)
        oficio = Oficio.objects.create(numero=numero, ano=2026, roteiro=roteiro, cancelado=cancelado)
        return oficio

    def _base_anotada(self, queryset):
        sub = PrestacaoServidor.objects.filter(prestacao__oficio=OuterRef("pk"))
        return tabs.anotar_finalizacao(queryset, sub, sub.filter(finalizada=False))

    def _abas_do(self, pk):
        """Conjunto de abas em que o ofício ``pk`` aparece (deve ser exatamente uma)."""
        sub = PrestacaoServidor.objects.filter(prestacao__oficio=OuterRef("pk"))
        base = tabs.anotar_finalizacao(Oficio.objects.filter(pk=pk), sub, sub.filter(finalizada=False))
        presentes = set()
        for aba in tabs.ABAS_VALIDAS:
            if base.filter(
                tabs.q_da_aba(aba, date_field="roteiro__saida_dt__date", cancelado_q=Q(cancelado=True))
            ).exists():
                presentes.add(aba)
        return presentes

    def test_futura_vs_atuais(self):
        futuro = self._oficio(1, saida_offset=5)
        passado = self._oficio(2, saida_offset=-5)
        sem_data = self._oficio(3)  # sem roteiro
        self.assertEqual(self._abas_do(futuro.pk), {tabs.ABA_FUTURAS})
        self.assertEqual(self._abas_do(passado.pk), {tabs.ABA_ATUAIS})
        self.assertEqual(self._abas_do(sem_data.pk), {tabs.ABA_ATUAIS})

    def test_finalizado_quando_prestacao_finalizada(self):
        from cadastros.models import Servidor

        oficio = self._oficio(1, saida_offset=-5)
        servidor = Servidor.objects.create(nome="Servidor A", cpf="12345678901")
        oficio.servidores.add(servidor)
        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        ps = prestacao.servidores_prestacao.get()
        self.assertEqual(self._abas_do(oficio.pk), {tabs.ABA_ATUAIS})
        ps.definir_finalizada(True)
        self.assertEqual(self._abas_do(oficio.pk), {tabs.ABA_FINALIZADOS})

    def test_cancelado_tem_precedencia(self):
        oficio = self._oficio(1, saida_offset=5, cancelado=True)
        # Mesmo com viagem futura, um cancelado só aparece em "Cancelados".
        self.assertEqual(self._abas_do(oficio.pk), {tabs.ABA_CANCELADOS})

    def test_abas_sao_mutuamente_exclusivas_e_exaustivas(self):
        self._oficio(1, saida_offset=5)
        self._oficio(2, saida_offset=-5)
        self._oficio(3, cancelado=True)
        contagem = tabs.contar_por_aba(
            self._base_anotada(Oficio.objects.all()),
            date_field="roteiro__saida_dt__date",
            cancelado_q=Q(cancelado=True),
        )
        self.assertEqual(sum(contagem.values()), Oficio.objects.count())

    def test_index_padrao_mostra_aba_futuras(self):
        self._oficio(1, saida_offset=5)
        self._oficio(2, saida_offset=-5)
        resp = self.client.get(reverse("oficios:index"))
        self.assertEqual(resp.context["aba"], tabs.ABA_FUTURAS)
        # Só o ofício futuro aparece na aba padrão.
        self.assertEqual(len(resp.context["cards"]), 1)
