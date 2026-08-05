from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .selectors import get_oficio_by_id
from .selectors import buscar_viaturas_para_oficio
from .selectors import get_viatura_por_placa_normalizada
from .selectors import viatura_para_resultado_busca


@require_GET
def api_viatura_por_placa(request, pk):
    """Busca viaturas por texto (`q`) ou compatível com consulta só por placa (`placa`).

    Parâmetros opcionais para o picker do wizard:
    - ``motorista_id``: prioriza viaturas vinculadas ao motorista selecionado
      (chip ``suggestion_reason="motorista"``).
    - Por padrão também considera ``equipe`` do ofício para sugestões por unidade.
    """
    from .selectors import _unidade_ids_dos_servidores

    oficio = get_oficio_by_id(pk)
    legado_placa = request.GET.get("placa", "").strip()
    q = request.GET.get("q", "").strip()

    if legado_placa and not q:
        viatura = get_viatura_por_placa_normalizada(legado_placa)
        if viatura is None:
            return JsonResponse({"found": False})
        return JsonResponse(
            {
                "found": True,
                "id": viatura.pk,
                "placa_formatada": viatura.placa_formatada,
                "modelo": viatura.modelo or "",
                "combustivel_id": viatura.combustivel_id,
                "tipo": viatura.tipo or "",
            }
        )

    equipe_ids = list(oficio.servidores.values_list("pk", flat=True))

    motorista_id_raw = request.GET.get("motorista_id", "").strip()
    try:
        motorista_id = int(motorista_id_raw) if motorista_id_raw else None
    except (TypeError, ValueError):
        motorista_id = None

    if len(q) < 2 and not equipe_ids and not motorista_id:
        return JsonResponse({"results": []})

    encontradas = buscar_viaturas_para_oficio(
        q,
        equipe_servidor_ids=equipe_ids or None,
        motorista_id=motorista_id,
    )
    unidade_match_ids = _unidade_ids_dos_servidores(equipe_ids)
    results = [
        viatura_para_resultado_busca(
            v,
            motorista_id=motorista_id,
            unidade_match_ids=unidade_match_ids,
        )
        for v in encontradas
    ]
    # Ordenar: motorista_match -> unidade_match -> demais (mantém ordem por placa do queryset).
    reason_order = {"motorista": 0, "unidade": 1}
    results.sort(key=lambda r: reason_order.get(r.get("suggestion_reason") or "", 2))
    return JsonResponse({"results": results})
