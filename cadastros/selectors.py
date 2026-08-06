from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404

from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area
from core.tenancy import get_current_area

from .models import Cargo
from .models import ConfiguracaoSistema
from .models import Cidade
from .models import Combustivel
from .models import Estado
from .models import Servidor
from .models import TabelaDiaria
from .models import Unidade
from .models import Viatura


def listar_tabelas_diaria():
    """Vigências de diária, da mais recente para a mais antiga.

    Não passa por ``filter_queryset_by_area``: os valores de diária vêm de
    norma externa e valem para todas as áreas — separá-los por área abriria a
    porta para duas áreas cobrarem valores diferentes pela mesma viagem.
    """
    return TabelaDiaria.objects.all()


def listar_unidades(q=None):
    queryset = filter_queryset_by_area(Unidade.objects).order_by("nome")
    if q:
        q = remove_accents(q)
        queryset = queryset.filter(Q(nome__unaccent__icontains=q) | Q(sigla__unaccent__icontains=q))
    return queryset


def listar_cidades(q=None):
    queryset = Cidade.objects.select_related("estado").order_by("estado__sigla", "nome")
    if q:
        q = remove_accents(q)
        queryset = queryset.filter(
            Q(nome__unaccent__icontains=q)
            | Q(uf__unaccent__icontains=q)
            | Q(estado__nome__unaccent__icontains=q)
            | Q(estado__sigla__unaccent__icontains=q)
        )
    return queryset


def listar_estados(q=None):
    queryset = Estado.objects.order_by("nome")
    if q:
        q = remove_accents(q)
        queryset = queryset.filter(Q(nome__unaccent__icontains=q) | Q(sigla__unaccent__icontains=q))
    return queryset


def get_unidade_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(Unidade.objects), pk=pk)


def get_cidade_by_id(pk):
    return get_object_or_404(Cidade.objects.select_related("estado"), pk=pk)


def get_estado_by_id(pk):
    return get_object_or_404(Estado, pk=pk)


def buscar_estado_por_sigla(sigla):
    """Devolve `None` quando a sigla nao existe — quem chama decide a resposta."""
    return Estado.objects.filter(sigla=sigla).first()


def rotulo_da_sede_configurada():
    """Nome da sede das Configuracoes — origem fixa da previa de Destinos.

    Morava copiada nas views de Eventos, Termos e Ordens de Servico (tres
    copias identicas, byte a byte). E consulta, entao vive aqui: as tres
    telas so consomem o rotulo. Devolve string vazia quando a configuracao
    nao aponta cidade nem estado — quem chama decide o que exibir.
    """
    from .services import resolver_sede_ids_desde_configuracao

    estado_id, cidade_id, _aviso = resolver_sede_ids_desde_configuracao()
    if cidade_id:
        cidade = Cidade.objects.filter(pk=cidade_id).only("nome").first()
        if cidade and cidade.nome:
            return cidade.nome
    if estado_id:
        estado = Estado.objects.filter(pk=estado_id).only("sigla", "nome").first()
        if estado:
            return estado.sigla or estado.nome
    return ""


def listar_cargos(q=None):
    queryset = filter_queryset_by_area(Cargo.objects).order_by("nome")
    if q:
        queryset = queryset.filter(Q(nome__unaccent__icontains=remove_accents(q)))
    return queryset


def get_cargo_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(Cargo.objects), pk=pk)


def listar_combustiveis(q=None):
    queryset = filter_queryset_by_area(Combustivel.objects).order_by("nome")
    if q:
        queryset = queryset.filter(Q(nome__unaccent__icontains=remove_accents(q)))
    return queryset


def get_combustivel_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(Combustivel.objects), pk=pk)


def cargos_mais_frequentes_servidores(limit=3):
    """Cargos com mais servidores na área atual (só os que têm ao menos um)."""
    return list(
        filter_queryset_by_area(Cargo.objects)
        .annotate(servidores_count=Count("servidores"))
        .filter(servidores_count__gt=0)
        .order_by("-servidores_count", "nome")[:limit]
    )


def listar_servidores(q=None, cargo_id=None):
    queryset = filter_queryset_by_area(Servidor.objects).select_related("cargo", "unidade").order_by("nome")
    if cargo_id:
        queryset = queryset.filter(cargo_id=cargo_id)
    if q:
        q_unaccent = remove_accents(q)
        queryset = queryset.filter(
            Q(nome__unaccent__icontains=q_unaccent)
            | Q(cpf__icontains=q)
            | Q(rg__icontains=q)
            | Q(cargo__nome__unaccent__icontains=q_unaccent)
            | Q(unidade__nome__unaccent__icontains=q_unaccent)
            | Q(unidade__sigla__unaccent__icontains=q_unaccent)
        )
    return queryset


def get_servidor_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(Servidor.objects).select_related("cargo", "unidade"), pk=pk)


def combustiveis_mais_frequentes_viaturas(limit=3):
    """Combustíveis com mais viaturas na área atual (só os que têm ao menos uma)."""
    return list(
        filter_queryset_by_area(Combustivel.objects)
        .annotate(viaturas_count=Count("viaturas"))
        .filter(viaturas_count__gt=0)
        .order_by("-viaturas_count", "nome")[:limit]
    )


def listar_viaturas(q=None, combustivel_id=None, unidade_id=None):
    queryset = (
        filter_queryset_by_area(Viatura.objects)
        .select_related("combustivel", "unidade")
        .prefetch_related("motoristas")
        .order_by("placa")
    )
    if combustivel_id:
        queryset = queryset.filter(combustivel_id=combustivel_id)
    if unidade_id:
        queryset = queryset.filter(unidade_id=unidade_id)
    if q:
        q_unaccent = remove_accents(q)
        queryset = (
            queryset.filter(
                Q(placa__icontains=q)
                | Q(modelo__unaccent__icontains=q_unaccent)
                | Q(combustivel__nome__unaccent__icontains=q_unaccent)
                | Q(tipo__unaccent__icontains=q_unaccent)
                | Q(unidade__nome__unaccent__icontains=q_unaccent)
                | Q(unidade__sigla__unaccent__icontains=q_unaccent)
                | Q(motoristas__nome__unaccent__icontains=q_unaccent)
            )
            .distinct()
        )
    return queryset


def get_viatura_by_id(pk):
    return get_object_or_404(
        filter_queryset_by_area(Viatura.objects)
        .select_related("combustivel", "unidade")
        .prefetch_related("motoristas"),
        pk=pk,
    )


def get_configuracao_sistema(area=None):
    """Resolve a configuração institucional da área.

    Prefira passar ``area`` (ex.: ``ordem.area`` / ``oficio.area``) quando o
    documento já conhece o tenant — em Celery e outros contextos sem request,
    ``get_current_area()`` é ``None`` e cairia na configuração legada sem área,
    trocando o assinante da OS pelo destinatário global do Ofício.
    """
    if area is None:
        area = get_current_area()
    return ConfiguracaoSistema.get_for_area(area)


def build_configuracao_context(area=None):
    configuracao = get_configuracao_sistema(area=area)
    cidade_doc = configuracao.cidade_endereco or ""
    assinaturas: dict = {}
    for ass in configuracao.assinaturas.filter(ativo=True).select_related("servidor__cargo").order_by("tipo", "ordem"):
        assinaturas.setdefault(ass.tipo, []).append({
            "servidor": ass.servidor,
            "nome": ass.servidor.nome if ass.servidor else "",
            "ordem": ass.ordem,
        })
    return {
        "nome_orgao": configuracao.nome_orgao,
        "sigla_orgao": configuracao.sigla_orgao,
        # Campo "divisão" removido do cabeçalho: mantido vazio apenas por
        # compatibilidade com placeholders/consumidores antigos.
        "divisao": "",
        "unidade": configuracao.unidade.nome if configuracao.unidade_id else "",
        "destinatario_oficio": configuracao.destinatario_oficio,
        "destinatario_oficio_nome": configuracao.destinatario_oficio_nome,
        "destinatario_oficio_cargo": configuracao.destinatario_oficio_cargo,
        "destinatario_oficio_unidade": configuracao.destinatario_oficio_unidade,
        # Compatibilidade: placeholders antigos "sede" passam a refletir cidade_endereco.
        "sede": cidade_doc,
        "nome_chefia": configuracao.nome_chefia,
        "cargo_chefia": configuracao.cargo_chefia,
        "cep": configuracao.cep,
        "cep_formatado": configuracao.cep_formatado,
        "logradouro": configuracao.logradouro,
        "numero": configuracao.numero,
        "bairro": configuracao.bairro,
        "cidade_endereco": cidade_doc,
        "uf": configuracao.uf,
        "telefone": configuracao.telefone,
        "telefone_formatado": configuracao.telefone_formatado,
        "email": configuracao.email,
        "cidade_sede_padrao": configuracao.cidade_sede_padrao,
        "coordenador_adm_plano_trabalho": configuracao.coordenador_adm_plano_trabalho,
        "prazo_justificativa_dias": configuracao.prazo_justificativa_dias,
        "pt_ultimo_numero": configuracao.pt_ultimo_numero,
        "pt_ano": configuracao.pt_ano,
        "pt_sufixo_numero": getattr(configuracao, "pt_sufixo_numero", ""),
        "assinaturas": assinaturas,
    }
