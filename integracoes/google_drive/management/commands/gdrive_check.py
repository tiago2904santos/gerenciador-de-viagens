from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.errors import capture


class Command(BaseCommand):
    help = (
        "Verifica configuração, autorização e a pasta raiz do Google Drive. "
        "Com --e2e, envia um arquivo de teste, confere que ele chegou e o apaga."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--e2e",
            action="store_true",
            help=(
                "Prova de ponta a ponta: cria um arquivo na pasta raiz, confirma pela "
                "API que ele existe e apaga em seguida. Só roda com MODO=ativo."
            ),
        )

    def handle(self, *args, **options):
        cfg = getattr(settings, "GOOGLE_DRIVE", {})
        modo = cfg.get("MODO", "mock")
        client_id = cfg.get("CLIENT_ID", "")
        client_secret = cfg.get("CLIENT_SECRET", "")
        redirect_uri = cfg.get("REDIRECT_URI", "")
        raiz_id = cfg.get("PASTA_RAIZ_ID", "")
        upload_em_mock = cfg.get("UPLOAD_EM_MOCK", False)

        self.stdout.write(f"GOOGLE_DRIVE_MODO         : {modo}")
        self.stdout.write(f"GOOGLE_CLIENT_ID          : {'(definido)' if client_id else '(não definido)'}")
        self.stdout.write(f"GOOGLE_CLIENT_SECRET      : {'(definido)' if client_secret else '(não definido)'}")
        self.stdout.write(f"GOOGLE_REDIRECT_URI       : {redirect_uri or '(não definido)'}")
        self.stdout.write(f"GOOGLE_DRIVE_PASTA_RAIZ_ID: {raiz_id or '(não definido no .env; pode vir do banco)'}")
        self.stdout.write(f"GOOGLE_DRIVE_UPLOAD_EM_MOCK: {upload_em_mock}")
        self.stdout.write("")

        # Modo ativo sem client OAuth falha adiante com "nenhuma credencial
        # armazenada", que manda o operador procurar no lugar errado.
        if modo != "mock" and not (client_id and client_secret):
            raise CommandError(
                "MODO=ativo sem GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET. O botão Conectar "
                "vai voltar do Google com 'invalid_client'. Preencha os dois no .env."
            )

        from integracoes.google_drive.services import get_credenciais

        creds = get_credenciais()
        if creds:
            self.stdout.write(self.style.SUCCESS(f"OAuth autorizado. Token atualizado em: {creds.atualizado_em:%d/%m/%Y %H:%M}"))
            self.stdout.write(f"Expiry: {creds.token_expiry}")
            self.stdout.write(f"Scope : {creds.scope}")
            if not (creds.refresh_token or "").strip():
                self.stdout.write(self.style.ERROR(
                    "SEM REFRESH TOKEN: o acesso morre quando o token expirar (~1h) e "
                    "não há como renovar. Reconecte a conta."
                ))

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
            return None

        if not creds:
            raise CommandError("Sem credencial OAuth no banco: conecte a conta antes.")

        self.stdout.write("")
        self.stdout.write("Conferindo a pasta raiz...")
        from integracoes.google_drive.services import (
            _reset_client,
            estado_pasta_raiz,
            get_pasta_raiz_id,
        )

        _reset_client()
        estado = estado_pasta_raiz(usar_cache=False)
        if not estado.configurada:
            raise CommandError(estado.motivo)
        if not estado.ok:
            raise CommandError(f"Pasta raiz inutilizável: {estado.motivo}")
        self.stdout.write(self.style.SUCCESS(
            f'Pasta raiz OK: "{estado.nome}" (id={estado.pasta_id})'
        ))

        if not options.get("e2e"):
            self.stdout.write("")
            self.stdout.write("Rode com --e2e para provar o envio de ponta a ponta.")
            return None

        self._e2e(get_pasta_raiz_id())

    def _e2e(self, raiz_id: str) -> None:
        """Cria, confere e apaga um arquivo de verdade na pasta raiz."""
        from datetime import datetime

        from integracoes.google_drive.services import get_client

        client = get_client()
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        nome = f"_teste-integracao-{carimbo}.txt"
        conteudo = f"Teste de integração do gerenciador de viagens em {carimbo}.\n".encode()

        self.stdout.write("")
        self.stdout.write(f"Enviando {nome}...")
        file_id = None
        try:
            file_id, url = client.upload(nome, conteudo, "text/plain", raiz_id)
            self.stdout.write(self.style.SUCCESS(f"Upload OK: id={file_id}"))
            self.stdout.write(f"URL: {url}")

            # Só o upload não prova nada: um arquivo criado dentro de pasta
            # lixeirada também devolve id. A busca filtra `trashed = false`,
            # então ela é a prova de que o arquivo está VISÍVEL na raiz.
            encontrado = client.buscar_arquivo_por_nome(nome, raiz_id)
            if encontrado == file_id:
                self.stdout.write(self.style.SUCCESS("Arquivo encontrado na pasta raiz — a integração está funcionando."))
            else:
                raise CommandError(
                    "O arquivo subiu mas NÃO foi encontrado na pasta raiz. "
                    "Verifique se a pasta (ou algum pai dela) está na lixeira."
                )
        except CommandError:
            raise
        except Exception as exc:
            capture(exc, "drive.management.commands.gdrive_check._e2e")
            raise CommandError(f"Falha no teste de ponta a ponta: {exc}") from exc
        finally:
            if file_id:
                client.excluir_arquivo(file_id)
                self.stdout.write(f"Arquivo de teste removido ({file_id}).")
