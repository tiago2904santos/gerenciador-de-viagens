from .models import DiarioBordo
from .models import PrestacaoContas
from .models import RelatorioTecnico


def build_relatorio_from_evento(evento):
    return RelatorioTecnico(
        evento=evento,
        titulo=f"Relatório Técnico - {evento.titulo}",
        objetivo=evento.descricao or "",
        periodo=evento.periodo_display,
        local=evento.destino_display,
        servidores_participantes=_servidores_participantes(evento),
    )


def build_diario_from_evento(evento):
    return DiarioBordo(
        evento=evento,
        titulo=f"Diário de Bordo - {evento.titulo}",
        destino=evento.destino_display,
        periodo=evento.periodo_display,
    )


def get_prestacao_status(evento):
    relatorio = evento.relatorios_tecnicos.order_by("-criado_em").first()
    diario = evento.diarios_bordo.order_by("-criado_em").first()
    prestacao = evento.prestacoes_contas.order_by("-criado_em").first()

    pendencias = []
    if not relatorio:
        pendencias.append("Relatório técnico não criado.")
    if not diario:
        pendencias.append("Diário de bordo não criado.")
    elif not diario.registros.exists():
        pendencias.append("Diário de bordo sem registros.")
    if not prestacao:
        pendencias.append("Prestação de contas não criada.")
    elif not prestacao.relatorio_tecnico_id:
        pendencias.append("Prestação sem relatório técnico vinculado.")
    elif not prestacao.diario_bordo_id:
        pendencias.append("Prestação sem diário de bordo vinculado.")

    return {
        "relatorio": relatorio,
        "diario": diario,
        "prestacao": prestacao,
        "status": prestacao.get_status_display() if prestacao else "Pendente",
        "pendencias": pendencias,
    }


def build_prestacao_from_evento(evento):
    context = get_prestacao_status(evento)
    return PrestacaoContas(
        evento=evento,
        relatorio_tecnico=context["relatorio"],
        diario_bordo=context["diario"],
        status=PrestacaoContas.STATUS_EM_PREENCHIMENTO,
    )


def _servidores_participantes(evento):
    servidores = []
    seen = set()
    for oficio in evento.oficios.prefetch_related("servidores"):
        for servidor in oficio.servidores.all():
            if servidor.pk in seen:
                continue
            seen.add(servidor.pk)
            servidores.append(str(servidor))
    return "\n".join(servidores)
