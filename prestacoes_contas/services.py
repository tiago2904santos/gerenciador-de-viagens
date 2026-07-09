from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from cadastros.selectors import build_configuracao_context
from core.normalizers import normalize_spaces
from documentos.services.facade import build_default_facade
from documentos.services.adapters.docxtpl_render import render_docx_bytes
from documentos.services.adapters.libreoffice_pdf import convert_docx_to_pdf_libreoffice
from documentos.services.adapters.libreoffice_pdf import convert_docx_to_pdf_unoserver
from documentos.services.adapters.word_pdf import convert_docx_to_pdf_word_com
from documentos.services.exceptions import DocumentValidationError
from documentos.services.formatters import format_city_uf
from documentos.services.formatters import format_currency_br
from documentos.services.formatters import format_document_display
from documentos.services.libreoffice_resolve import resolve_libreoffice_binary
from documentos.services.pdf_engine import build_pdf_unavailable_message
from documentos.services.pdf_engine import resolve_pdf_engine
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from oficios.assunto_oficio import resolver_assunto_oficio
from oficios.documents import build_canonical_document_payload
from oficios.docxtpl_context import build_oficio_docxtpl_context

from .diario_services import gerar_diario_bordo_pdf
from .diario_services import sincronizar_trechos
from .forms import DEFAULT_CUSTEIO_VALUES
from .models import DiarioBordo
from .models import PrestacaoDocumentoAnexo
from .models import RelatorioTecnico

_MESES = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_extenso(dt) -> str:
    return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"


def _as_local_date(dt):
    if dt is None:
        return None
    if hasattr(dt, "date"):
        if timezone.is_aware(dt):
            return timezone.localtime(dt).date()
        return dt.date()
    return dt


def _data_retorno_oficio(oficio):
    roteiro = getattr(oficio, "roteiro", None)
    if roteiro is None:
        return None

    dt = (
        getattr(roteiro, "retorno_chegada_dt", None)
        or getattr(roteiro, "chegada_dt", None)
        or getattr(roteiro, "retorno_saida_dt", None)
    )
    if dt:
        return _as_local_date(dt)

    trecho = roteiro.trechos.order_by("-chegada_dt", "-ordem", "-pk").first()
    if trecho and trecho.chegada_dt:
        return _as_local_date(trecho.chegada_dt)
    return None


def _add_dias_uteis(data, quantidade: int):
    atual = data
    restantes = quantidade
    while restantes > 0:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            restantes -= 1
    return atual


def _data_relatorio_tecnico(oficio):
    hoje = timezone.localdate()
    retorno = _data_retorno_oficio(oficio)
    if retorno is None:
        return hoje
    limite = _add_dias_uteis(retorno, 3)
    if hoje < retorno:
        return retorno
    return min(hoje, limite)


def _sede() -> str:
    try:
        from cadastros.models import ConfiguracaoSistema
        cfg = ConfiguracaoSistema.objects.first()
        return cfg.cidade_endereco if cfg else ""
    except Exception:
        return ""


def diaria_inicial_da_prestacao(prestacao) -> str:
    try:
        oficio = prestacao.oficio
        roteiro = oficio.roteiro
        if roteiro and roteiro.valor_diarias:
            total_servidores = oficio.servidores.count() or 1
            valor_por_servidor = Decimal(roteiro.valor_diarias) / Decimal(total_servidores)
            return format_currency_br(valor_por_servidor)
    except Exception:
        pass
    return ""


def relatorio_tecnico_default_values(prestacao) -> dict:
    values = dict(DEFAULT_CUSTEIO_VALUES)
    diaria = diaria_inicial_da_prestacao(prestacao)
    if diaria:
        values["diaria"] = diaria
    return values


def garantir_campos_padrao_relatorio_tecnico(relatorio: RelatorioTecnico) -> list[str]:
    defaults = relatorio_tecnico_default_values(relatorio.prestacao)
    update_fields = []
    for campo in ("diaria", "translado", "combustivel", "passagem"):
        valor_atual = normalize_spaces(getattr(relatorio, campo, "") or "")
        valor_padrao = normalize_spaces(defaults.get(campo) or "")
        if not valor_atual and valor_padrao:
            setattr(relatorio, campo, valor_padrao)
            update_fields.append(campo)
    if update_fields:
        relatorio.save(update_fields=[*update_fields, "atualizado_em"])
    return update_fields


def _endereco_institucional(inst: dict) -> str:
    logradouro = format_document_display(inst.get("logradouro"))
    numero = str(inst.get("numero") or "").strip()
    bairro = format_document_display(inst.get("bairro"))
    cidade = str(inst.get("cidade_endereco") or "").strip()
    uf = str(inst.get("uf") or "").strip().upper()
    cidade_uf = format_city_uf(f"{cidade}/{uf}") if cidade and uf else format_document_display(cidade) or uf
    cep = str(inst.get("cep_formatado") or inst.get("cep") or "").strip()
    cep_label = f"CEP {cep}" if cep else ""
    return ", ".join(part for part in (logradouro, numero, bairro, cidade_uf, cep_label) if part)


def _upper_header_value(value: object) -> str:
    return str(value or "").strip().upper()


def _assunto_relatorio_tecnico(oficio) -> str:
    try:
        termo = resolver_assunto_oficio(oficio).get("assunto_termo") or ""
    except Exception:
        termo = ""
    if termo:
        return termo[:1].upper() + termo[1:]

    assunto = str(oficio.assunto or "").strip()
    assunto_upper = assunto.upper()
    if assunto_upper == "AUTORIZACAO":
        return "Autorização"
    if assunto_upper == "CONVALIDACAO":
        return "Convalidação"
    return format_document_display(assunto)


def build_relatorio_tecnico_context(relatorio: RelatorioTecnico, servidor) -> dict:
    pc = relatorio.prestacao
    oficio = pc.oficio
    data_rt = _data_relatorio_tecnico(oficio)
    inst = build_configuracao_context()
    defaults = relatorio_tecnico_default_values(pc)

    divisao_cabecalho = _upper_header_value(inst.get("divisao"))
    unidade_cabecalho = _upper_header_value(inst.get("unidade"))
    unidade_rodape = (
        format_document_display(inst.get("divisao"))
        or format_document_display(inst.get("unidade"))
        or format_document_display(inst.get("nome_orgao"))
    )

    return {
        "oficio": oficio.numero_formatado,
        "assunto_oficio": _assunto_relatorio_tecnico(oficio),
        "sede": inst.get("cidade_endereco") or _sede(),
        "data_atual_extenso": _data_extenso(data_rt),
        "divisao": divisao_cabecalho,
        "unidade_cabecalho": unidade_cabecalho,
        "unidade_rodape": unidade_rodape,
        "endereco": _endereco_institucional(inst),
        "telefone": inst.get("telefone_formatado") or inst.get("telefone") or "",
        "email": str(inst.get("email") or "").strip().lower(),
        "nome_servidor": servidor.nome,
        "cpf_servidor": servidor.cpf_formatado,
        "diaria": normalize_spaces(relatorio.diaria or "") or defaults.get("diaria", ""),
        "translado": normalize_spaces(relatorio.translado or "") or defaults.get("translado", ""),
        "combustivel": normalize_spaces(relatorio.combustivel or "") or defaults.get("combustivel", ""),
        "passagem": normalize_spaces(relatorio.passagem or "") or defaults.get("passagem", ""),
        "motivo": relatorio.motivo or oficio.motivo or "",
        "atividade": relatorio.atividade,
        "conclusao": relatorio.conclusao,
        "medidas": relatorio.medidas,
        "info_complementares": relatorio.info_complementares,
    }


def gerar_relatorio_tecnico_docx(relatorio: RelatorioTecnico, servidor) -> bytes:
    garantir_campos_padrao_relatorio_tecnico(relatorio)
    context = build_relatorio_tecnico_context(relatorio, servidor)
    template_path = Path(settings.BASE_DIR) / "documentos" / "resources" / "relatorio-tecnico.docx"
    return render_docx_bytes(template_path=template_path, context=context)


def gerar_relatorio_tecnico_pdf(relatorio: RelatorioTecnico, servidor) -> bytes:
    docx_bytes = gerar_relatorio_tecnico_docx(relatorio, servidor)
    explicit = (getattr(settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto") or "auto").strip().lower()
    resolution = resolve_pdf_engine(explicit_setting=explicit, prefer_docx_pipeline=True)
    if not resolution.attempt_chain:
        raise DocumentValidationError(build_pdf_unavailable_message(resolution))

    last_error: BaseException | None = None
    for engine in resolution.attempt_chain:
        try:
            if engine == "word_com":
                return convert_docx_to_pdf_word_com(docx_bytes)
            if engine == "unoserver":
                url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", None) or "").strip()
                timeout = float(getattr(settings, "DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS", 3) or 3)
                return convert_docx_to_pdf_unoserver(
                    docx_bytes=docx_bytes,
                    unoserver_url=url,
                    timeout_seconds=timeout,
                )
            if engine == "libreoffice":
                binary = resolve_libreoffice_binary()
                if not binary:
                    raise DocumentValidationError("LibreOffice indisponivel para gerar PDF.")
                return convert_docx_to_pdf_libreoffice(docx_bytes=docx_bytes, libreoffice_binary=binary)
        except Exception as exc:
            last_error = exc
            continue

    msg = build_pdf_unavailable_message(resolution)
    if last_error is not None:
        raise DocumentValidationError(msg) from last_error
    raise DocumentValidationError(msg)


def nome_arquivo_rt(relatorio: RelatorioTecnico, servidor, formato: str = "docx") -> str:
    nome = servidor.nome.replace(" ", "_").upper()
    oficio = relatorio.prestacao.oficio.numero_formatado.replace("/", "-")
    ext = "pdf" if formato == "pdf" else "docx"
    return f"RT_{nome}_OFICIO_{oficio}.{ext}"


def _pdf_bytes_from_file_field(field, label: str) -> bytes:
    if not field:
        raise DocumentValidationError(f"Anexe o arquivo: {label}.")
    name = str(getattr(field, "name", "") or "")
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        with field.open("rb") as arquivo:
            return arquivo.read()
    if suffix in {".png", ".jpg", ".jpeg"}:
        with field.open("rb") as arquivo:
            return _image_bytes_to_pdf(arquivo.read())
    raise DocumentValidationError(f"Formato inválido em {label}. Use PDF, PNG, JPG ou JPEG.")


def _pdf_parts_from_anexos(anexos_qs, label: str, legacy_field=None) -> list[tuple[str, bytes]]:
    parts = []
    seen = set()
    for index, anexo in enumerate(anexos_qs.order_by("criado_em", "pk"), start=1):
        name = str(getattr(anexo.arquivo, "name", "") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        parts.append((f"{label} {index}", _pdf_bytes_from_file_field(anexo.arquivo, label)))

    legacy_name = str(getattr(legacy_field, "name", "") or "") if legacy_field is not None else ""
    if legacy_name and legacy_name not in seen:
        parts.append((label, _pdf_bytes_from_file_field(legacy_field, label)))

    if not parts:
        raise DocumentValidationError(f"Anexe o arquivo: {label}.")
    return parts


def _image_bytes_to_pdf(content: bytes) -> bytes:
    from PIL import Image
    from PIL import ImageSequence

    def normalize(frame):
        frame = frame.copy()
        if frame.mode in ("RGBA", "LA") or (frame.mode == "P" and "transparency" in frame.info):
            background = Image.new("RGB", frame.size, "white")
            rgba = frame.convert("RGBA")
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return frame.convert("RGB")

    with Image.open(BytesIO(content)) as image:
        frames = [normalize(frame) for frame in ImageSequence.Iterator(image)]

    if not frames:
        raise DocumentValidationError("Não foi possível ler a imagem anexada.")

    output = BytesIO()
    first, *rest = frames
    first.save(output, format="PDF", save_all=True, append_images=rest)
    return output.getvalue()


def _append_pdf(writer, pdf_bytes: bytes, label: str) -> None:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if getattr(reader, "is_encrypted", False):
            reader.decrypt("")
        if not reader.pages:
            raise DocumentValidationError(f"O PDF de {label} não possui páginas.")
        for page in reader.pages:
            writer.add_page(page)
    except DocumentValidationError:
        raise
    except Exception as exc:
        raise DocumentValidationError(f"Não foi possível ler o PDF de {label}.") from exc


def _merge_pdf_parts(parts: list[tuple[str, bytes]]) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for label, content in parts:
        _append_pdf(writer, content, label)
    output = BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()


def _solicitacoes_do_oficio(prestacao) -> dict[int, str]:
    solicitacoes = {}
    try:
        for ps in prestacao.servidores_prestacao.all():
            numero = str(ps.numero_solicitacao or "").strip()
            if numero:
                solicitacoes[ps.servidor_id] = numero
    except Exception:
        pass
    return solicitacoes


def gerar_oficio_prestacao_pdf(prestacao) -> bytes:
    oficio = prestacao.oficio
    payload = build_canonical_document_payload(oficio, DocumentoTipo.OFICIO)
    docxtpl = build_oficio_docxtpl_context(
        oficio,
        solicitacoes_por_servidor=_solicitacoes_do_oficio(prestacao),
    )
    reference = oficio.numero_formatado.replace("/", "-")
    doc = build_default_facade().gerar(
        tipo=DocumentoTipo.OFICIO,
        formato=DocumentoFormato.PDF,
        payload=payload,
        reference=reference,
        docxtpl_context=docxtpl,
    )
    return doc.conteudo


def gerar_prestacao_consolidado_pdf(servidor_prestacao) -> bytes:
    """Pacote final de um servidor: ofício + despacho (compartilhados) + RT do
    servidor + diário (compartilhado) + comprovante do servidor."""
    prestacao = servidor_prestacao.prestacao

    if not str(servidor_prestacao.numero_solicitacao or "").strip():
        raise DocumentValidationError("Informe o número da solicitação antes de gerar o PDF final.")

    diario, _ = DiarioBordo.objects.get_or_create(prestacao=prestacao)
    sincronizar_trechos(diario)

    despacho_parts = _pdf_parts_from_anexos(
        prestacao.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO),
        "despacho assinado do ofício",
        legacy_field=prestacao.despacho_assinado,
    )
    comprovante_parts = _pdf_parts_from_anexos(
        servidor_prestacao.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE),
        "comprovante de saque/transferência",
    )

    from .assinatura_services import pdf_db_assinado_ou_gerado
    from .assinatura_services import pdf_rt_assinado_ou_gerado

    return _merge_pdf_parts(
        [
            ("ofício", gerar_oficio_prestacao_pdf(prestacao)),
            *despacho_parts,
            ("relatório técnico", pdf_rt_assinado_ou_gerado(servidor_prestacao)),
            ("diário de bordo", pdf_db_assinado_ou_gerado(prestacao)),
            *comprovante_parts,
        ]
    )


def nome_arquivo_prestacao_consolidado(servidor_prestacao) -> str:
    nome = servidor_prestacao.servidor.nome.replace(" ", "_").upper()
    oficio = servidor_prestacao.prestacao.oficio.numero_formatado.replace("/", "-")
    return f"PRESTACAO_{nome}_OFICIO_{oficio}.pdf"
