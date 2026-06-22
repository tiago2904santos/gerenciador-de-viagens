"""Assinatura eletrônica de RT e Diário de Bordo.

Fluxo: a partir da tela do documento gera-se um link (``emitir_link``) enviado por
WhatsApp ao signatário. O signatário confirma identidade (5 primeiros dígitos do CPF +
nome) e envia uma assinatura (nome em fonte manuscrita OU desenho à mão) renderizada
como PNG transparente no navegador. O servidor apenas **carimba** esse PNG sobre o
snapshot do PDF (``arquivo_origem``) e guarda o resultado em ``arquivo_assinado``.

O carimbo é puro Python (reportlab + pypdf) e independe do motor de geração de PDF.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone

from .models import AssinaturaDocumento
from .models import DiarioBordo
from .models import RelatorioTecnico


class AssinaturaError(Exception):
    """Erro amigável exibido ao usuário (ex.: signatário sem CPF, link expirado)."""


# ─────────────────────────────────────────────────────────────────
# Resolução do signatário
# ─────────────────────────────────────────────────────────────────

def signer_do_documento(prestacao, tipo: str):
    """Servidor que deve assinar o documento, ou ``None`` se indefinido.

    RT → servidor da prestação. DB → motorista do ofício (quando é um Servidor
    cadastrado; motorista manual não tem CPF e não pode assinar).
    """
    if tipo == AssinaturaDocumento.TIPO_RT:
        return prestacao.servidor
    if tipo == AssinaturaDocumento.TIPO_DB:
        return getattr(prestacao.oficio, "motorista", None)
    return None


def _cpf_valido(servidor) -> bool:
    cpf = (getattr(servidor, "cpf", "") or "").strip()
    return len(cpf) == 11 and cpf.isdigit()


def _label_documento(tipo: str) -> str:
    return dict(AssinaturaDocumento.TIPO_CHOICES).get(tipo, tipo)


def _label_signatario(tipo: str) -> str:
    return "servidor" if tipo == AssinaturaDocumento.TIPO_RT else "motorista"


# ─────────────────────────────────────────────────────────────────
# Geração do snapshot (PDF não assinado)
# ─────────────────────────────────────────────────────────────────

def _gerar_origem_bytes(prestacao, tipo: str) -> bytes:
    if tipo == AssinaturaDocumento.TIPO_RT:
        from .services import gerar_relatorio_tecnico_pdf

        relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=prestacao)
        return gerar_relatorio_tecnico_pdf(relatorio)

    from .diario_services import gerar_diario_bordo_pdf

    diario, _ = DiarioBordo.objects.get_or_create(prestacao=prestacao)
    return gerar_diario_bordo_pdf(diario)


# ─────────────────────────────────────────────────────────────────
# Emissão / consulta de link
# ─────────────────────────────────────────────────────────────────

def emitir_link(prestacao, tipos, dias: int = 7, forcar: bool = False):
    """Cria/atualiza o link de assinatura para os ``tipos`` pendentes.

    Documentos já assinados são ignorados (a menos de ``forcar``). Levanta
    ``AssinaturaError`` se nenhum documento puder ser incluído ou se algum
    signatário não tiver CPF cadastrado. Retorna ``(token, [docs])``.
    """
    tipos = [t for t in dict.fromkeys(tipos) if t in dict(AssinaturaDocumento.TIPO_CHOICES)]
    if not tipos:
        raise AssinaturaError("Selecione ao menos um documento para assinar.")

    resolvidos = []
    for tipo in tipos:
        signer = signer_do_documento(prestacao, tipo)
        if signer is None:
            raise AssinaturaError(
                f"O {_label_documento(tipo)} não tem {_label_signatario(tipo)} definido para assinar."
            )
        if not _cpf_valido(signer):
            raise AssinaturaError(
                f"O {_label_signatario(tipo)} \"{signer}\" não tem CPF cadastrado; "
                "cadastre o CPF para poder gerar o link de assinatura."
            )
        resolvidos.append((tipo, signer))

    token = secrets.token_urlsafe(32)
    agora = timezone.now()
    expira = agora + timedelta(days=max(1, int(dias)))

    incluidos = []
    for tipo, signer in resolvidos:
        doc, _ = AssinaturaDocumento.objects.get_or_create(
            prestacao=prestacao,
            tipo=tipo,
            defaults={"signer": signer},
        )
        if doc.status == AssinaturaDocumento.STATUS_ASSINADA and not forcar:
            continue
        if forcar:
            _limpar_assinatura(doc)
        doc.signer = signer
        doc.nome_esperado = signer.nome
        doc.status = AssinaturaDocumento.STATUS_PENDENTE
        doc.identidade_confirmada_em = None
        doc.link_token = token
        doc.link_criado_em = agora
        doc.link_expira_em = expira
        origem = _gerar_origem_bytes(prestacao, tipo)
        doc.arquivo_origem.save(f"{tipo}_origem.pdf", ContentFile(origem), save=False)
        doc.save()
        incluidos.append(doc)

    if not incluidos:
        raise AssinaturaError("Os documentos selecionados já estão assinados.")
    return token, incluidos


def documentos_do_link(token: str):
    """Documentos válidos (token confere e link não expirado), em ordem RT→DB."""
    if not token:
        return []
    docs = list(
        AssinaturaDocumento.objects.select_related(
            "prestacao__oficio", "signer"
        ).filter(link_token=token)
    )
    validos = [d for d in docs if not d.link_expirado]
    ordem = {AssinaturaDocumento.TIPO_RT: 0, AssinaturaDocumento.TIPO_DB: 1}
    validos.sort(key=lambda d: ordem.get(d.tipo, 9))
    return validos


def documento_do_link(token: str, tipo: str):
    for doc in documentos_do_link(token):
        if doc.tipo == tipo:
            return doc
    return None


def proximo_pendente(token: str):
    for doc in documentos_do_link(token):
        if doc.status != AssinaturaDocumento.STATUS_ASSINADA:
            return doc
    return None


# ─────────────────────────────────────────────────────────────────
# Identidade
# ─────────────────────────────────────────────────────────────────

def validar_identidade(doc: AssinaturaDocumento, cpf5: str) -> bool:
    """Confere os 5 primeiros dígitos do CPF do signatário."""
    digitos = "".join(ch for ch in str(cpf5 or "") if ch.isdigit())[:5]
    esperado = doc.cpf_prefixo_esperado
    if len(esperado) < 5 or digitos != esperado:
        return False
    doc.identidade_confirmada_em = timezone.now()
    doc.save(update_fields=["identidade_confirmada_em", "atualizado_em"])
    return True


# ─────────────────────────────────────────────────────────────────
# Carimbo da assinatura
# ─────────────────────────────────────────────────────────────────

def _limpar_assinatura(doc: AssinaturaDocumento) -> None:
    for field in ("arquivo_assinado", "assinatura_png"):
        arquivo = getattr(doc, field)
        if arquivo:
            arquivo.delete(save=False)
    doc.modo = ""
    doc.fonte = ""
    doc.pos_x = doc.pos_y = doc.largura = doc.altura = None
    doc.pagina = 0
    doc.assinado_em = None
    doc.assinado_ip = ""
    doc.codigo_verificacao = ""


def _carimbar_pdf(origem_bytes, png_bytes, *, pagina, x, y, w, h, nome, codigo) -> bytes:
    from pypdf import PdfReader
    from pypdf import PdfWriter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    reader = PdfReader(BytesIO(origem_bytes))
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:
            pass

    total = len(reader.pages)
    if total == 0:
        raise AssinaturaError("O documento não possui páginas para assinar.")
    idx = max(0, min(int(pagina or 0), total - 1))

    page = reader.pages[idx]
    if page.rotation:
        # Normaliza páginas giradas (ex.: diário em paisagem) para a mediabox bater
        # com o que foi exibido ao signatário.
        page.transfer_rotation_to_content()

    page_w = float(page.mediabox.width)
    page_h = float(page.mediabox.height)

    # Frações vêm do navegador com origem no topo-esquerdo; PDF tem origem embaixo.
    box_w = max(1.0, float(w) * page_w)
    box_h = max(1.0, float(h) * page_h)
    box_x = float(x) * page_w
    box_y_bottom = page_h - (float(y) * page_h) - box_h

    overlay_buf = BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))
    image = ImageReader(BytesIO(png_bytes))
    c.drawImage(
        image,
        box_x,
        box_y_bottom,
        width=box_w,
        height=box_h,
        mask="auto",
        preserveAspectRatio=True,
        anchor="sw",
    )
    legenda = f"Assinado eletronicamente por {nome} em {timezone.localtime().strftime('%d/%m/%Y %H:%M')} — cód {codigo}"
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.30, 0.36, 0.43)
    cap_y = max(2.0, box_y_bottom - 8)
    c.drawString(box_x, cap_y, legenda[:120])
    c.save()
    overlay_buf.seek(0)

    overlay_page = PdfReader(overlay_buf).pages[0]
    page.merge_page(overlay_page)

    writer = PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    out = BytesIO()
    writer.write(out)
    writer.close()
    return out.getvalue()


def aplicar_assinatura(doc, *, png_bytes, modo, fonte, pagina, x, y, w, h, ip="") -> None:
    """Carimba o PNG da assinatura sobre o snapshot e marca o documento como assinado."""
    if not doc.arquivo_origem:
        raise AssinaturaError("Não há documento de origem para assinar; gere o link novamente.")
    if not png_bytes:
        raise AssinaturaError("Assinatura não recebida. Tente novamente.")

    with doc.arquivo_origem.open("rb") as f:
        origem_bytes = f.read()

    codigo = secrets.token_hex(4).upper()
    nome = doc.nome_esperado or (str(doc.signer) if doc.signer_id else "")
    assinado = _carimbar_pdf(
        origem_bytes,
        png_bytes,
        pagina=pagina,
        x=x,
        y=y,
        w=w,
        h=h,
        nome=nome,
        codigo=codigo,
    )

    doc.modo = modo if modo in dict(AssinaturaDocumento.MODO_CHOICES) else AssinaturaDocumento.MODO_FONTE
    doc.fonte = (fonte or "")[:60]
    doc.pagina = int(pagina or 0)
    doc.pos_x, doc.pos_y, doc.largura, doc.altura = float(x), float(y), float(w), float(h)
    doc.assinatura_png.save("assinatura.png", ContentFile(png_bytes), save=False)
    doc.arquivo_assinado.save(f"{doc.tipo}_assinado.pdf", ContentFile(assinado), save=False)
    doc.assinado_em = timezone.now()
    doc.assinado_ip = (ip or "")[:64]
    doc.codigo_verificacao = codigo
    doc.status = AssinaturaDocumento.STATUS_ASSINADA
    doc.save()


def cancelar_assinatura(prestacao, tipo: str) -> None:
    doc = AssinaturaDocumento.objects.filter(prestacao=prestacao, tipo=tipo).first()
    if not doc:
        return
    _limpar_assinatura(doc)
    doc.status = AssinaturaDocumento.STATUS_PENDENTE
    doc.identidade_confirmada_em = None
    doc.link_token = ""
    doc.link_criado_em = None
    doc.link_expira_em = None
    doc.save()


# ─────────────────────────────────────────────────────────────────
# Integração: usar o arquivo assinado quando existir
# ─────────────────────────────────────────────────────────────────

def assinatura_assinada(prestacao, tipo: str):
    return (
        AssinaturaDocumento.objects.select_related("signer")
        .filter(prestacao=prestacao, tipo=tipo, status=AssinaturaDocumento.STATUS_ASSINADA)
        .first()
    )


def _bytes_assinado(doc) -> bytes | None:
    if doc and doc.arquivo_assinado:
        with doc.arquivo_assinado.open("rb") as f:
            return f.read()
    return None


def pdf_rt_assinado_ou_gerado(prestacao) -> bytes:
    conteudo = _bytes_assinado(assinatura_assinada(prestacao, AssinaturaDocumento.TIPO_RT))
    if conteudo is not None:
        return conteudo
    from .services import gerar_relatorio_tecnico_pdf

    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=prestacao)
    return gerar_relatorio_tecnico_pdf(relatorio)


def pdf_db_assinado_ou_gerado(prestacao) -> bytes:
    conteudo = _bytes_assinado(assinatura_assinada(prestacao, AssinaturaDocumento.TIPO_DB))
    if conteudo is not None:
        return conteudo
    from .diario_services import gerar_diario_bordo_pdf

    diario, _ = DiarioBordo.objects.get_or_create(prestacao=prestacao)
    return gerar_diario_bordo_pdf(diario)


def assinaturas_status(prestacao) -> dict:
    """Mapa ``{tipo: AssinaturaDocumento|None}`` para uso nos templates."""
    docs = {d.tipo: d for d in AssinaturaDocumento.objects.select_related("signer").filter(prestacao=prestacao)}
    return {
        AssinaturaDocumento.TIPO_RT: docs.get(AssinaturaDocumento.TIPO_RT),
        AssinaturaDocumento.TIPO_DB: docs.get(AssinaturaDocumento.TIPO_DB),
    }
