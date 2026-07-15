from django.test import TestCase

from integracoes.google_drive.models import DriveCredenciais
from integracoes.google_drive.services import esta_autorizado
from integracoes.google_drive.services import get_credenciais
from integracoes.google_drive.services import get_pasta_raiz_id
from usuarios.models import AreaTrabalho


class DriveCredenciaisAreaTests(TestCase):
    def test_resolve_credenciais_e_pasta_por_area(self):
        ascom = AreaTrabalho.objects.create(nome="Assessoria de Comunicacao Social", sigla="ASCOM")
        dpcap = AreaTrabalho.objects.create(nome="DPCAP", sigla="DPCAP")
        DriveCredenciais.objects.create(
            area=ascom,
            access_token="token-ascom",
            refresh_token="refresh-ascom",
            pasta_raiz_id="pasta-ascom",
        )
        DriveCredenciais.objects.create(
            area=dpcap,
            access_token="token-dpcap",
            refresh_token="refresh-dpcap",
            pasta_raiz_id="pasta-dpcap",
        )

        self.assertEqual(get_credenciais(ascom).access_token, "token-ascom")
        self.assertEqual(get_credenciais(dpcap).access_token, "token-dpcap")
        self.assertEqual(get_pasta_raiz_id(ascom), "pasta-ascom")
        self.assertEqual(get_pasta_raiz_id(dpcap), "pasta-dpcap")
        self.assertTrue(esta_autorizado(ascom))
        self.assertTrue(esta_autorizado(dpcap))

    def test_sem_area_usa_credencial_global_legada(self):
        DriveCredenciais.objects.create(
            access_token="token-global",
            refresh_token="refresh-global",
            pasta_raiz_id="pasta-global",
        )

        self.assertEqual(get_credenciais().access_token, "token-global")
        self.assertEqual(get_pasta_raiz_id(), "pasta-global")
