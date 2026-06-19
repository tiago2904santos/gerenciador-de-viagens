from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.utils import timezone

from documentos.services.adapters.docxtpl_render import render_docx_bytes

from .models import RelatorioTecnico

_MESES = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_extenso(dt) -> str:
    return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"


def _sede() -> str:
    try:
        from cadastros.models import ConfiguracaoSistema
        cfg = ConfiguracaoSistema.objects.first()
        return cfg.cidade_endereco if cfg else ""
    except Exception:
        return ""


def gerar_relatorio_tecnico_docx(relatorio: RelatorioTecnico) -> bytes:
    pc = relatorio.prestacao
    oficio = pc.oficio
    servidor = pc.servidor
    hoje = timezone.localdate()

    context = {
        "oficio": oficio.numero_formatado,
        "assunto_oficio": oficio.assunto or "",
        "sede": _sede(),
        "data_atual_extenso": _data_extenso(hoje),
        "nome_servidor": servidor.nome,
        "rg_servidor": servidor.rg_formatado,
        "diaria": relatorio.diaria,
        "translado": relatorio.translado,
        "combustivel": relatorio.combustivel,
        "passagem": relatorio.passagem,
        "motivo": oficio.motivo or "",
        "atividade": relatorio.atividade,
        "conclusao": relatorio.conclusao,
        "medidas": relatorio.medidas,
        "info_complementares": relatorio.info_complementares,
    }

    template_path = Path(settings.BASE_DIR) / "documentos" / "resources" / "relatorio-tecnico.docx"
    return render_docx_bytes(template_path=template_path, context=context)


def nome_arquivo_rt(relatorio: RelatorioTecnico) -> str:
    pc = relatorio.prestacao
    nome = pc.servidor.nome.replace(" ", "_").upper()
    oficio = pc.oficio.numero_formatado.replace("/", "-")
    return f"RT_{nome}_OFICIO_{oficio}.docx"
