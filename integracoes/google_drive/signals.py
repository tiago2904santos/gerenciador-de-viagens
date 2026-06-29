from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def conectar() -> None:
    from django.db.models.signals import post_save
    from documentos.models import DocumentoArtefato

    post_save.connect(_upload_pos_persist, sender=DocumentoArtefato, dispatch_uid="gdrive_upload_artefato")


def _upload_pos_persist(sender, instance, created: bool, **kwargs) -> None:
    if not created:
        return

    from django.conf import settings

    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    modo = cfg.get("MODO", "mock").lower()
    upload_em_mock = cfg.get("UPLOAD_EM_MOCK", False)

    if modo == "mock" and not upload_em_mock:
        return

    try:
        from integracoes.google_drive.models import DriveArquivo
        from integracoes.google_drive.services import is_mock, mimetype_para_formato, upload_artefato

        if DriveArquivo.objects.filter(artefato=instance).exists():
            return

        result = upload_artefato(instance)
        if result is None:
            return

        file_id, url = result
        nome = ""
        if instance.arquivo:
            nome = instance.arquivo.name.rsplit("/", 1)[-1]

        DriveArquivo.objects.create(
            artefato=instance,
            file_id=file_id,
            url=url,
            nome=nome,
            mime_type=mimetype_para_formato(instance.formato),
            mock=is_mock(),
        )
    except Exception as exc:
        logger.error("[Drive] erro no signal para artefato %s: %s", instance.pk, exc, exc_info=True)
