from django.test import TestCase

from oficios.models import Oficio
from oficios.services import obter_roteiro_escolhido_do_post
from oficios.services import vincular_roteiro_ao_oficio_sem_copia
from oficios.views import _resolver_roteiro_rascunho_autosave
from roteiros.models import Roteiro
from usuarios.models import AreaTrabalho


class OficioRoteiroAreaIsolationTests(TestCase):
    def setUp(self):
        self.area_a = AreaTrabalho.objects.create(nome="Área A", sigla="AREA-A")
        self.area_b = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        self.oficio = Oficio.objects.create(area=self.area_a)
        self.roteiro_outra_area = Roteiro.objects.create(
            area=self.area_b,
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
        )

    def test_picker_nao_resolve_roteiro_avulso_de_outra_area(self):
        result = obter_roteiro_escolhido_do_post(
            {
                "roteiro_modo": "EVENTO_EXISTENTE",
                "roteiro_id": str(self.roteiro_outra_area.pk),
            },
            area=self.area_a,
        )
        self.assertIsNone(result)

    def test_autosave_nao_resolve_rascunho_de_outra_area(self):
        result = _resolver_roteiro_rascunho_autosave(
            {"autosave_obj_id": str(self.roteiro_outra_area.pk)},
            oficio=self.oficio,
        )
        self.assertIsNone(result)

    def test_servico_recusa_vinculo_cruzado_mesmo_com_objeto_direto(self):
        with self.assertRaisesRegex(ValueError, "outra área"):
            vincular_roteiro_ao_oficio_sem_copia(
                self.oficio,
                self.roteiro_outra_area,
            )
