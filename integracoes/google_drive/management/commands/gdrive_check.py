from django.conf import settings
from django.core.management.base import BaseCommand

from core.errors import capture


class Command(BaseCommand):
    help = "Verifica configuração e status de autorização do Google Drive"

    def handle(self, *args, **options):
        cfg = getattr(settings, "GOOGLE_DRIVE", {})
        modo = cfg.get("MODO", "mock")
        client_id = cfg.get("CLIENT_ID", "")
        redirect_uri = cfg.get("REDIRECT_URI", "")
        raiz_id = cfg.get("PASTA_RAIZ_ID", "")
        upload_em_mock = cfg.get("UPLOAD_EM_MOCK", False)

        self.stdout.write(f"GOOGLE_DRIVE_MODO         : {modo}")
        self.stdout.write(f"GOOGLE_CLIENT_ID          : {'(definido)' if client_id else '(não definido)'}")
        self.stdout.write(f"GOOGLE_REDIRECT_URI       : {redirect_uri or '(não definido)'}")
        self.stdout.write(f"GOOGLE_DRIVE_PASTA_RAIZ_ID: {raiz_id or '(não definido)'}")
        self.stdout.write(f"GOOGLE_DRIVE_UPLOAD_EM_MOCK: {upload_em_mock}")
        self.stdout.write("")

        from integracoes.google_drive.services import get_credenciais

        creds = get_credenciais()
        if creds:
            self.stdout.write(self.style.SUCCESS(f"OAuth autorizado. Token atualizado em: {creds.atualizado_em:%d/%m/%Y %H:%M}"))
            self.stdout.write(f"Expiry: {creds.token_expiry}")
            self.stdout.write(f"Scope : {creds.scope}")

            from integracoes.google_drive.services import escopo_faltante

            faltando = escopo_faltante()
            if faltando:
                self.stdout.write("")
                self.stdout.write(self.style.ERROR(
                    "ESCOPO INSUFICIENTE: a autorização salva não inclui "
                    + ", ".join(faltando) + "."
                ))
                self.stdout.write(self.style.ERROR(
                    "A renovação do token vai falhar com 'invalid_scope' e o upload "
                    "não chega ao Drive. Reconecte a conta em Configurações > Google Drive."
                ))
        else:
            self.stdout.write(self.style.WARNING("OAuth não autorizado. Nenhuma credencial no banco."))
            self.stdout.write("Para autorizar: acesse /integracoes/google-drive/oauth/iniciar/ no navegador.")

        if modo == "mock":
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Modo mock ativo — uploads não chegam ao Drive real."))
            self.stdout.write("Para ativar: defina GOOGLE_DRIVE_MODO=ativo no .env.")
            return

        if not creds:
            return

        self.stdout.write("")
        self.stdout.write("Testando client real...")
        try:
            from integracoes.google_drive.services import _RealClient, _reset_client
            _reset_client()
            client = _RealClient()
            self.stdout.write(self.style.SUCCESS("Client OAuth inicializado com sucesso."))

            if raiz_id:
                import datetime
                now = datetime.datetime.now()
                ano_id = client.get_or_create_pasta(str(now.year), raiz_id)
                self.stdout.write(self.style.SUCCESS(f"Pasta {now.year} acessível → id={ano_id}"))
            else:
                self.stdout.write(self.style.WARNING("GOOGLE_DRIVE_PASTA_RAIZ_ID não definido — pulando teste de pasta."))
        except Exception as exc:
            capture(exc, "drive.management.commands.gdrive_check.handle")  # pragma: no cover
            self.stdout.write(self.style.ERROR(f"Falha: {exc}"))
