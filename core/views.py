from django.contrib import messages
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator

from core import entity_cards
from core import login_throttle
from core.errors import capture
from eventos.models import Evento

from .forms import AlterarSenhaForm
from .forms import LoginForm
from .forms import PerfilUsuarioForm


@login_not_required
def health(request):
    from django.db import connection
    from django.db.utils import DatabaseError

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@login_not_required
def metrics(request):
    expected = (getattr(settings, "METRICS_TOKEN", "") or "").strip()
    supplied = request.headers.get("Authorization", "")
    if not expected or supplied != f"Bearer {expected}":
        raise Http404
    from core.metrics import prometheus_text

    return HttpResponse(
        prometheus_text(),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )


def _encerrar_outras_sessoes(request) -> None:
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    current_key = request.session.session_key
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.session_key == current_key:
            continue
        try:
            if str(session.get_decoded().get("_auth_user_id")) == str(request.user.pk):
                session.delete()
        except Exception as exc:
            capture(exc, "core.login.encerrar_outras_sessoes", session_key=session.session_key)
            continue


@method_decorator(login_not_required, name="dispatch")
class LoginView(DjangoLoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True
    authentication_form = LoginForm

    # A regra vive em core/login_throttle.py, compartilhada com o login do Django
    # Admin (QA-01) — duas portas para o mesmo sistema não podem ter limites
    # diferentes.
    limit = login_throttle.LIMITE
    window_seconds = login_throttle.JANELA_SEGUNDOS

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and login_throttle.excedeu_limite(request):
            form = self.get_form()
            form.add_error(None, login_throttle.MENSAGEM)
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        login_throttle.registrar_falha(self.request)
        return super().form_invalid(form)

    def form_valid(self, form):
        # `NOVO-10`: era `self._rate_key()`, método que saiu daqui quando a regra
        # mudou para `core/login_throttle.py` (`QA-01`). Ninguém percebeu porque
        # esta linha só roda quando o login **dá certo** — e nenhum teste entrava
        # por esta porta com a senha correta (todos usam `force_login`, e o único
        # teste de login bem-sucedido que existia era o do admin, que passa pelo
        # wrapper e não por aqui). Em produção, acertar a senha devolvia 500.
        cache.delete(login_throttle.chave_de_tentativa(self.request))
        return super().form_valid(form)


def dashboard(request):
    """Tela inicial. Sem consulta: o painel de indicadores foi apagado.

    A versao anterior contava oficios, oficios em rascunho, assinaturas
    pendentes e prestacoes pendentes, e ainda listava as viagens dos proximos
    30 dias — cinco consultas por acesso, na rota que TODO login abre
    (`LOGIN_REDIRECT_URL`). O dono apagou o conteudo; as consultas vao junto,
    senao o custo fica pagando por uma tela que nao mostra mais o resultado.
    """
    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Central de Viagens 3",
            "page_section": "Inicio",
            "page_description": "Escolha um modulo para comecar.",
        },
    )


class _MensagemDeExemplo:
    """Imita uma mensagem do Django na galeria do v2 (só `tags` e texto)."""

    def __init__(self, tags: str, texto: str):
        self.tags = tags
        self._texto = texto

    def __str__(self) -> str:
        return self._texto


# Uma seção por página (2026-08-16). A ordem é a de leitura de uma tela: primeiro
# o que se clica, depois o que se preenche, depois como se navega, e por fim as
# telas montadas. Os slugs entram na URL, então mudá-los quebra link guardado.
SECOES_DA_GALERIA = (
    ("acao", "Ação"),
    ("entrada", "Entrada"),
    ("navegacao", "Navegação"),
    ("conteudo", "Conteúdo"),
    ("lista", "Lista"),
    ("formulario", "Formulário avançado"),
    ("estrutura", "Estrutura"),
    ("tipografia", "Tipografia"),
)


@login_not_required
def main_preview(request, secao=None):
    """Galeria do sistema de componentes v2, uma seção por página.

    A rota só é registrada sob ``DEBUG``. Não consulta dados nem aceita escrita:
    existe para o dono aprovar cada componente visualmente, nos dois temas,
    antes de qualquer página real adotá-lo.

    Também é o consumidor de produção dos componentes de ``cotton/v2/`` — o
    repositório proíbe Cotton órfão (``test_componentes_sem_orfao``).

    NOVO-120: a prévia anterior (``main-preview-header``, ``sub-header``,
    ``form-card``, ``entity-card`` e ``collection-panel``) foi apagada junto com
    ``cotton/dev/``, ``css/dev/`` e ``js/dev/``.

    Sem ``secao``, cai na primeira — a rota sem slug continua valendo porque é
    ela que está no menu lateral e nos links já anotados.
    """
    rotulos = dict(SECOES_DA_GALERIA)
    if secao not in rotulos:
        secao = SECOES_DA_GALERIA[0][0]
    return render(
        request,
        "core/main_preview.html",
        {
            "page_title": f"UI Lab · {rotulos[secao]}",
            "secao_atual": secao,
            "secao_label": rotulos[secao],
            "secao_template": f"core/main_preview/{secao}.html",
            "secoes": [
                {
                    "label": label,
                    "url": reverse("core:main_preview_secao", args=[slug]),
                    "is_active": slug == secao,
                }
                for slug, label in SECOES_DA_GALERIA
            ],
            # NOVO-120: alimenta a galeria do sistema v2. Dados fixos, como o
            # resto desta rota — ela existe para aprovar aparência, não para
            # consultar nada.
            # O alerta espera objetos com `tags` e que saibam se imprimir, como
            # as mensagens do Django — um dict sairia como "{'tags': ...}" no
            # template, porque `{{ message }}` chama `str()`.
            "v2_mensagens": tuple(
                _MensagemDeExemplo(tag, texto)
                for tag, texto in (
                    ("success", "Termo salvo com sucesso."),
                    ("warning", "Faltam dados do motorista."),
                    ("error", "Não foi possível gerar o documento."),
                    ("info", "O rascunho é criado na confirmação."),
                )
            ),
            "v2_erros": (
                "Selecione ao menos um servidor.",
                "O período do evento é obrigatório quando não vem do ofício.",
            ),
            "v2_erros_de_campo": ("Este campo é obrigatório.",),
            "v2_etapas": (
                {"label": "Dados e viajantes", "status": "Concluída", "state": "done"},
                {"label": "Roteiro e diárias", "status": "Em andamento", "state": "current"},
                {"label": "Justificativa", "status": "Não iniciada", "state": ""},
                {"label": "Documentos", "status": "Não iniciada", "state": ""},
            ),
            "v2_opcoes": (
                {"value": "1", "label": "Primeira opção"},
                {"value": "2", "label": "Segunda opção"},
                {"value": "3", "label": "Terceira opção"},
            ),
            # Oito opções: o menu tem teto de cinco, então este prova a rolagem.
            "v2_opcoes_longas": tuple(
                {"value": str(i), "label": f"Opção {i:02d}"} for i in range(1, 9)
            ),
            "v2_abas": (
                {"label": "Exemplo", "count": 3, "url": "#", "is_active": True},
                {"label": "Outro", "count": 0, "url": "#", "is_active": False},
            ),
            "v2_abas_tres": (
                {"label": "Todos", "count": 12, "url": "#", "is_active": True},
                {"label": "Ativos", "count": 8, "url": "#", "is_active": False},
                {"label": "Arquivados", "count": 4, "url": "#", "is_active": False},
            ),
            # A lista da galeria filtra de verdade: sem registros que difiram
            # entre si, um filtro quebrado passa despercebido — foi assim que o
            # picker ficou uma sessão inteira sem inicializar, com a tela certa.
            "v2_registros": (
                {
                    "titulo": "Nº 153/2026 · ARAPONGAS/PR",
                    "meta": "12/08 a 15/08/2026 · ADEMAR SCHONS",
                    "status": "Em andamento",
                    "tone": "progress",
                    "busca": "153/2026 arapongas ademar schons protocolo 18.221.443-0",
                },
                {
                    "titulo": "Nº 152/2026 · CURITIBA/PR",
                    "meta": "05/08 a 12/08/2026 · ADRIANO SILVA",
                    "status": "Concluído",
                    "tone": "done",
                    "busca": "152/2026 curitiba adriano silva protocolo 18.220.917-4",
                },
                {
                    "titulo": "Nº 151/2026 · MARINGÁ/PR",
                    "meta": "01/08 a 03/08/2026 · BEATRIZ CARDOSO",
                    "status": "Em andamento",
                    "tone": "progress",
                    "busca": "151/2026 maringa beatriz cardoso protocolo 18.220.554-2",
                },
                {
                    "titulo": "Nº 150/2026 · LONDRINA/PR",
                    "meta": "28/07 a 30/07/2026 · CARLOS MENDES",
                    "status": "Cancelado",
                    "tone": "late",
                    "busca": "150/2026 londrina carlos mendes protocolo 18.219.880-5",
                },
            ),
            # O valor tem de bater com o `status` do registro: o motor compara
            # os dois normalizados, e um rótulo diferente do valor filtra nada.
            "v2_status_opcoes": (
                {"value": "", "label": "Todos os status"},
                {"value": "Em andamento", "label": "Em andamento"},
                {"value": "Concluído", "label": "Concluído"},
                {"value": "Cancelado", "label": "Cancelado"},
            ),
            # O menu de ações montado a partir dos dados, como os presenters o
            # entregam — o caminho que as telas reais usam.
            # Trechos do itinerário, na forma que os presenters de ofício já
            # produzem (`card.trechos`) — a galeria consome o mesmo formato das
            # telas reais, senão o componente só funciona aqui.
            "v2_trechos": [
                {"rota": "ARAPONGAS/PR → LONDRINA/PR", "saida": "12/08 08:00", "chegada": "12/08 09:10"},
                {"rota": "LONDRINA/PR → ARAPONGAS/PR", "saida": "15/08 17:30", "chegada": "15/08 18:40"},
            ],
            "v2_menu": entity_cards.menu(
                "lab-menu-docs",
                "Documentos",
                "ARAPONGAS/PR",
                [
                    # Editar é a PRIMEIRA ação do menu: é a que se usa mais, e
                    # tirá-la da fileira de botões devolve espaço ao rodapé sem
                    # esconder nada — o menu é o lugar onde as ações do registro
                    # já moram.
                    entity_cards.menu_link(
                        "#", "Editar", "Abrir o formulário do registro", "edit", "info",
                    ),
                    entity_cards.menu_link(
                        "#", "Baixar PDF", "Todos os servidores do termo",
                        "pdf", "pdf", download=True,
                    ),
                    entity_cards.menu_link(
                        "#", "Baixar DOCX", "Arquivo editável", "docx", "docx", download=True,
                    ),
                    entity_cards.menu_attach_signed("#", "ARAPONGAS/PR"),
                ],
            ),
            # Opções de duas linhas: o `meta` é o que a variação mostra embaixo.
            "v2_opcoes_pessoas": (
                {"value": "1", "label": "ADEMAR SCHONS", "meta": "Agente de Polícia Judiciária • 1ª Delegacia"},
                {"value": "2", "label": "BEATRIZ CARDOSO", "meta": "Escrivã • 1ª Delegacia"},
                {"value": "3", "label": "CARLOS MENDES", "meta": "Papiloscopista • COPE"},
            ),
            "v2_opcoes_viaturas": (
                {"value": "1", "label": "AAA-1234 - DUSTER", "meta": "FLEX • Descaracterizada • ASCOM"},
                {"value": "2", "label": "AAA-1235 - DUSTER", "meta": "FLEX • Descaracterizada • ASCOM"},
                {"value": "3", "label": "AAA-1244 - DUSTER", "meta": "DIESEL • Descaracterizada"},
            ),
            "v2_pagina": Paginator(range(48), 10).page(2),
            "v2_paginas": (1, 2, 3, "...", 5),
            "shell_css_profile_path": "css/shell.form-components.bundle.css",
        },
    )


@login_required(login_url="core:login")
def perfil(request):
    from django.conf import settings

    from core.tenancy import filter_queryset_by_area
    from integracoes.google_drive import status as drive_status
    from integracoes.google_drive.models import (
        DriveArquivo,
        DriveReorganizacaoJob,
    )
    from integracoes.google_drive.services import (
        escopo_faltante,
        esta_autorizado,
        get_credenciais,
        get_pasta_raiz_id,
    )

    perfil_form = PerfilUsuarioForm(instance=request.user, prefix="perfil")
    senha_form = AlterarSenhaForm(user=request.user, prefix="senha")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "atualizar_perfil":
            perfil_form = PerfilUsuarioForm(request.POST, instance=request.user, prefix="perfil")
            if perfil_form.is_valid():
                perfil_form.save()
                messages.success(request, "Perfil atualizado com sucesso.")
                return redirect("core:perfil")
        elif action == "alterar_senha":
            senha_form = AlterarSenhaForm(user=request.user, data=request.POST, prefix="senha")
            if senha_form.is_valid():
                user = senha_form.save()
                update_session_auth_hash(request, user)
                _encerrar_outras_sessoes(request)
                messages.success(request, "Senha alterada com sucesso.")
                return redirect("core:perfil")
        else:
            messages.error(request, "Ação de perfil inválida.")

    vinculos_area = (
        request.user.vinculos_area.select_related("area")
        .filter(ativo=True)
        .order_by("-area_padrao", "area__sigla")
    )

    cfg_drive = getattr(settings, "GOOGLE_DRIVE", {})
    usuario_drive = request.user if request.user.is_authenticated else None
    area_drive = getattr(request, "area", None)
    drive_creds = get_credenciais(usuario_drive)
    drive_modo = cfg_drive.get("MODO", "mock").lower()
    drive_autorizado = esta_autorizado(usuario_drive)
    drive_pasta_raiz_id = get_pasta_raiz_id(usuario_drive)
    drive_pendencias_resumo = drive_status.resumo_pendencias(
        limite=20,
        usuario=usuario_drive,
        area=area_drive,
    )

    return render(
        request,
        "core/perfil.html",
        {
            "page_title": "Meu perfil",
            "page_section": "Conta",
            "page_description": "Gerencie seus dados de acesso, senha e sessão.",
            "flow_eyebrow": "Conta e segurança",
            "flow_status_label": "Sessão ativa",
            "flow_status_variant": "complete",
            "perfil_form": perfil_form,
            "senha_form": senha_form,
            "vinculos_area": vinculos_area,
            # Google Drive
            "drive_autorizado": drive_autorizado,
            "drive_creds": drive_creds,
            "drive_escopo_faltante": escopo_faltante(usuario_drive),
            "drive_pasta_raiz_id": drive_pasta_raiz_id,
            "drive_pasta_raiz_nome": drive_creds.pasta_raiz_nome if drive_creds else "",
            "drive_total_arquivos": DriveArquivo.objects.filter(artefato__area=area_drive).count(),
            "drive_modo_ativo": drive_modo != "mock",
            # Reorganização em massa
            "drive_pode_reorganizar": bool(drive_pasta_raiz_id)
            and (drive_autorizado or drive_modo == "mock"),
            "drive_total_eventos": filter_queryset_by_area(Evento.objects, area=area_drive).count(),
            # `BE-09`: `all_objects` — `area_drive` é explicita na linha de baixo.
            "drive_job_reorg": DriveReorganizacaoJob.all_objects.filter(
                usuario=usuario_drive,
                area=area_drive,
            ).order_by("-iniciado_em").first(),
            # Pendências (falhas de envio ao Drive)
            "drive_total_pendencias": drive_pendencias_resumo["total"],
            "drive_pendencias": drive_pendencias_resumo["itens"],
        },
    )
