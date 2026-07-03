"""Geração do diário de bordo do veículo a partir do roteiro do ofício.

Cabeçalho (motorista, viatura, ofício, e-protocolo) vem do ofício; as linhas
vêm dos trechos do roteiro. KM inicial/final e necessidade de abastecimento são
complementados pelo usuário e persistidos em ``DiarioBordoTrecho``.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.utils import timezone

from cadastros.selectors import build_configuracao_context
from core.utils.masks import format_placa
from core.utils.masks import format_protocolo
from documentos.services.adapters.xlsx_render import fill_diario_bordo_xlsx
from documentos.services.exceptions import DocumentValidationError
from documentos.services.libreoffice_resolve import resolve_libreoffice_binary
from documentos.services.pdf_engine import build_pdf_unavailable_message
from documentos.services.pdf_engine import resolve_pdf_engine
from oficios.models import Oficio
from roteiros.models import RoteiroTrecho

from .models import DiarioBordo
from .models import DiarioBordoTrecho


def roteiro_efetivo(prestacao):
    """Roteiro usado pelo diário: a cópia ajustada, se existir; senão o do ofício."""
    return prestacao.roteiro_ajustado or getattr(prestacao.oficio, "roteiro", None)


def _copiar_campos_concretos(origem, destino, excluir: set) -> None:
    for campo in origem._meta.concrete_fields:
        if campo.primary_key or campo.name in excluir:
            continue
        setattr(destino, campo.attname, getattr(origem, campo.attname))


def clonar_roteiro(origem):
    """Cria uma cópia independente do roteiro (cabeçalho + destinos + trechos)."""
    from roteiros.models import Roteiro
    from roteiros.models import RoteiroDestino

    novo = Roteiro()
    _copiar_campos_concretos(origem, novo, excluir={"evento"})
    novo.pk = None
    novo.evento = None
    novo.tipo = Roteiro.TIPO_AVULSO
    novo.save()

    for destino in origem.destinos.all():
        nd = RoteiroDestino()
        _copiar_campos_concretos(destino, nd, excluir={"roteiro"})
        nd.pk = None
        nd.roteiro = novo
        nd.save()

    for trecho in origem.trechos.all():
        nt = RoteiroTrecho()
        _copiar_campos_concretos(trecho, nt, excluir={"roteiro"})
        nt.pk = None
        nt.roteiro = novo
        nt.save()

    return novo


CAMPOS_COMPARACAO_ROTEIRO = [
    "origem_estado_id",
    "origem_cidade_id",
    "saida_dt",
    "duracao_min",
    "chegada_dt",
    "retorno_saida_dt",
    "retorno_duracao_min",
    "retorno_chegada_dt",
    "quantidade_diarias",
    "valor_diarias",
    "observacoes",
    "rota_distancia_manual_km",
    "rota_duracao_manual_min",
    "rota_ajuste_justificativa",
]

CAMPOS_COMPARACAO_TRECHO = [
    "tipo",
    "ordem",
    "origem_estado_id",
    "origem_cidade_id",
    "destino_estado_id",
    "destino_cidade_id",
    "saida_dt",
    "chegada_dt",
    "distancia_km",
    "duracao_estimada_min",
    "tempo_cru_estimado_min",
    "tempo_adicional_min",
]


def snapshot_comparavel_roteiro(roteiro):
    """Dict com os campos relevantes do roteiro (+ destinos/trechos), para comparar
    uma cópia (`roteiro_ajustado`) com o original sem considerar pk/timestamps."""
    dados = {campo: getattr(roteiro, campo) for campo in CAMPOS_COMPARACAO_ROTEIRO}
    dados["destinos"] = [
        (d.cidade_id, d.estado_id, d.ordem) for d in roteiro.destinos.all().order_by("ordem", "id")
    ]
    dados["trechos"] = [
        tuple(getattr(t, campo) for campo in CAMPOS_COMPARACAO_TRECHO)
        for t in roteiro.trechos.all().order_by("ordem", "id")
    ]
    return dados


def diferencas_entre_roteiros(original, copia):
    """Lista as chaves (campo/destinos/trechos) que diferem entre dois roteiros.
    Lista vazia = cópia idêntica ao original (nunca foi de fato ajustada)."""
    a = snapshot_comparavel_roteiro(original)
    b = snapshot_comparavel_roteiro(copia)
    return [chave for chave in a if a[chave] != b[chave]]


def garantir_roteiro_ajustado(prestacao):
    """Garante a cópia editável do roteiro na prestação (clona do ofício na 1ª vez)."""
    if prestacao.roteiro_ajustado_id:
        return prestacao.roteiro_ajustado
    origem = getattr(prestacao.oficio, "roteiro", None)
    if origem is None:
        return None
    copia = clonar_roteiro(origem)
    prestacao.roteiro_ajustado = copia
    prestacao.save(update_fields=["roteiro_ajustado", "atualizado_em"])
    return copia


def diaria_info(prestacao) -> dict:
    """Compara a diária do roteiro ajustado com a do ofício para sinalizar alteração."""
    copia = prestacao.roteiro_ajustado
    if copia is None:
        return {"alterada": False, "ajustado": False}
    original = getattr(prestacao.oficio, "roteiro", None)

    def valor(r):
        return getattr(r, "valor_diarias", None) if r else None

    def qtd(r):
        return (getattr(r, "quantidade_diarias", "") or "").strip() if r else ""

    def moeda(v):
        if v is None:
            return "—"
        try:
            from documentos.services.formatters import format_currency_br

            return format_currency_br(v)
        except Exception:
            return str(v)

    alterada = (valor(original) != valor(copia)) or (qtd(original) != qtd(copia))
    return {
        "alterada": alterada,
        "ajustado": True,
        "valor_oficio": valor(original),
        "valor_ajustado": valor(copia),
        "valor_oficio_label": moeda(valor(original)),
        "valor_ajustado_label": moeda(valor(copia)),
        "qtd_oficio": qtd(original) or "—",
        "qtd_ajustado": qtd(copia) or "—",
    }


def _upper(value: object) -> str:
    return str(value or "").strip().upper()


def _local(dt):
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return timezone.localtime(dt)
    return dt


def _cidade_label(cidade, estado) -> str:
    if cidade is not None:
        return _upper(getattr(cidade, "nome", cidade))
    if estado is not None:
        return _upper(getattr(estado, "sigla", estado))
    return ""


def trechos_ordenados(roteiro) -> list[RoteiroTrecho]:
    """Trechos do roteiro na ordem do documento: IDA (por ordem) e depois RETORNO."""
    if roteiro is None:
        return []
    qs = list(
        roteiro.trechos.select_related(
            "origem_cidade",
            "origem_estado",
            "destino_cidade",
            "destino_estado",
        ),
    )

    def chave(t):
        return (0 if t.tipo == RoteiroTrecho.TIPO_IDA else 1, t.ordem, t.pk)

    return sorted(qs, key=chave)


def sincronizar_trechos(diario: DiarioBordo) -> list[DiarioBordoTrecho]:
    """Garante uma linha de diário por trecho do roteiro, preservando o que já foi digitado."""
    roteiro = roteiro_efetivo(diario.prestacao)
    trechos = trechos_ordenados(roteiro)
    existentes = list(diario.trechos.all().order_by("ordem", "pk"))
    por_trecho = {dt.trecho_id: dt for dt in existentes}
    ids_atuais = {t.id for t in trechos}
    # Linhas cujo trecho deixou de existir (ex.: roteiro foi clonado/recriado):
    # ficam disponíveis para reaproveitar, preservando KM/abastecimento por ordem.
    sobrando = [dt for dt in existentes if dt.trecho_id not in ids_atuais]

    usados = []
    for i, trecho in enumerate(trechos):
        linha = por_trecho.get(trecho.id)
        if linha is None and sobrando:
            linha = sobrando.pop(0)
        if linha is None:
            # Padrão: necessidade de abastecimento = Sim.
            linha = DiarioBordoTrecho(diario=diario, abastecimento=True)
        linha.trecho = trecho
        linha.ordem = i
        linha.save()
        usados.append(linha.pk)

    diario.trechos.exclude(pk__in=usados).delete()
    return list(diario.trechos.select_related("trecho").all())


def _motorista_nome_cpf(oficio: Oficio) -> tuple[str, str]:
    if oficio.motorista_id:
        servidor = oficio.motorista
        return servidor.nome, (servidor.cpf_formatado or "")
    if oficio.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL:
        return (
            (oficio.motorista_manual_nome or "").strip(),
            (oficio.motorista_manual_cpf or "").strip(),
        )
    return "", ""


def _viatura_dados(oficio: Oficio) -> dict:
    if oficio.viatura_id:
        v = oficio.viatura
        return {
            "viatura": _upper(v.get_tipo_display()) if (v.tipo or "").strip() else "",
            "combustivel": _upper(v.combustivel) if v.combustivel_id else "",
            "placa": format_placa(v.placa) if v.placa else "",
        }
    tm = (oficio.transporte_tipo_manual or "").strip()
    return {
        "viatura": _upper(oficio.get_transporte_tipo_manual_display()) if tm else "",
        "combustivel": (
            _upper(oficio.transporte_combustivel_manual)
            if oficio.transporte_combustivel_manual_id
            else ""
        ),
        "placa": format_placa(oficio.transporte_placa_manual) if oficio.transporte_placa_manual else "",
    }


def _abastecimento_label(valor) -> str:
    sim = "X" if valor is True else " "
    nao = "X" if valor is False else " "
    return f"( {sim} ) Sim   ( {nao} ) Não"


def build_diario_bordo_context(diario: DiarioBordo) -> tuple[dict, list[dict]]:
    oficio = diario.prestacao.oficio
    inst = build_configuracao_context()
    motorista_nome, motorista_cpf = _motorista_nome_cpf(oficio)
    viatura = _viatura_dados(oficio)

    header = {
        "divisao": _upper(inst.get("divisao")),
        "unidade_cabecalho": _upper(inst.get("unidade")),
        "oficio_motorista": str(oficio.numero or "").strip(),
        "ano": str(oficio.ano or "").strip(),
        "protocolo_motorista": format_protocolo(oficio.protocolo) or "",
        "viatura": viatura["viatura"],
        "combustivel": viatura["combustivel"],
        "placa": viatura["placa"],
        "placa_reservada": "",
        "motorista": _upper(motorista_nome),
        "cpf_motorista": motorista_cpf,
    }

    linhas = []
    for linha in sincronizar_trechos(diario):
        t = linha.trecho
        saida = _local(getattr(t, "saida_dt", None)) if t else None
        chegada = _local(getattr(t, "chegada_dt", None)) if t else None
        linhas.append(
            {
                "data_saida": saida.strftime("%d/%m/%Y") if saida else "",
                "hora_saida": saida.strftime("%H:%M") if saida else "",
                "km_inicial": linha.km_inicial if linha.km_inicial is not None else "",
                "data_chegada": chegada.strftime("%d/%m/%Y") if chegada else "",
                "hora_chegada": chegada.strftime("%H:%M") if chegada else "",
                "km_final": linha.km_final if linha.km_final is not None else "",
                "origem": _cidade_label(getattr(t, "origem_cidade", None), getattr(t, "origem_estado", None)) if t else "",
                "destino": _cidade_label(getattr(t, "destino_cidade", None), getattr(t, "destino_estado", None)) if t else "",
                "abastecimento": _abastecimento_label(linha.abastecimento),
            },
        )

    return header, linhas


def _template_path() -> Path:
    return Path(settings.BASE_DIR) / "documentos" / "resources" / "diario_bordo.xlsx"


def gerar_diario_bordo_xlsx(diario: DiarioBordo) -> bytes:
    header, trechos = build_diario_bordo_context(diario)
    return fill_diario_bordo_xlsx(template_path=_template_path(), header=header, trechos=trechos)


def gerar_diario_bordo_pdf(diario: DiarioBordo) -> bytes:
    from documentos.services.adapters.excel_pdf import convert_xlsx_to_pdf_excel_com
    from documentos.services.adapters.libreoffice_pdf import convert_xlsx_to_pdf_libreoffice
    from documentos.services.adapters.libreoffice_pdf import convert_xlsx_to_pdf_unoserver

    xlsx_bytes = gerar_diario_bordo_xlsx(diario)
    explicit = (getattr(settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto") or "auto").strip().lower()
    resolution = resolve_pdf_engine(explicit_setting=explicit, prefer_docx_pipeline=True)
    if not resolution.attempt_chain:
        raise DocumentValidationError(build_pdf_unavailable_message(resolution))

    last_error: BaseException | None = None
    tentou = False
    for engine in resolution.attempt_chain:
        try:
            if engine == "word_com":
                # Mesmo motor (MS Office COM), mas para planilhas usa-se o Excel.
                tentou = True
                return convert_xlsx_to_pdf_excel_com(xlsx_bytes)
            if engine == "unoserver":
                tentou = True
                url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", None) or "").strip()
                timeout = float(getattr(settings, "DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS", 3) or 3)
                return convert_xlsx_to_pdf_unoserver(
                    xlsx_bytes=xlsx_bytes,
                    unoserver_url=url,
                    timeout_seconds=timeout,
                )
            if engine == "libreoffice":
                tentou = True
                binary = resolve_libreoffice_binary()
                if not binary:
                    raise DocumentValidationError("LibreOffice indisponível para gerar PDF.")
                return convert_xlsx_to_pdf_libreoffice(xlsx_bytes=xlsx_bytes, libreoffice_binary=binary)
            # 'simple_fallback' não suporta planilhas — ignorado.
        except Exception as exc:
            last_error = exc
            continue

    msg = (
        build_pdf_unavailable_message(resolution)
        if not tentou
        else "Não foi possível converter o diário de bordo para PDF."
    )
    if last_error is not None:
        raise DocumentValidationError(msg) from last_error
    raise DocumentValidationError(msg)


def nome_arquivo_diario(diario: DiarioBordo, formato: str = "xlsx") -> str:
    pc = diario.prestacao
    oficio = pc.oficio.numero_formatado.replace("/", "-")
    ext = "pdf" if formato == "pdf" else "xlsx"
    return f"DIARIO_DE_BORDO_OFICIO_{oficio}.{ext}"
