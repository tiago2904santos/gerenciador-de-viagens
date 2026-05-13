from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from assinaturas.models import AssinaturaDigital
from assinaturas.models import EventoAssinatura
from assinaturas.services.carimbo_pdf import DadosCarimbo
from assinaturas.services.carimbo_pdf import aplicar_carimbo_pdf
from assinaturas.services.codigos import gerar_codigo_verificacao
from assinaturas.services.hash import calcular_sha256_bytes
from documentos.models import DocumentoArtefato
from documentos.services.persistence import atualizar_apos_assinatura


def mascarar_cpf_assinatura(cpf: str) -> str:
    digits = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    if len(digits) == 11:
        return f"***.{digits[3:6]}.{digits[6:9]}-**"
    if not digits:
        return "—"
    return digits


def _montar_url_validacao(request: HttpRequest | None, codigo: str) -> str:
    try:
        rel = reverse("assinaturas:assinatura-verificar-codigo", kwargs={"codigo": codigo})
    except Exception:  # noqa: BLE001 — rota ainda não registada em alguns testes
        rel = f"/assinaturas/verificar/{codigo}/"
    if request is not None:
        return request.build_absolute_uri(rel)
    return urljoin("http://127.0.0.1/", rel.lstrip("/"))


def _validar_artefato_pdf(artefato: DocumentoArtefato) -> bytes:
    if (artefato.formato or "").lower() != "pdf":
        raise ValueError("O artefato tem de estar em formato PDF para assinatura com etiqueta.")
    if not artefato.arquivo or not getattr(artefato.arquivo, "name", ""):
        raise ValueError("O artefato não tem ficheiro PDF associado.")
    try:
        data = artefato.arquivo.read()
    except OSError as exc:
        raise ValueError("Não foi possível ler o PDF do artefato.") from exc
    if len(data) < 8 or not data[:8].startswith(b"%PDF"):
        raise ValueError("O ficheiro do artefato não parece ser um PDF válido.")
    return data


def assinar_artefato_com_etiqueta(
    artefato: DocumentoArtefato,
    *,
    nome_assinante: str,
    cpf_assinante: str = "",
    email_assinante: str = "",
    cargo_assinante: str = "",
    documento_label: str = "",
    usuario: AbstractBaseUser | None = None,
    metodo_autenticacao: str = "validacao_cpf",
    request: HttpRequest | None = None,
    posicao: dict | None = None,
) -> AssinaturaDigital:
    pdf_bytes = _validar_artefato_pdf(artefato)
    hash_original = calcular_sha256_bytes(pdf_bytes)

    codigo_verificacao = gerar_codigo_verificacao()
    url_validacao = _montar_url_validacao(request, codigo_verificacao)

    dados = DadosCarimbo(
        nome_assinante=nome_assinante or "—",
        cpf_mascarado=mascarar_cpf_assinatura(cpf_assinante),
        data_hora_assinatura=timezone.now(),
        codigo_verificacao=codigo_verificacao,
        url_validacao=url_validacao,
        cargo_assinante=cargo_assinante,
        documento_label=documento_label,
        hash_curto=hash_original[:12],
    )

    pdf_assinado, position_meta = aplicar_carimbo_pdf(pdf_bytes, dados, posicao)
    hash_assinado = calcular_sha256_bytes(pdf_assinado)

    atualizar_apos_assinatura(artefato, pdf_assinado=pdf_assinado, backend="etiqueta_pdf")
    artefato.refresh_from_db()

    ip = None
    ua = ""
    if request is not None:
        ip = request.META.get("REMOTE_ADDR") or None
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:4000]

    appearance: dict[str, Any] = {
        "label_width_pt": position_meta.get("label_width_pt"),
        "label_height_pt": position_meta.get("label_height_pt"),
        "qr_size_pt": position_meta.get("qr_size_pt"),
        "bg": "#08172a",
        "fg": "#f8fafc",
        "font_title": "Times-Bold",
        "font_body": "Times-Roman",
    }
    evidencias: dict[str, Any] = {
        "backend": "etiqueta_pdf",
        "position_meta": position_meta,
        "usuario_id": str(usuario.pk) if usuario is not None and getattr(usuario, "pk", None) else "",
    }

    reg = AssinaturaDigital.objects.create(
        artefato=artefato,
        chave=None,
        status=AssinaturaDigital.STATUS_VALID,
        codigo_verificacao=codigo_verificacao,
        nome_assinante=nome_assinante[:160],
        cpf_assinante=cpf_assinante[:14],
        email_assinante=(email_assinante or "")[:254],
        metodo_autenticacao=metodo_autenticacao[:40],
        ip_assinatura=ip,
        user_agent=ua,
        hash_documento=hash_original,
        hash_documento_assinado=hash_assinado,
        posicao_carimbo_json=dict(position_meta),
        pagina_carimbo=int(position_meta.get("page_number") or 1),
        url_validacao=url_validacao[:600],
        appearance=appearance,
        evidencias=evidencias,
    )
    EventoAssinatura.objects.create(
        assinatura=reg,
        tipo="assinatura_etiqueta_pdf",
        payload={"codigo_verificacao": codigo_verificacao},
    )
    return reg


def assinatura_arquivo_esta_integra(assinatura: AssinaturaDigital) -> bool:
    artefato = assinatura.artefato
    field = artefato.arquivo_assinado
    if not field or not getattr(field, "name", ""):
        return False
    try:
        field.open("rb")
        data = field.read()
    except OSError:
        return False
    digest = calcular_sha256_bytes(data)
    esperado = (assinatura.hash_documento_assinado or "").strip().lower()
    return bool(esperado) and digest == esperado
