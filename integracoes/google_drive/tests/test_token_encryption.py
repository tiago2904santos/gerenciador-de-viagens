from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from integracoes.google_drive.models import DriveCredenciais


class DriveTokenEncryptionTests(TestCase):
    def test_tokens_sao_criptografados_no_banco_e_transparentes_no_modelo(self):
        usuario = get_user_model().objects.create_user(username="oauth-encrypted")
        credencial = DriveCredenciais.objects.create(
            usuario=usuario,
            access_token="access-secret",
            refresh_token="refresh-secret",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token, refresh_token "
                "FROM google_drive_drivecredenciais WHERE id = %s",
                [credencial.pk],
            )
            raw_access, raw_refresh = cursor.fetchone()

        self.assertTrue(raw_access.startswith("enc::"))
        self.assertTrue(raw_refresh.startswith("enc::"))
        self.assertNotIn("access-secret", raw_access)
        self.assertNotIn("refresh-secret", raw_refresh)

        recarregada = DriveCredenciais.objects.get(pk=credencial.pk)
        self.assertEqual(recarregada.access_token, "access-secret")
        self.assertEqual(recarregada.refresh_token, "refresh-secret")
