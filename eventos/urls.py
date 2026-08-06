from django.urls import path

from . import views


app_name = "eventos"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("api/cidades/<str:uf>/", views.api_cidades_por_uf, name="api_cidades_por_uf"),
    path("tipos/", views.tipos_index, name="tipos_index"),
    path("tipos/<int:pk>/editar/", views.tipo_editar, name="tipo_update"),
    path("tipos/<int:pk>/excluir/", views.tipo_excluir, name="tipo_delete"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/guiado/", views.detalhe, name="guiado"),
    path("<int:pk>/guiado/etapa-<int:etapa>/", views.detalhe, name="guiado_etapa"),
    path("<int:pk>/guiado_etapa-<int:etapa>/", views.detalhe, name="guiado_etapa_legacy"),
    path("<int:pk>/guiado_termos/", views.guiado_termos, name="guiado_termos"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("<int:pk>/reativar/", views.reativar, name="reativar"),
    path(
        "<int:pk>/anexo/<int:anexo_pk>/conteudo/",
        views.evento_anexo_conteudo,
        name="evento_anexo_conteudo",
    ),
    path(
        "<int:pk>/solicitacao/anexar/",
        views.anexar_solicitacao,
        name="solicitacao_anexar",
    ),
    path(
        "<int:pk>/solicitacao-anexo/<int:anexo_pk>/conteudo/",
        views.solicitacao_anexo_conteudo,
        name="solicitacao_anexo_conteudo",
    ),
    path(
        "<int:pk>/solicitacao-anexo/<int:anexo_pk>/excluir/",
        views.excluir_solicitacao_anexo,
        name="excluir_solicitacao_anexo",
    ),
]
