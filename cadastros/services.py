from django.db import transaction

from core.deletion import DelecaoProtegidaError
from core.deletion import excluir_com_protecao
from core.normalizers import normalize_digits
from core.normalizers import normalize_spaces
from core.normalizers import remove_accents
from core.tenancy import get_current_area

from .models import Cargo
from .models import Cidade
from .models import Combustivel
from .models import ConfiguracaoSistema
from .models import Estado
from .services_via_cep import ViaCEPNotFoundError
from .services_via_cep import ViaCEPServiceError
from .services_via_cep import consultar_cep as consultar_cep_externo


class CadastroVinculadoError(Exception):
    pass


def _normalize_for_match(value):
    return remove_accents(normalize_spaces(value).lower())


def _traduz_delecao_protegida(instance):
    try:
        excluir_com_protecao(instance)
    except DelecaoProtegidaError as exc:
        # `NOVO-35`: a mensagem viaja junto. Antes o `raise` era sem argumento e a
        # razão morria aqui, então a tela só sabia dizer "está vinculado a outros
        # registros" — verdadeiro e inútil para quem precisa resolver.
        raise CadastroVinculadoError(str(exc)) from exc


def resolver_cidade_sede_por_endereco(uf, cidade_endereco):
    uf = (uf or "").strip().upper()
    cidade_nome = (cidade_endereco or "").strip()
    if not uf or not cidade_nome:
        return None

    estado = Estado.objects.filter(sigla=uf).first()
    if not estado:
        return None

    alvo = _normalize_for_match(cidade_nome)
    for cidade in Cidade.objects.filter(estado=estado).only("id", "nome", "estado_id"):
        if _normalize_for_match(cidade.nome) == alvo:
            return cidade
    return None


def resolver_sede_ids_desde_configuracao():
    """
    Resolve (estado_id, cidade_id, aviso_ui) a partir do singleton de configuração.

    Ordem: FK cidade_sede_padrao; texto UF + cidade_endereco; CEP (ViaCEP) + localidade.
    Retorna aviso_ui curto quando não for possível resolver (para exibição discreta no editor).
    """
    cfg = ConfiguracaoSistema.get_singleton()
    if getattr(cfg, "cidade_sede_padrao_id", None):
        cidade = (
            Cidade.objects.select_related("estado")
            .filter(pk=cfg.cidade_sede_padrao_id)
            .first()
        )
        if cidade and cidade.estado_id:
            return (int(cidade.estado_id), int(cidade.pk), "")
    cidade_txt = resolver_cidade_sede_por_endereco(cfg.uf, cfg.cidade_endereco)
    if cidade_txt and cidade_txt.estado_id:
        return (int(cidade_txt.estado_id), int(cidade_txt.pk), "")
    cep = normalize_digits(cfg.cep or "")
    if len(cep) == 8:
        try:
            payload = consultar_cep_externo(cep)
        except (ViaCEPServiceError, ViaCEPNotFoundError):
            return (
                None,
                None,
                "Não foi possível identificar cidade/UF pelo CEP das Configurações. "
                "Informe a sede manualmente ou ajuste o CEP nas Configurações.",
            )
        uf = (payload.get("uf") or "").strip().upper()
        loc = (payload.get("cidade") or "").strip()
        cidade_cep = resolver_cidade_sede_por_endereco(uf, loc)
        if cidade_cep and cidade_cep.estado_id:
            return (int(cidade_cep.estado_id), int(cidade_cep.pk), "")
        if uf:
            estado = Estado.objects.filter(sigla=uf).only("id").first()
            if estado:
                return (
                    int(estado.pk),
                    None,
                    "O CEP das Configurações foi encontrado, mas o município não está cadastrado na base. "
                    "Cadastre a cidade ou informe a sede manualmente.",
                )
        return (
            None,
            None,
            "O CEP das Configurações foi encontrado, mas o município não está cadastrado na base. "
            "Cadastre a cidade ou informe a sede manualmente.",
        )
    return (
        None,
        None,
        "Defina CEP ou cidade sede nas Configurações do sistema para pré-preencher a sede automaticamente.",
    )


@transaction.atomic
def salvar_configuracao_sistema(form):
    configuracao = form.save(commit=False)
    cidade_ok = False
    if "uf" in form.cleaned_data:
        uf = form.cleaned_data.get("uf") or ""
        cidade_txt = form.cleaned_data.get("cidade_endereco") or ""
        if uf and cidade_txt:
            cidade_sede = resolver_cidade_sede_por_endereco(uf, cidade_txt)
            configuracao.cidade_sede_padrao = cidade_sede
            cidade_ok = cidade_sede is not None
        else:
            configuracao.cidade_sede_padrao = None

    configuracao.save()
    form.save_m2m()
    return configuracao, cidade_ok


@transaction.atomic
def definir_cargo_padrao(cargo: Cargo) -> Cargo:
    """Marca o cargo como padrão; o `save()` do modelo garante um único padrão."""
    cargo.is_padrao = True
    cargo.save()
    return cargo


@transaction.atomic
def definir_combustivel_padrao(combustivel: Combustivel) -> Combustivel:
    """Marca o combustível como padrão; o `save()` do modelo garante um único padrão."""
    combustivel.is_padrao = True
    combustivel.save()
    return combustivel


def criar_estado(form):
    return form.save()


def atualizar_estado(instance, form):
    return form.save()


def excluir_estado(instance):
    _traduz_delecao_protegida(instance)


def criar_unidade(form):
    unidade = form.save(commit=False)
    if not unidade.area_id:
        unidade.area = get_current_area()
    unidade.save()
    form.save_m2m()
    return unidade


def atualizar_unidade(instance, form):
    unidade = form.save(commit=False)
    if not unidade.area_id:
        unidade.area = get_current_area()
    unidade.save()
    form.save_m2m()
    return unidade


def excluir_unidade(instance):
    _traduz_delecao_protegida(instance)


def criar_cidade(form):
    return form.save()


def atualizar_cidade(instance, form):
    return form.save()


def excluir_cidade(instance):
    _traduz_delecao_protegida(instance)


def criar_cargo(form):
    cargo = form.save(commit=False)
    if not cargo.area_id:
        cargo.area = get_current_area()
    cargo.save()
    form.save_m2m()
    return cargo


def atualizar_cargo(instance, form):
    cargo = form.save(commit=False)
    if not cargo.area_id:
        cargo.area = get_current_area()
    cargo.save()
    form.save_m2m()
    return cargo


def excluir_cargo(instance):
    _traduz_delecao_protegida(instance)


def criar_combustivel(form):
    combustivel = form.save(commit=False)
    if not combustivel.area_id:
        combustivel.area = get_current_area()
    combustivel.save()
    form.save_m2m()
    return combustivel


def atualizar_combustivel(instance, form):
    combustivel = form.save(commit=False)
    if not combustivel.area_id:
        combustivel.area = get_current_area()
    combustivel.save()
    form.save_m2m()
    return combustivel


def excluir_combustivel(instance):
    _traduz_delecao_protegida(instance)


def criar_servidor(form):
    servidor = form.save(commit=False)
    if not servidor.area_id:
        servidor.area = get_current_area()
    servidor.save()
    form.save_m2m()
    return servidor


def atualizar_servidor(instance, form):
    servidor = form.save(commit=False)
    if not servidor.area_id:
        servidor.area = get_current_area()
    servidor.save()
    form.save_m2m()
    return servidor


def prestacoes_com_prova_irrefazivel(servidor):
    """Linhas de prestação do servidor que a exclusão apagaria sem volta (`NOVO-35`).

    **`PrestacaoServidor.todos`, nunca `servidor.prestacoes_servidor`.** O acessor
    reverso herda o `_default_manager`, que desde o `DB-06` é o manager que esconde
    as linhas com `removida_em` preenchido. E o invariante do `DB-06` é justamente
    que linha marcada é a que TEM dados — a sem dados é apagada de fato. Ou seja: a
    relação reversa esconde exatamente o conjunto que esta função existe para
    encontrar. Medido: com a reversa, a guarda bloqueava zero de zero.

    O `Collector` do `delete()` usa `_base_manager` e apaga todas, marcadas
    inclusive — então a assimetria não é acadêmica, é a diferença entre proteger e
    fingir que protege.
    """
    from prestacoes_contas.models import PrestacaoServidor

    return [
        ps
        for ps in PrestacaoServidor.todos.filter(servidor=servidor).select_related(
            "prestacao__oficio",
        )
        if ps.tem_prova_irrefazivel()
    ]


def excluir_servidor(instance):
    """`NOVO-35`: recusa a exclusão quando ela apagaria prova sem volta.

    `PrestacaoServidor.servidor` é `on_delete=CASCADE` — o único `CASCADE` entre as
    treze FKs que apontam para `Servidor`; as outras são `SET_NULL`, `PROTECT` ou
    M2M. Excluir o servidor derrubava as linhas de prestação dele e, por cascata, o
    comprovante de saque e a assinatura eletrônica. Medido: 1 anexo -> 0.

    A guarda fica aqui, no serviço, e **não** como `PROTECT` no schema: `PROTECT`
    bloquearia todo servidor que já tenha entrado em qualquer ofício — no banco de
    desenvolvimento, 3 de 4 — inclusive os que não têm nada a perder. O critério é
    o dado, não o vínculo.
    """
    presas = prestacoes_com_prova_irrefazivel(instance)
    if presas:
        oficios = sorted({ps.prestacao.oficio.numero_formatado for ps in presas})
        raise CadastroVinculadoError(
            f"Não foi possível excluir {instance.nome}: há prestação de contas com "
            f"comprovante, assinatura ou número de solicitação em "
            f"{len(presas)} ofício(s) ({', '.join(oficios)}). "
            f"Remova o servidor da equipe desses ofícios — os dados dele ficam "
            f"preservados — e tente de novo.",
        )
    _traduz_delecao_protegida(instance)


def criar_viatura(form):
    viatura = form.save(commit=False)
    if not viatura.area_id:
        viatura.area = get_current_area()
    viatura.save()
    form.save_m2m()
    return viatura


def atualizar_viatura(instance, form):
    viatura = form.save(commit=False)
    if not viatura.area_id:
        viatura.area = get_current_area()
    viatura.save()
    form.save_m2m()
    return viatura


def excluir_viatura(instance):
    _traduz_delecao_protegida(instance)


def consultar_cep(cep_limpo):
    return consultar_cep_externo(cep_limpo)
