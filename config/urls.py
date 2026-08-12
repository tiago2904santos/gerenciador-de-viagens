from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path

from core.admin_login import admin_login_com_limite


urlpatterns = [
    # QA-01: precisa vir ANTES de admin.site.urls — o resolver casa a primeira rota,
    # e é assim que o login do admin passa a ter o mesmo limite de tentativas do
    # login da aplicação. `reverse("admin:login")` continua devolvendo /admin/login/,
    # que é justamente esta view.
    path("admin/login/", admin_login_com_limite, name="admin_login"),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("usuarios/", include("usuarios.urls")),
    path("cadastros/", include("cadastros.urls")),
    path("roteiros/", include("roteiros.urls")),
    path("eventos/", include("eventos.urls")),
    path("documentos/", include("documentos.urls")),
    path("oficios/", include("oficios.urls")),
    path("termos/", include("termos.urls")),
    path("justificativas/", include("justificativas.urls")),
    path("planos-trabalho/", include("planos_trabalho.urls")),
    path("ordens-servico/", include("ordens_servico.urls")),
    path("prestacoes-contas/", include("prestacoes_contas.urls")),
    path("integracoes/google-drive/", include("integracoes.google_drive.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
