from unittest import mock

from django.test import TestCase

from core.testing import area_de_teste
from core.testing import com_request
from eventos.forms import EventoNovoCadastroForm
from eventos.models import Evento
from eventos.models import TipoEvento
from eventos.services import salvar_identificacao_evento
from oficios.models import Oficio
from ordens_servico.models import OrdemServico
from planos_trabalho.models import PlanoTrabalho
from roteiros.models import Roteiro
from termos.models import TermoAutorizacao


class SalvarIdentificacaoEventoTests(TestCase):
    def setUp(self):
        self.area = area_de_teste()
        self.evento = Evento.objects.create(
            area=self.area,
            titulo="Titulo anterior",
            motivo="Motivo anterior",
        )
        self.tipo_anterior = TipoEvento.objects.create(
            area=self.area,
            nome="Tipo anterior",
        )
        self.tipo_novo = TipoEvento.objects.create(
            area=self.area,
            nome="Tipo novo",
        )
        self.evento.tipos.add(self.tipo_anterior)
        self.oficio = Oficio.objects.create(area=self.area, numero=91, ano=2026)
        self.ordem_servico = OrdemServico.objects.create(
            area=self.area,
            numero=91,
            ano=2026,
        )
        self.plano_trabalho = PlanoTrabalho.objects.create(
            area=self.area,
            numero=91,
            ano=2026,
        )
        self.termo = TermoAutorizacao.objects.create(area=self.area)
        self.roteiro = Roteiro.objects.create(area=self.area)

    def _form_valido(self):
        with com_request(self.area):
            form = EventoNovoCadastroForm(
                data={
                    "tipos": [self.tipo_novo.pk],
                    "motivo": "Motivo novo",
                    "destino_uf": "PR",
                    "destino_cidade": "Curitiba",
                    "oficios_vinculados": [self.oficio.pk],
                    "ordens_servico_vinculadas": [self.ordem_servico.pk],
                    "planos_trabalho_vinculados": [self.plano_trabalho.pk],
                    "termos_vinculados": [self.termo.pk],
                    "roteiros_vinculados": [self.roteiro.pk],
                },
                instance=self.evento,
            )
            self.assertTrue(form.is_valid(), form.errors.as_json())
        return form

    def test_falha_no_termo_desfaz_evento_m2m_e_documentos_vinculados(self):
        form = self._form_valido()

        with mock.patch(
            "eventos.services.garantir_termo_automatico",
            side_effect=RuntimeError("falha depois dos vinculos"),
        ):
            with self.assertRaisesRegex(RuntimeError, "falha depois dos vinculos"):
                salvar_identificacao_evento(
                    form,
                    area=self.area,
                    destinos_json='[{"uf":"PR","cidade":"Curitiba"}]',
                )

        self.evento.refresh_from_db()
        self.assertEqual(self.evento.titulo, "Titulo anterior")
        self.assertEqual(self.evento.motivo, "Motivo anterior")
        self.assertEqual(list(self.evento.tipos.all()), [self.tipo_anterior])
        for documento in (
            self.oficio,
            self.ordem_servico,
            self.plano_trabalho,
            self.termo,
            self.roteiro,
        ):
            documento.refresh_from_db()
            self.assertIsNone(documento.evento_id)

    def test_sucesso_persiste_a_etapa_completa(self):
        evento = salvar_identificacao_evento(
            self._form_valido(),
            area=self.area,
            destinos_json=(
                '[{"uf":"PR","cidade":"Curitiba"},'
                '{"uf":"SC","cidade":"Florianopolis"}]'
            ),
        )

        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Tipo novo")
        self.assertEqual(evento.motivo, "Motivo novo")
        self.assertEqual(evento.destino_uf, "PR")
        self.assertEqual(evento.destino_cidade, "Curitiba")
        self.assertEqual(
            evento.destinos_extras,
            [{"uf": "SC", "cidade": "Florianopolis"}],
        )
        self.assertEqual(list(evento.tipos.all()), [self.tipo_novo])
        for documento in (
            self.oficio,
            self.ordem_servico,
            self.plano_trabalho,
            self.termo,
            self.roteiro,
        ):
            documento.refresh_from_db()
            self.assertEqual(documento.evento_id, evento.pk)
        self.assertEqual(evento.termos_autorizacao.count(), 1)
