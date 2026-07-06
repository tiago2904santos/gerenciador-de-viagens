from django.urls import path

from . import views

app_name = "google_drive"

urlpatterns = [
    path("", views.index, name="index"),
    # OAuth
    path("oauth/iniciar/", views.oauth_iniciar, name="oauth_iniciar"),
    path("oauth/callback/", views.oauth_callback, name="oauth_callback"),
    path("oauth/revogar/", views.oauth_revogar, name="oauth_revogar"),
    # API interna (AJAX)
    path("api/pastas/", views.api_listar_pastas, name="api_listar_pastas"),
    path(
        "api/drives-compartilhados/",
        views.api_listar_drives_compartilhados,
        name="api_listar_drives_compartilhados",
    ),
    path(
        "api/compartilhados-comigo/",
        views.api_listar_compartilhados_comigo,
        name="api_listar_compartilhados_comigo",
    ),
    path("api/pastas/criar/", views.api_criar_pasta, name="api_criar_pasta"),
    path("api/pasta-raiz/salvar/", views.salvar_pasta_raiz, name="salvar_pasta_raiz"),
    # Organização em massa
    path("reorganizar/", views.reorganizar_tudo, name="reorganizar_tudo"),
    path("api/previa-reorganizacao/", views.previa_reorganizacao, name="previa_reorganizacao"),
    path("api/status-reorganizacao/", views.status_reorganizacao, name="status_reorganizacao"),
    # Pendências
    path("pendencias/reprocessar/", views.reprocessar_pendencias, name="reprocessar_pendencias"),
]
