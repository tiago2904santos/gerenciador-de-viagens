from django.contrib.auth import get_user_model
from django.test import TestCase

from integracoes.google_drive.models import DriveCredenciais
from integracoes.google_drive.services import esta_autorizado
from integracoes.google_drive.services import get_credenciais
from integracoes.google_drive.services import get_pasta_raiz_id


class DriveCredenciaisUsuarioTests(TestCase):
    def test_resolve_credenciais_e_pasta_por_usuario(self):
        User = get_user_model()
        tsantos = User.objects.create_user(username="tsantos", email="adm.tsantos@pc.pr.gov.br")
        dpcap = User.objects.create_user(username="dpcap", email="adm.dpcap@pc.pr.gov.br")
        DriveCredenciais.objects.create(
            usuario=tsantos,
            access_token="token-tsantos",
            refresh_token="refresh-tsantos",
            pasta_raiz_id="pasta-tsantos",
        )
        DriveCredenciais.objects.create(
            usuario=dpcap,
            access_token="token-dpcap",
            refresh_token="refresh-dpcap",
            pasta_raiz_id="pasta-dpcap",
        )

        self.assertEqual(get_credenciais(tsantos).access_token, "token-tsantos")
        self.assertEqual(get_credenciais(dpcap).access_token, "token-dpcap")
        self.assertEqual(get_pasta_raiz_id(tsantos), "pasta-tsantos")
        self.assertEqual(get_pasta_raiz_id(dpcap), "pasta-dpcap")
        self.assertTrue(esta_autorizado(tsantos))
        self.assertTrue(esta_autorizado(dpcap))

    def test_sem_usuario_usa_credencial_global_legada(self):
        DriveCredenciais.objects.create(
            access_token="token-global",
            refresh_token="refresh-global",
            pasta_raiz_id="pasta-global",
        )

        self.assertEqual(get_credenciais().access_token, "token-global")
        self.assertEqual(get_pasta_raiz_id(), "pasta-global")
