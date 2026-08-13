from django.contrib import messages
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.cache import cache
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.decorators import method_decorator

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


@login_not_required
def main_preview(request):
    """Prévia isolada do novo contrato visual do ``main``.

    A rota só é registrada sob ``DEBUG``. Ela não consulta dados, aceita escrita
    nem entra na navegação de produção; existe para o dono aprovar as camadas
    visualmente antes de qualquer página real adotar o contrato.
    """
    from core.dev_forms import MainPreviewFiltersForm

    preview_steps = (
        {
            "marker": "✓",
            "marker_aria_hidden": True,
            "state_class": "is-complete",
            "step_label": "Etapa 1",
            "title": "Dados e viajantes",
            "status": "Concluída",
        },
        {
            "marker": "2",
            "marker_aria_hidden": True,
            "state_class": "is-current",
            "aria_current": "step",
            "step_label": "Etapa 2",
            "title": "Roteiro e diárias",
            "status": "Em andamento",
        },
        {
            "marker": "3",
            "marker_aria_hidden": True,
            "state_class": "",
            "step_label": "Etapa 3",
            "title": "Justificativa",
            "status": "Não iniciada",
        },
        {
            "marker": "4",
            "marker_aria_hidden": True,
            "state_class": "",
            "step_label": "Etapa 4",
            "title": "Documentos",
            "status": "Não iniciada",
        },
    )

    return render(
        request,
        "core/main_preview.html",
        {
            "page_title": "Prévia do main",
            "preview_filters": MainPreviewFiltersForm(request.GET or None),
            "preview_steps": preview_steps,
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
