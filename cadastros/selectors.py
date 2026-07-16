from django.db.models import Q
from django.shortcuts import get_object_or_404

from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area
from core.tenancy import get_current_area

from .models import AssinaturaConfiguracao
from .models import Cargo
from .models import ConfiguracaoSistema
from .models import Cidade
from .models import Combustivel
from .models import Estado
from .models import Servidor
from .models import Unidade
from .models import Viatura


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


def listar_servidores(q=None):
    queryset = filter_queryset_by_area(Servidor.objects).select_related("cargo", "unidade").order_by("nome")
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


def listar_viaturas(q=None):
    queryset = (
        filter_queryset_by_area(Viatura.objects)
        .select_related("combustivel", "unidade")
        .prefetch_related("motoristas")
        .order_by("placa")
    )
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


def get_configuracao_sistema():
    return ConfiguracaoSistema.get_for_area(get_current_area())


def build_configuracao_context():
    configuracao = get_configuracao_sistema()
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
        "divisao": configuracao.divisao.nome if configuracao.divisao_id else "",
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
