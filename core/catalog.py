"""Fábrica de CRUD de catálogo (`P-02`).

O fluxo "lista + quick add + editar inline + definir padrão + excluir" estava
reimplementado em cinco arquivos e onze catálogos — 1.008 linhas repetindo a
mesma sequência com variações pequenas. Este módulo é o motor; cada app declara
um `CatalogConfig` por catálogo e liga as views geradas no `urls.py`.

**Nenhum template muda.** Os índices de catálogo já são invólucros de 5 a 10
linhas sobre `cotton/lists/list_page_quick_add.html`; a duplicação estava
inteiramente nas views. Por isso `rows_context_key` existe: `planos_trabalho`
passa as linhas como `linhas` e os outros como `rows`, e preservar essa diferença
é mais barato (e mais seguro) do que mexer em quatro templates.

Cada campo de `CatalogConfig` corresponde a uma variação real levantada lendo os
cinco arquivos, não a uma generalização especulativa:

- paginação existe só em `cadastros`;
- busca por `q` existe em sete dos onze;
- "definir padrão" em cinco;
- `?next=` com rótulo de volta próprio em todos, com textos diferentes;
- `CadastroVinculadoError` na exclusão só em `cadastros`;
- as mensagens são literais por catálogo ("Atividade cadastrada." não é
  "Programa cadastrado.").
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.deletion import DelecaoProtegidaError
from core.deletion import excluir_com_protecao
from core.pagination import contexto_paginacao
from core.retorno import next_valido


@dataclass(frozen=True)
class CatalogMessages:
    """As frases exibidas. Literais, porque cada catálogo tem as suas."""

    criado: str
    atualizado: str
    #: recebe o rótulo do objeto — ex.: 'Programa “{}” excluído.'
    excluido: str
    erro_ao_salvar: str = ""
    #: recebe o rótulo do objeto
    padrao_definido: str = ""


@dataclass(frozen=True)
class CatalogConfig:
    """Tudo o que um catálogo tem de próprio."""

    # ── dados ────────────────────────────────────────────────────────────────
    listar: Callable[..., Any]
    get_by_id: Callable[[Any], Any]
    form_class: Any
    row_presenter: Callable[..., dict]

    # ── urls (nomes com namespace, ex. "planos_trabalho:programas_index") ────
    url_index: str
    url_editar: str
    url_excluir: str
    url_definir_padrao: str | None = None

    # ── telas ────────────────────────────────────────────────────────────────
    template_index: str = ""
    template_confirm_delete: str = ""
    contexto: dict[str, Any] = field(default_factory=dict)
    contexto_delete: dict[str, Any] = field(default_factory=dict)
    #: `planos_trabalho` usa "linhas"; os demais, "rows"
    rows_context_key: str = "rows"

    # ── comportamento ────────────────────────────────────────────────────────
    mensagens: CatalogMessages | None = None
    #: como o objeto aparece nas mensagens de exclusão e de padrão
    rotulo: Callable[[Any], str] = lambda obj: str(obj)
    buscar: bool = True
    paginar_por: int | None = None
    #: aceita `?next=` sem inventar fallback; usado pelos catálogos de cadastros
    aceitar_next: bool = False
    #: fallback do `?next=`; sem ele, o catálogo não carrega retorno
    url_fallback_next: str | None = None
    #: rótulo do botão de voltar quando há `?next=` externo, e quando não há
    back_label_com_next: str = ""
    back_label_sem_next: str = ""
    #: JSON dos campos do quick edit, quando o presenter não o monta sozinho
    edit_fields_json: Callable[[Any], str] | None = None
    #: os presenters de ofícios e justificativas montam o `set_default_url`
    #: sozinhos, revertendo a URL por dentro; os do PT recebem pronto
    presenter_recebe_set_default: bool = True
    #: só o presenter de justificativas precisa do `next_url` para compor o
    #: link de "definir padrão"
    presenter_recebe_next_url: bool = False
    #: se as URLs de editar/excluir da linha carregam o `?next=`.
    #: Ofícios, eventos e os catálogos simples do PT usam a URL nua.
    urls_de_linha_com_next: bool = True
    #: sobrescritas granulares; `None` herda `urls_de_linha_com_next`
    url_editar_com_next: bool | None = None
    url_excluir_com_next: bool | None = None
    url_definir_padrao_com_next: bool | None = None
    #: alguns catálogos antigos redirecionam GET em vez de abrir confirmação
    confirmar_exclusao_em_get: bool = True
    #: o que "definir padrão" faz num GET. Presets, modelos de motivo e modelos
    #: de justificativa eram `@require_POST` — GET devolve 405. Cargos e
    #: combustíveis redirecionavam em silêncio. Nos dois casos o GET **não**
    #: altera nada: definir padrão é escrita e não pode acontecer por navegação.
    definir_padrao_get_redireciona: bool = False

    # ── escrita: services do app, quando existirem ───────────────────────────
    criar: Callable[..., Any] | None = None
    atualizar: Callable[..., Any] | None = None
    excluir: Callable[[Any], None] | None = None
    definir_padrao: Callable[[Any], None] | None = None
    #: exceção de vínculo na exclusão (só `cadastros`) e o que fazer com ela
    erro_vinculo: type[Exception] | None = None
    tratar_erro_vinculo: Callable[[HttpRequest], None] | None = None


# ── navegação ────────────────────────────────────────────────────────────────


def _next_url(request: HttpRequest, config: CatalogConfig) -> str:
    """`?next=` validado contra o host, com o fallback do catálogo."""
    if not config.url_fallback_next:
        return next_valido(request) if config.aceitar_next else ""
    candidato = request.POST.get("next") or request.GET.get("next") or ""
    if candidato and url_has_allowed_host_and_scheme(
        candidato, allowed_hosts={request.get_host()}
    ):
        return candidato
    return reverse(config.url_fallback_next)


def _com_next(base: str, next_url: str, config: CatalogConfig) -> str:
    """Anexa `?next=` só quando ele aponta para fora do próprio catálogo."""
    if not (config.url_fallback_next or config.aceitar_next) or not next_url:
        return base
    if (
        config.url_fallback_next
        and next_url == reverse(config.url_fallback_next)
    ):
        return base
    return f"{base}?{urlencode({'next': next_url})}"


def _url_index(config: CatalogConfig, next_url: str = "", base: str | None = None) -> str:
    return _com_next(base or reverse(config.url_index), next_url, config)


def _e_retorno_externo(next_url: str, config: CatalogConfig) -> bool:
    if not next_url:
        return False
    if config.aceitar_next and not config.url_fallback_next:
        return True
    if not config.url_fallback_next:
        return False
    return next_url != reverse(config.url_fallback_next)


# ── escrita ──────────────────────────────────────────────────────────────────


def _salvar(form, request: HttpRequest, config: CatalogConfig, *, instance=None):
    """Grava respeitando o service do app, se houver.

    Sem service, faz o que `eventos` e `planos_trabalho` fazem à mão: salva sem
    commit, garante a área de trabalho e persiste. O `save_m2m` é chamado porque
    presets têm many-to-many.
    """
    if instance is None and config.criar is not None:
        return config.criar(form)
    if instance is not None and config.atualizar is not None:
        return config.atualizar(instance, form)

    obj = form.save(commit=False)
    if getattr(obj, "area_id", None) is None:
        obj.area = getattr(request, "area", None)
    obj.save()
    form.save_m2m()
    return obj


# ── views ────────────────────────────────────────────────────────────────────


def index_view(
    config: CatalogConfig,
    *,
    contexto_extra: Callable[[HttpRequest, str], dict] | None = None,
) -> Callable[[HttpRequest], HttpResponse]:
    """Lista + quick add.

    `contexto_extra` recebe a requisição e o `?next=` já validado. Existe para os
    catálogos cujo rótulo de retorno depende da tela de origem — modelos de
    motivo dizem "Voltar para a Ordem de Serviço" quando se chega por lá.
    """

    def view(request: HttpRequest) -> HttpResponse:
        q = request.GET.get("q", "").strip() if config.buscar else ""
        next_url = _next_url(request, config)
        form = config.form_class(request.POST or None)

        if request.method == "POST" and form.is_valid():
            _salvar(form, request, config)
            messages.success(request, config.mensagens.criado)
            return redirect(_url_index(config, next_url))

        objetos = config.listar(q=q or None) if config.buscar else config.listar()

        page_obj = None
        paginacao = {}
        if config.paginar_por:
            page_params = {}
            if q:
                page_params["q"] = q
            if config.aceitar_next and next_url:
                page_params["next"] = next_url
            paginacao = contexto_paginacao(
                objetos,
                request,
                config.paginar_por,
                query_params=page_params,
            )
            page_obj = paginacao["page_obj"]
            objetos = page_obj.object_list

        linhas = [_linha(obj, config, next_url) for obj in objetos]

        externo = _e_retorno_externo(next_url, config)
        contexto = {
            "q": q,
            config.rows_context_key: linhas,
            "quick_add_form": form,
            "quick_add_next_url": next_url if externo else "",
            **_contexto_navegacao(config, next_url, externo),
            **config.contexto,
            **(contexto_extra(request, next_url) if contexto_extra else {}),
        }
        if page_obj is not None:
            contexto.update(paginacao)
        return render(request, config.template_index, contexto)

    return view


def _contexto_navegacao(config: CatalogConfig, next_url: str, externo: bool) -> dict:
    if not config.url_fallback_next:
        return {}
    return {
        "back_url": next_url,
        "back_label": (
            config.back_label_com_next if externo else config.back_label_sem_next
        ),
    }


def _linha(obj, config: CatalogConfig, next_url: str) -> dict:
    def com_next(base: str, sobrescrita: bool | None) -> str:
        habilitado = (
            config.urls_de_linha_com_next
            if sobrescrita is None
            else sobrescrita
        )
        return _com_next(base, next_url, config) if habilitado else base

    kwargs = {
        "edit_url": com_next(
            reverse(config.url_editar, args=[obj.pk]),
            config.url_editar_com_next,
        ),
        "delete_url": com_next(
            reverse(config.url_excluir, args=[obj.pk]),
            config.url_excluir_com_next,
        ),
        "delete_modal": True,
    }
    if config.url_definir_padrao and config.presenter_recebe_set_default:
        kwargs["set_default_url"] = (
            None
            if getattr(obj, "is_padrao", False)
            else com_next(
                reverse(config.url_definir_padrao, args=[obj.pk]),
                config.url_definir_padrao_com_next,
            )
        )
    if config.presenter_recebe_next_url:
        kwargs["next_url"] = next_url
    linha = config.row_presenter(obj, **kwargs)
    if config.edit_fields_json is not None:
        linha["edit_fields_json"] = config.edit_fields_json(obj)
    return linha


def edit_view(config: CatalogConfig) -> Callable[..., HttpResponse]:
    """Edição inline pelo quick edit — a página standalone não existe mais."""

    def view(request: HttpRequest, pk) -> HttpResponse:
        obj = config.get_by_id(pk)
        next_url = _next_url(request, config)
        if request.method == "POST":
            form = config.form_class(request.POST, instance=obj)
            if form.is_valid():
                _salvar(form, request, config, instance=obj)
                messages.success(request, config.mensagens.atualizado)
            else:
                _avisar_erro(request, form, config)
        return redirect(_url_index(config, next_url))

    return view


def _avisar_erro(request: HttpRequest, form, config: CatalogConfig) -> None:
    """Alguns catálogos mostram os erros do form; outros, uma frase única."""
    if config.mensagens.erro_ao_salvar:
        messages.error(request, config.mensagens.erro_ao_salvar)
        return
    for erros in form.errors.values():
        for erro in erros:
            messages.error(request, erro)


def delete_view(config: CatalogConfig) -> Callable[..., HttpResponse]:
    """POST exclui; GET mostra a confirmação."""

    def view(request: HttpRequest, pk) -> HttpResponse:
        obj = config.get_by_id(pk)
        next_url = _next_url(request, config)
        destino = _url_index(config, next_url)

        if request.method == "POST":
            rotulo = config.rotulo(obj)
            if config.erro_vinculo is not None:
                try:
                    (config.excluir or _excluir_padrao)(obj)
                except config.erro_vinculo:
                    if config.tratar_erro_vinculo:
                        config.tratar_erro_vinculo(request)
                    return redirect(destino)
            else:
                try:
                    (config.excluir or _excluir_padrao)(obj)
                except DelecaoProtegidaError as exc:
                    messages.error(request, str(exc))
                    return redirect(destino)
            messages.success(request, config.mensagens.excluido.format(rotulo))
            return redirect(destino)

        if not config.confirmar_exclusao_em_get:
            return redirect(destino)

        return render(
            request,
            config.template_confirm_delete,
            {
                "object": obj,
                "back_url": destino,
                "cancel_url": destino,
                **config.contexto,
                **config.contexto_delete,
            },
        )

    return view


def _excluir_padrao(obj) -> None:
    excluir_com_protecao(obj)


def set_default_view(config: CatalogConfig) -> Callable[..., HttpResponse]:
    """Definir padrão é escrita, então só acontece por POST.

    As views antigas garantiam isso de duas formas: `@require_POST` (presets,
    modelos de motivo, modelos de justificativa) ou um `if request.method !=
    "POST": return redirect(...)` silencioso (cargos, combustíveis). As duas
    estão preservadas — o que nenhuma das duas faz é gravar num GET.
    """

    def view(request: HttpRequest, pk) -> HttpResponse:
        if request.method != "POST":
            if config.definir_padrao_get_redireciona:
                return redirect(_url_index(config, _next_url(request, config)))
            return HttpResponseNotAllowed(["POST"])

        obj = config.get_by_id(pk)
        next_url = _next_url(request, config)
        if config.definir_padrao is not None:
            config.definir_padrao(obj)
        else:
            obj.is_padrao = True
            obj.save(update_fields=["is_padrao", "updated_at"])
        messages.success(
            request, config.mensagens.padrao_definido.format(config.rotulo(obj))
        )
        return redirect(_url_index(config, next_url))

    return view
