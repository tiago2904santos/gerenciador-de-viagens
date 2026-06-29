from __future__ import annotations

import datetime
import enum
import json
import uuid
from decimal import Decimal
from typing import Any, Mapping

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Model
from django.db.models.query import QuerySet

from documentos.models import DocumentoArtefato
from documentos.services.facade import DocumentoGerado
from documentos.services.timing import measure_step

_MAX_SNAPSHOT_DEPTH = 48


def _sanear_objeto_para_json(val: Any, *, _depth: int = 0) -> Any:
    """
    Converte valores arbitrários do contexto/payload documental em tipos aceites por JSONField
    (inclui instâncias de modelos Django aninhados, QuerySets, datas, etc.).
    """
    if _depth > _MAX_SNAPSHOT_DEPTH:
        return "<profundidade-maxima>"
    if val is None or isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, enum.Enum):
        return val.value
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, datetime.time):
        return val.isoformat()
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, bytearray):
        return bytes(val).decode("utf-8", errors="replace")
    if isinstance(val, memoryview):
        return val.tobytes().decode("utf-8", errors="replace")
    if isinstance(val, Model):
        return str(val)
    if isinstance(val, QuerySet):
        return [_sanear_objeto_para_json(x, _depth=_depth + 1) for x in val[:2000]]
    if isinstance(val, dict):
        return {str(k): _sanear_objeto_para_json(v, _depth=_depth + 1) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_sanear_objeto_para_json(x, _depth=_depth + 1) for x in val]
    if isinstance(val, set):
        return [_sanear_objeto_para_json(x, _depth=_depth + 1) for x in sorted(val, key=lambda x: str(x))]
    return str(val)


def _payload_snapshot_json_seguro(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Garante estrutura compatível com JSONField e com o adaptador JSON do psycopg."""
    raw = _sanear_objeto_para_json(dict(snapshot or {}))
    return json.loads(json.dumps(raw, default=str))


def persist_geracao(
    doc: DocumentoGerado,
    *,
    oficio_id: int | None = None,
    servidor_id: int | None = None,
    evento_id: int | None = None,
    nome_drive: str = "",
    payload_snapshot: Mapping[str, Any] | None = None,
    cache_key: str = "",
    engine: str = "",
    generator_version: str = "",
) -> DocumentoArtefato | None:
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        return None
    nome = doc.nome_arquivo
    arquivo = ContentFile(doc.conteudo, name=nome)
    payload_snapshot = _payload_snapshot_json_seguro(payload_snapshot)
    gen_ver = generator_version or str(getattr(settings, "DOCUMENTOS_GENERATOR_VERSION", "1") or "1")
    with measure_step(
        "persist_geracao",
        {
            "tipo": doc.tipo.value,
            "formato": doc.formato.value,
            "oficio_id": oficio_id,
            "servidor_id": servidor_id,
            "evento_id": evento_id,
        },
    ):
        return DocumentoArtefato.objects.create(
            tipo=doc.tipo.value,
            formato=doc.formato.value,
            oficio_id=oficio_id,
            servidor_id=servidor_id,
            evento_id=evento_id,
            nome_drive=nome_drive or "",
            payload_snapshot=payload_snapshot,
            hash_sha256=doc.hash_sha256,
            arquivo=arquivo,
            cache_key=cache_key or "",
            engine=engine or "",
            generator_version=gen_ver,
        )


