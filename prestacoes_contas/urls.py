from django.urls import path

from . import views


app_name = "prestacoes_contas"

urlpatterns = [
    path("", views.index, name="index"),
    path("prestacao/<int:pc_pk>/documentos/", views.documentos, name="documentos"),
    path("prestacao/<int:pc_pk>/autosave/", views.prestacao_autosave, name="prestacao_autosave"),
    path("prestacao/<int:pc_pk>/autosave-arquivo/", views.prestacao_arquivo_autosave, name="prestacao_arquivo_autosave"),
    path("prestacao/<int:pc_pk>/anexo/<int:anexo_pk>/excluir/", views.prestacao_documento_excluir, name="prestacao_documento_excluir"),
    path("prestacao/<int:pc_pk>/rt/", views.rt_criar, name="rt_criar"),
    path("rt/<int:pk>/autosave/", views.rt_autosave, name="rt_autosave"),
    path("rt/<int:pk>/download/", views.rt_download, name="rt_download"),
    path("rt/<int:pk>/download/<str:formato>/", views.rt_download, name="rt_download_formato"),
    path("prestacao/<int:pc_pk>/diario/", views.diario_criar, name="diario_criar"),
    path("prestacao/<int:pc_pk>/diario/editar-roteiro/", views.diario_editar_roteiro, name="diario_editar_roteiro"),
    path("diario/<int:pk>/autosave/", views.diario_autosave, name="diario_autosave"),
    path("diario/<int:pk>/download/", views.diario_download, name="diario_download"),
    path("diario/<int:pk>/download/<str:formato>/", views.diario_download, name="diario_download_formato"),
    path("prestacao/<int:pc_pk>/consolidado/", views.consolidado, name="consolidado"),
    path("prestacao/<int:pc_pk>/consolidado/download/", views.consolidado_download, name="consolidado_download"),
    # Modelos de texto reutilizáveis
    path("modelos-texto/", views.modelos_index, name="modelos_index"),
    path("modelos-texto/novo/", views.modelo_novo, name="modelo_novo"),
    path("modelos-texto/<int:pk>/editar/", views.modelo_editar, name="modelo_editar"),
    path("modelos-texto/<int:pk>/excluir/", views.modelo_excluir, name="modelo_excluir"),
]
